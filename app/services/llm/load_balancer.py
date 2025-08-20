from __future__ import annotations
import asyncio
import time
from typing import Any, Dict, List, Optional, Literal
from dataclasses import dataclass, field
from enum import Enum

from app.services.llm.openai_service import OpenAIService
from app.services.llm.llama_service import LlamaService

class ProviderStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"

@dataclass
class ProviderInfo:
    name: str
    service: OpenAIService | LlamaService
    status: ProviderStatus = ProviderStatus.UNKNOWN
    last_health_check: float = 0.0
    health_check_interval: float = 30.0  # seconds
    consecutive_failures: int = 0
    max_failures: int = 3
    requests_handled: int = 0
    last_request_time: float = 0.0
    total_latency_ms: int = 0
    average_latency_ms: float = 0.0

# load balancer for multiple llm providers w/ health monitoring and failover
class LLMLoadBalancer:
    
    def __init__(self):
        self.providers: List[ProviderInfo] = []
        self.current_provider_index: int = 0
        self.total_requests: int = 0
        self.last_health_check: float = 0.0
        self.health_check_interval: float = 30.0  # seconds
        
    def add_provider(self, name: str, service: OpenAIService | LlamaService) -> None:
        provider = ProviderInfo(name=name, service=service)
        self.providers.append(provider)
        print(f"Added provider: {name}")
    
    def get_next_provider(self) -> Optional[ProviderInfo]:
        if not self.providers:
            return None
            
        # find healthy providers
        healthy_providers = [p for p in self.providers if p.status == ProviderStatus.HEALTHY]
        
        if not healthy_providers:
            # no healthy providers, try degraded ones
            degraded_providers = [p for p in self.providers if p.status == ProviderStatus.DEGRADED]
            if degraded_providers:
                healthy_providers = degraded_providers
            else:
                return None  # no available providers
        
        # round-robin selection
        provider = healthy_providers[self.current_provider_index % len(healthy_providers)]
        self.current_provider_index += 1
        
        return provider
    
    async def health_check_provider(self, provider: ProviderInfo) -> None:
        try:
            start_time = time.perf_counter()
            health_result = await provider.service.health_check()
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            
            # update provider status based on health check
            if health_result.get("status") == "ok":
                provider.status = ProviderStatus.HEALTHY
                provider.consecutive_failures = 0
            else:
                provider.status = ProviderStatus.DEGRADED
                provider.consecutive_failures += 1
                
                # mark as failed if too many consecutive failures
                if provider.consecutive_failures >= provider.max_failures:
                    provider.status = ProviderStatus.FAILED
                    print(f"Provider {provider.name} marked as failed after {provider.consecutive_failures} failures")
            
            # update metrics
            provider.last_health_check = time.time()
            provider.total_latency_ms += latency_ms
            provider.average_latency_ms = provider.total_latency_ms / max(provider.requests_handled, 1)
            
        except Exception as e:
            provider.status = ProviderStatus.FAILED
            provider.consecutive_failures += 1
            print(f"Health check failed for {provider.name}: {e}")
    
    async def health_check_all(self) -> None:
        if time.time() - self.last_health_check < self.health_check_interval:
            return  # skip if too soon
            
        self.last_health_check = time.time()
        
        # check all providers concurrently
        tasks = [self.health_check_provider(provider) for provider in self.providers]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def generate_review(self, prompt: str, **kwargs) -> Dict[str, Any]:
        # ensure health checks are up to date
        await self.health_check_all()
        
        # get next available provider
        provider = self.get_next_provider()
        if not provider:
            raise RuntimeError("No available LLM providers")
        
        try:
            # track request start
            start_time = time.perf_counter()
            provider.requests_handled += 1
            provider.last_request_time = time.time()
            
            # generate review
            result = await provider.service.generate_review(prompt, **kwargs)
            
            # update metrics
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            provider.total_latency_ms += latency_ms
            provider.average_latency_ms = provider.total_latency_ms / provider.requests_handled
            
            # add load balancer metadata
            result["load_balancer"] = {
                "provider_used": provider.name,
                "provider_status": provider.status.value,
                "latency_ms": latency_ms,
                "total_requests": self.total_requests + 1
            }
            
            self.total_requests += 1
            return result
            
        except Exception as e:
            # mark provider as degraded on failure
            provider.consecutive_failures += 1
            if provider.consecutive_failures >= provider.max_failures:
                provider.status = ProviderStatus.FAILED
                print(f"Provider {provider.name} marked as failed after request failure")
            
            # try to get another provider for retry
            fallback_provider = self.get_next_provider()
            if fallback_provider and fallback_provider != provider:
                print(f"Retrying with fallback provider: {fallback_provider.name}")
                return await self.generate_review(prompt, **kwargs)
            else:
                raise e
    
    def get_stats(self) -> Dict[str, Any]:
        healthy_count = sum(1 for p in self.providers if p.status == ProviderStatus.HEALTHY)
        degraded_count = sum(1 for p in self.providers if p.status == ProviderStatus.DEGRADED)
        failed_count = sum(1 for p in self.providers if p.status == ProviderStatus.FAILED)
        
        # calculate distribution percentages
        total_requests = sum(p.requests_handled for p in self.providers)
        distribution = {}
        for provider in self.providers:
            if total_requests > 0:
                percentage = (provider.requests_handled / total_requests) * 100
                distribution[provider.name] = f"{percentage:.1f}%"
            else:
                distribution[provider.name] = "0%"
        
        return {
            "total_requests": self.total_requests,
            "providers": {
                "total": len(self.providers),
                "healthy": healthy_count,
                "degraded": degraded_count,
                "failed": failed_count
            },
            "distribution": distribution,
            "last_health_check": self.last_health_check,
            "current_provider_index": self.current_provider_index
        }
    
    def get_provider_details(self) -> List[Dict[str, Any]]:
        details = []
        for provider in self.providers:
            details.append({
                "name": provider.name,
                "status": provider.status.value,
                "requests_handled": provider.requests_handled,
                "last_request": provider.last_request_time,
                "average_latency_ms": round(provider.average_latency_ms, 2),
                "consecutive_failures": provider.consecutive_failures,
                "last_health_check": provider.last_health_check
            })
        return details

# global singleton instance
_load_balancer_singleton: Optional[LLMLoadBalancer] = None

def get_load_balancer() -> LLMLoadBalancer:
    global _load_balancer_singleton
    if _load_balancer_singleton is None:
        _load_balancer_singleton = LLMLoadBalancer()
        
        # add providers if they're configured
        from app.settings import settings
        
        if settings.is_openai_configured():
            from app.services.llm.openai_service import get_openai_service
            _load_balancer_singleton.add_provider("openai", get_openai_service())
        
        if settings.is_huggingface_configured():
            from app.services.llm.llama_service import get_llama_service
            _load_balancer_singleton.add_provider("huggingface", get_llama_service())
    
    return _load_balancer_singleton