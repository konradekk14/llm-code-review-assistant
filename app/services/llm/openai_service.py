from __future__ import annotations
import asyncio, random, time
from typing import Any, Dict, Optional
import httpx
from app.settings import settings 

# communication file with OpenAI API
_OPENAI_BASE = (getattr(settings, "openai_base_url", None) or "https://api.openai.com/v1").rstrip("/")

# this is for global singleton dependency injection
_openai_singleton: Optional['OpenAIService'] = None

# gets singleton instance and ensures only one service exists
def get_openai_service() -> OpenAIService:
    """Get or create the singleton OpenAIService instance."""
    global _openai_singleton
    if _openai_singleton is None:
        _openai_singleton = OpenAIService()
    return _openai_singleton

# this is the actual service class
class OpenAIService:
    def __init__(self):
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.temperature = settings.openai_temperature
        self.max_tokens = settings.openai_max_tokens
        self.org = getattr(settings, "openai_org", None)
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    # creates HTTP client only when needed w/ auth (sets up headers and timeouts)
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            api_key = self.api_key.get_secret_value() if self.api_key else None
            headers = {"Authorization": f"Bearer {api_key}"}
            if self.org:
                headers["OpenAI-Organization"] = self.org
            # a single shared client with sane defaults
            self._client = httpx.AsyncClient(
                base_url=_OPENAI_BASE,
                headers=headers,
                timeout=httpx.Timeout(120.0, connect=10.0, read=120.0),
            )
        return self._client

    # closes the client when the service is no longer needed
    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # retries on specific errors (429, 500, 502, 503, 504) w/ increased delay
    async def _request_with_retries(
        self, method: str, url: str, *, json_body: Optional[dict] = None, max_retries: int = 2
    ) -> httpx.Response:
        client = await self._get_client()
        attempt = 0
        last_exc: Optional[Exception] = None
        while attempt <= max_retries:
            try:
                resp = await client.request(method, url, json=json_body)
                if resp.status_code in (429, 500, 502, 503, 504):
                    # log details so you know *what* is failing
                    try:
                        body = resp.text
                    except Exception:
                        body = "<no-body>"
                    req_id = resp.headers.get("x-request-id")  # useful for support
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

    # the health check endpoint called by llm_status.py
    async def health_check(self) -> Dict[str, Any]:
        """
        Cheap probe that verifies API key validity and model accessibility.
        """
        start = time.perf_counter()
        if not self.available:
            return {"provider": "openai", "status": "degraded", "reason": "missing_api_key"}

        try:
            # best-effort: confirm the configured model is visible/usable
            # GET /v1/models/{model} is cheaper than listing all models
            resp = await self._request_with_retries("GET", f"/models/{self.model}")
            latency_ms = int((time.perf_counter() - start) * 1000)
            data = resp.json()
            return {
                "provider": "openai",
                "status": "ok",
                "model": data.get("id", self.model),
                "latency_ms": latency_ms,
            }
        except httpx.HTTPStatusError as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            status = e.response.status_code
            # make common cases human-readable reasons
            if status in (401, 403):
                reason = "unauthorized_or_forbidden"
            elif status == 404:
                reason = "model_not_found"
            else:
                reason = f"http_{status}"
            return {
                "provider": "openai",
                "status": "degraded",
                "reason": reason,
                "model": self.model,
                "latency_ms": latency_ms,
            }
        except Exception as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return {"provider": "openai", "status": "degraded", "reason": str(e), "model": self.model, "latency_ms": latency_ms}

    # the main method for generating a review
    # prompt as string, checks api serivce is available, and optional paramaters in case.
    async def generate_review(
        self,
        prompt: str,
        *,
        response_format: Optional[dict] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not self.available:
            raise RuntimeError("No OpenAI API key configured.")

        # request body to send to the API
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are an expert software engineer and strict code reviewer."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": self.temperature if temperature is None else temperature,
        }
        if response_format:
            # e.g. {"type": "json_object"} (for structured review output)
            payload["response_format"] = response_format

        # making the API call w/ payload
        resp = await self._request_with_retries("POST", "/chat/completions", json_body=payload)
        data = resp.json()
        # extracting the response content and structuring
        try:
            message = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            # expose raw for debugging, but keep a stable error type
            raise RuntimeError(f"Unexpected OpenAI response shape: {data}")

        return {
            "content": message,
            "provider_used": "openai",
            "provider_name": f"OpenAI {self.model}",
            "usage": data.get("usage", {}),
            "id": data.get("id"),
        }

    #  for monitoring service availability
    def get_status(self) -> Dict[str, Any]:
        return {"available": self.available, "name": f"OpenAI {self.model}" if self.available else None}
