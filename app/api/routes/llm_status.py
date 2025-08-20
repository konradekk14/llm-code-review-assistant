from fastapi import APIRouter, Depends
import asyncio
from typing import Any, Dict, List
from app.services.llm.openai_service import get_openai_service, OpenAIService

router = APIRouter()

@router.get("/llm-status")
async def llm_status(openai: OpenAIService = Depends(get_openai_service)) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    # OpenAI
    checks.append(await openai.health_check())

    # Future providers (safe to stub; won't fail the endpoint)
    # try:
    #     llama = get_llama_service()
    #     checks.append(await llama.health_check())
    # except Exception:
    #     checks.append({"provider": "llama", "status": "degraded", "error": "not_configured"})

    overall = "ok" if any(c.get("status") == "ok" for c in checks) else "degraded"
    return {"overall": overall, "providers": checks}
