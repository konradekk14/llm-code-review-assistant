from __future__ import annotations
import asyncio, time
from typing import Any, Dict, Optional
import httpx
from app.settings import settings

# comm base for hf
_HF_BASE = (getattr(settings, "hf_base_url", None) or "https://api-inference.huggingface.co").rstrip("/")

# glabal singleton
_llama_singleton: Optional["LlamaService"] = None

def get_llama_service() -> "LlamaService":
    global _llama_singleton
    if _llama_singleton is None:
        _llama_singleton = LlamaService()
    return _llama_singleton


class LlamaService:

    def __init__(self):
        self.api_key = getattr(settings, "hf_api_key", None)
        self.model = getattr(settings, "hf_model", None)
        self.temperature = getattr(settings, "hf_temperature", 0.2)
        self.max_tokens = getattr(settings, "hf_max_tokens", 512)
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def available(self) -> bool:
        return bool(self.api_key and self.model)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            api_key = self.api_key.get_secret_value() if self.api_key else None
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            # Shared async client with sensible timeouts
            self._client = httpx.AsyncClient(
                base_url=_HF_BASE,
                headers=headers,
                timeout=httpx.Timeout(120.0, connect=10.0, read=120.0),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request_with_retries(
        self,
        method: str,
        url: str,
        *,
        json_body: Optional[dict] = None,
        max_retries: int = 2,
    ) -> httpx.Response:
        client = await self._get_client()
        attempt = 0
        last_exc: Optional[Exception] = None
        while attempt <= max_retries:
            try:
                resp = await client.request(method, url, json=json_body)
                if resp.status_code in (429, 500, 502, 503, 504):
                    try:
                        body = resp.text
                    except Exception:
                        body = "<no-body>"
                    req_id = resp.headers.get("x-request-id")
                    print(f"[LLM RETRY] {resp.status_code} on {url} (x-request-id={req_id}) body={body[:1000]}")
                resp.raise_for_status()
                return resp
            except httpx.HTTPError as e:
                last_exc = e
                if attempt == max_retries:
                    raise
                await asyncio.sleep(0.25 * (2 ** attempt))
                attempt += 1
        if last_exc:
            raise last_exc
        else:
            raise RuntimeError("Request failed after all retries")

    # verify token and model are available
    async def health_check(self) -> Dict[str, Any]:
        start = time.perf_counter()
        if not self.available:
            return {"provider": "huggingface", "status": "degraded", "reason": "missing_api_key_or_model"}

        try:
            payload = {
                "inputs": "ping",
                "parameters": {
                    "max_new_tokens": 1,
                    "temperature": 0.0,
                    "return_full_text": False,
                },
                "options": {
                    # fast probe
                    "wait_for_model": False,
                    "use_cache": True,
                },
            }
            resp = await self._request_with_retries("POST", f"/models/{self.model}", json_body=payload)
            latency_ms = int((time.perf_counter() - start) * 1000)
            # considered as ok if successful
            return {
                "provider": "huggingface",
                "status": "ok",
                "model": self.model,
                "latency_ms": latency_ms,
            }
        except httpx.HTTPStatusError as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            status = e.response.status_code
            if status in (401, 403):
                reason = "unauthorized_or_forbidden"
            elif status in (404, 422):
                reason = "model_not_found_or_unavailable"
            elif status == 503:
                reason = "model_loading_or_busy"
            else:
                reason = f"http_{status}"
            return {
                "provider": "huggingface",
                "status": "degraded",
                "reason": reason,
                "model": self.model,
                "latency_ms": latency_ms,
            }
        except Exception as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return {
                "provider": "huggingface",
                "status": "degraded",
                "reason": str(e),
                "model": self.model,
                "latency_ms": latency_ms,
            }

    async def generate_review(
        self,
        prompt: str,
        *,
        response_format: Optional[dict] = None,   # kept for API parity; hf serverless doesn't enforce json schemas
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Sends a single-turn prompt to a HF Inference API text-generation model.

        NOTE:
        - If you're using a chat-tuned LLaMA Instruct model, you can pass an already
          well-formed prompt. For multi-turn chat, handle formatting upstream or
          adapt here as needed.
        """
        if not self.available:
            raise RuntimeError("No Hugging Face API key or model configured.")

        # parameters map closely to hf serverless and tgi
        params = {
            "max_new_tokens": max_tokens or self.max_tokens,
            "temperature": self.temperature if temperature is None else temperature,
            "return_full_text": False,  # only return the newly generated tokens
        }

        # prompt based format, not liek openai
        effective_prompt = prompt
        if response_format and response_format.get("type") == "json_object":
            effective_prompt = (
                f"{prompt}\n\n"
                "Return ONLY a valid, minified JSON object. Do not include any prose before or after."
            )

        payload = {
            "inputs": effective_prompt,
            "parameters": params,
            "options": {
                # not blocking on cold start
                "use_cache": True,
                "wait_for_model": True, 
            },
        }

        resp = await self._request_with_retries("POST", f"/models/{self.model}", json_body=payload)
        data = resp.json()

        message: Optional[str] = None
        try:
            if isinstance(data, list) and data:
                message = data[0].get("generated_text")
            elif isinstance(data, dict):
                message = data.get("generated_text") or data.get("answer")
        except Exception:
            pass

        if not message:
            raise RuntimeError(f"Unexpected Hugging Face response shape: {data}")

        return {
            "content": message,
            "provider_used": "huggingface",
            "provider_name": f"Hugging Face {self.model}",
            "usage": {},
            "id": None,
        }

    def get_status(self) -> Dict[str, Any]:
        return {"available": self.available, "name": f"Hugging Face {self.model}" if self.available else None}
