from fastapi.testclient import TestClient
from app.main import app

def test_llm_status_smoke(monkeypatch):
    # monkeypatch OpenAIService.health_check to avoid network calls
    from app.services.llm.openai_service import OpenAIService

    async def fake_health(self):
        return {"provider": "openai", "status": "ok", "model": "test-model", "latency_ms": 10}

    monkeypatch.setattr(OpenAIService, "health_check", fake_health)
    
    # ensure DI singleton exists
    from app.services.llm.openai_service import _openai_singleton
    _openai_singleton = OpenAIService()

    client = TestClient(app)
    r = client.get("/llm-status")
    assert r.status_code == 200
    body = r.json()
    assert body["overall"] == "ok"
    assert any(p["provider"] == "openai" and p["status"] == "ok" for p in body["providers"])
