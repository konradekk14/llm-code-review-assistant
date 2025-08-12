# app bootstrapper

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.settings import settings
from app.api.routes import health, review, llm_status

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    # log environment/config status
    print(f"Starting {settings.app_name} v{settings.version}")
    yield
    # shutdown (if needed)
    print(f"Shutting down {settings.app_name}")

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="AI-powered code review assistant for GitHub Pull Requests",
    lifespan=lifespan
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# include routers
app.include_router(health.router, prefix="", tags=["Health"])
app.include_router(review.router, prefix="", tags=["Review"])
app.include_router(llm_status.router, prefix="", tags=["LLM Status"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )