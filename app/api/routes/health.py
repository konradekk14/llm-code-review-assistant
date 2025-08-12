from fastapi import APIRouter
from datetime import datetime
from app.services.github_service import github_service
from app.services.llm.openai_service import OpenAIService

router = APIRouter()
llm_service = OpenAIService()

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "github": "configured" if github_service else "missing_token",
            "llm": llm_service.get_status()
        }
    }
