from __future__ import annotations

from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class AIProviderStatus:
    provider: str
    configured: bool


class AIAssistanceService:
    """Non-blocking AI provider registry for generation/evaluation operations.

    The platform can be run without any AI key. When keys are provided, the
    selected provider can later be used by generation, remediation or benchmark
    explanation services. Perplexity is included as a first-class provider.
    """

    SUPPORTED_PROVIDERS = ("openai", "anthropic", "gemini", "perplexity")

    def provider_statuses(self) -> dict[str, bool]:
        return {
            "openai": bool(settings.openai_api_key),
            "anthropic": bool(settings.anthropic_api_key),
            "gemini": bool(settings.gemini_api_key),
            "perplexity": bool(settings.perplexity_api_key),
        }

    def selected_provider(self) -> AIProviderStatus:
        provider = (settings.ai_provider or "none").lower()
        statuses = self.provider_statuses()
        if provider == "none":
            return AIProviderStatus(provider="none", configured=False)
        if provider not in self.SUPPORTED_PROVIDERS:
            return AIProviderStatus(provider=provider, configured=False)
        return AIProviderStatus(provider=provider, configured=statuses.get(provider, False))

    def describe(self) -> dict:
        selected = self.selected_provider()
        return {
            "selected_provider": selected.provider,
            "selected_provider_configured": selected.configured,
            "available_providers": self.provider_statuses(),
            "non_blocking": True,
            "note": "Generation and benchmark operations must continue when AI keys are empty.",
        }
