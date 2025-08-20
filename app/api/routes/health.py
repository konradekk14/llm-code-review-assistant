from fastapi import APIRouter, Depends
from datetime import datetime
from app.services.github_service import github_service
from app.services.llm.openai_service import OpenAIService, get_openai_service

router = APIRouter()

# dependency injection to get the OpenAIService instance
# using for monitoring serivce availability
@router.get("/health")
async def health_check(llm_service: OpenAIService = Depends(get_openai_service)):
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "github": "configured" if github_service else "missing_token",
            "llm": llm_service.get_status()
        }
    }
