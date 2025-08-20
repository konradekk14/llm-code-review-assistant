from __future__ import annotations
from functools import lru_cache
from typing import Optional, List, Literal
from pydantic_settings import BaseSettings
from pydantic import Field, SecretStr, field_validator


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # app
    app_name: str = "AI Code Review Assistant"
    version: str = "1.0.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # host server
    host: str = "0.0.0.0"
    port: int = 8000
    allowed_origins: List[str] = Field(default_factory=lambda: ["*"])  # CORS

    # HTTP/client defaults (centralize timeouts/retries)
    http_connect_timeout_s: float = 5.0
    http_read_timeout_s: float = 15.0
    http_total_timeout_s: float = 20.0
    http_max_retries: int = 2

    # GitHub (prefer GitHub App; keep PAT for dev)
    github_api_base: str = "https://api.github.com"
    github_token: Optional[SecretStr] = None  # PAT (dev only)
    github_app_id: Optional[str] = None
    github_webhook_secret: Optional[SecretStr] = None
    github_private_key: Optional[SecretStr] = None  # PEM, handle multiline
    github_app_installation_id: Optional[str] = None  # optional, for app auth

    # openai / compatible
    openai_api_key: Optional[SecretStr] = None
    openai_org: Optional[str] = None
    openai_base_url: Optional[str] = None  # e.g., Azure/OpenAI-compatible gateway
    openai_model: str = "gpt-4o-mini"  # keep configurable; override via env
    openai_max_tokens: int = 1500
    openai_temperature: float = 0.3

    # hugging face or local llms
    hf_api_key: Optional[SecretStr] = None
    hf_model: str = "meta-llama/Meta-Llama-3-8B-Instruct"
    hf_temperature: float = 0.2
    hf_max_tokens: int = 512
    hf_base_url: Optional[str] = None

    # embeddings / vectors 
    embeddings_provider: Literal["openai", "huggingface", "local"] = "openai"
    embeddings_model: str = "text-embedding-3-large"
    vectordb_kind: Literal["pgvector", "qdrant"] = "pgvector"
    vectordb_url: Optional[str] = None          # e.g., postgresql://... or http://qdrant:6333
    vectordb_collection: str = "repo_context"

    # queue / background worker
    queue_kind: Literal["redis"] = "redis"
    redis_url: Optional[str] = None  # e.g., redis://localhost:6379/0

    # set limits
    max_changed_lines_reviewed: int = 4000
    max_findings_per_file: int = 20
    max_concurrent_file_reviews: int = 4

    # logging
    log_level: str = "INFO"
    log_json: bool = False
    sentry_dsn: Optional[str] = None

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    # validators so pydantic can convert env vars to python types
    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, v):
        # allow comma-separated env like: http://localhost:3000,https://your.app
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    def get_github_headers(self) -> dict:
        """
        PAT-only helper (dev). For GitHub App, prefer installation tokens via a dedicated service.
        """
        if not self.github_token:
            raise ValueError("GitHub token (PAT) not configured")
        return {
            "Authorization": f"token {self.github_token.get_secret_value()}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"{self.app_name}/{self.version}",
        }

    # convenience flags for maintainable code
    def is_github_configured(self) -> bool:
        return bool(self.github_token or (self.github_app_id and self.github_private_key))

    def is_openai_configured(self) -> bool:
        return bool(self.openai_api_key)
    
    def is_huggingface_configured(self) -> bool:
        return bool(self.hf_api_key and self.hf_model)

    def require_prod_secrets(self) -> None:
        """
        Fail-fast guard you can call at startup in production.
        """
        if self.environment == "production":
            missing = []
            if not self.is_github_configured():
                missing.append("GitHub App or token")
            if not self.is_openai_configured():
                missing.append("OpenAI API key")
            if not self.allowed_origins or self.allowed_origins == ["*"]:
                missing.append("CORS allowed_origins")
            if missing:
                raise RuntimeError(f"Missing required prod config: {', '.join(missing)}")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# keep this for modules expecting a global, but injecting get_settings() is better
settings = get_settings()
