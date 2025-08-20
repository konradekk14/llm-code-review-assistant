from fastapi import APIRouter, Depends
from datetime import datetime
from app.services.github_service import github_service
from app.services.llm.openai_service import OpenAIService, get_openai_service
from app.services.llm.llama_service import LlamaService, get_llama_service

router = APIRouter()

# dependency injection to get the OpenAIService instance
# using for monitoring serivce availability
@router.get("/health")
async def health_check(
    openai_service: OpenAIService = Depends(get_openai_service),
    llama_service: LlamaService = Depends(get_llama_service)
):
    # check github service
    github_status = "configured" if github_service else "missing_token"
    
    llm_services = {}
    
    # openai status
    if openai_service.available:
        try:
            openai_status = await openai_service.health_check()
            llm_services["openai"] = {
                "status": openai_status.get("status", "unknown"),
                "model": openai_status.get("model", "unknown"),
                "latency_ms": openai_status.get("latency_ms", 0)
            }
        except Exception as e:
            llm_services["openai"] = {
                "status": "error",
                "error": str(e)
            }
    else:
        llm_services["openai"] = {"status": "not_configured"}
    
    # llama status
    if llama_service.available:
        try:
            llama_status = await llama_service.health_check()
            print(f"LLaMA health check failed: {llama_status}")
            llm_services["llama"] = {
                "status": llama_status.get("status", "unknown"),
                "model": llama_status.get("model", "unknown"),
                "latency_ms": llama_status.get("latency_ms", 0)
            }
        except Exception as e:
            llm_services["llama"] = {
                "status": "error",
                "error": str(e)
            }
    else:
        llm_services["llama"] = {"status": "not_configured"}
    
    # overall health calculation
    overall_status = "healthy"
    if github_status == "missing_token":
        overall_status = "degraded"
    
    # check if any LLM service is working
    working_llms = sum(1 for service in llm_services.values() 
                      if service.get("status") == "ok")
    if working_llms == 0:
        overall_status = "degraded"
    
    return {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "services": {
            "github": github_status,
            "llm_providers": llm_services
        }
    }