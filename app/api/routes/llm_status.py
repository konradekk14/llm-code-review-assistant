
from fastapi import APIRouter
from app.services.llm.openai_service import OpenAIService
# from app.services.llm.llama_service import LLaMAService  # optional

router = APIRouter()

@router.get("/llm-status")
async def llm_status():
    # Here you could check each LLM provider
    openai_service = OpenAIService()
    openai_ok = await openai_service.health_check()

    return {
        "openai": "available" if openai_ok else "unavailable",
        # "llama": "available" if llama_ok else "unavailable"
    }
