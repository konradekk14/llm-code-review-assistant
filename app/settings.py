from pydantic_settings import BaseSettings
from typing import Optional
import os
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # app settings
    app_name: str = "AI Code Review Assistant"
    version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"
    
    # server settings
    host: str = "0.0.0.0"
    port: int = 8000
    
    # GitHub config
    github_token: Optional[str] = None
    github_api_base: str = "https://api.github.com"
    
    # OpenAI config
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4"
    openai_max_tokens: int = 1500
    openai_temperature: float = 0.3
    
    # Hugging Face config
    huggingface_api_token: Optional[str] = None
    llama_hf_model: str = "meta-llama/Llama-2-70b-chat-hf"
    
    # local Llama config
    enable_local_llama: bool = False
    llama_local_model: str = "meta-llama/Llama-2-7b-chat-hf"
    
    # logging
    log_level: str = "INFO"
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore"
    }
    
    # get the github api headers
    def get_github_headers(self) -> dict:
        if not self.github_token:
            raise ValueError("GitHub token not configured")
        return {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"{self.app_name}/{self.version}"
        }
    
    # ensure proper configs
    def is_github_configured(self) -> bool:
        return bool(self.github_token)
    
    def is_openai_configured(self) -> bool:
        return bool(self.openai_api_key)
    
    def is_huggingface_configured(self) -> bool:
        return bool(self.huggingface_api_token)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# global settings instance
settings = get_settings()