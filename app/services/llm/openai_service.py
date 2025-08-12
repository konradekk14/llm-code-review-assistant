import httpx
from app.settings import settings

class OpenAIService:
    def __init__(self):
        self.api_key = settings.openai_api_key
        self.available = bool(self.api_key)

    async def generate_review(self, prompt: str, provider: str = "auto", max_tokens: int = None):
        if not self.api_key:
            raise Exception("No OpenAI API key configured.")

        max_tokens = max_tokens or settings.openai_max_tokens
        async with httpx.AsyncClient() as client:
            payload = {
                "model": settings.openai_model,
                "messages": [
                    {"role": "system", "content": "You are an expert software engineer..."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": settings.openai_temperature
            }
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload
            )
            resp.raise_for_status()
            result = resp.json()
            return {
                "content": result['choices'][0]['message']['content'],
                "provider_used": "openai",
                "provider_name": f"OpenAI {settings.openai_model}"
            }

    def get_status(self):
        return {
            "available": self.available,
            "name": f"OpenAI {settings.openai_model}" if self.available else None
        }
