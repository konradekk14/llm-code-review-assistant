from fastapi import APIRouter, Depends
import asyncio
from typing import Any, Dict, List
from app.services.llm.openai_service import get_openai_service, OpenAIService
from app.services.llm.llama_service import get_llama_service, LlamaService

router = APIRouter()

@router.get("/llm-status")
async def llm_status(openai: OpenAIService = Depends(get_openai_service),
                     llama: LlamaService = Depends(get_llama_service)
                     ) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    # openai
    checks.append(await openai.health_check())

    # llama
    try:
        llama_check = await llama.health_check()
        checks.append(llama_check)
    except Exception as e:
        checks.append({
            "provider": "llama", 
            "status": "degraded", 
            "error": str(e),
            "model": getattr(llama, 'model', 'unknown')
        })

    overall = "ok" if any(c.get("status") == "ok" for c in checks) else "degraded"
    return {"overall": overall, "providers": checks}
