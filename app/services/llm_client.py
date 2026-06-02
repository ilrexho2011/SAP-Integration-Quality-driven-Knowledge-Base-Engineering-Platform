from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.config import settings

# Default models per provider. These are intentionally conservative, widely
# available models. They can be overridden per call via generate(model=...).
DEFAULT_MODELS = {
    "anthropic": "claude-3-5-haiku-latest",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
    "perplexity": "sonar",
}

# Network/token budget guardrails. Knowledge-section enrichment is small by design.
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_TOKENS = 700


@dataclass
class LLMResult:
    """Outcome of a single LLM call.

    `ok` is True only when a non-empty completion was returned. On any failure
    (`ok=False`) the caller must fall back to deterministic template content.
    The error string is safe to record in a manifest (no secrets, no payload).
    """

    ok: bool
    text: str = ""
    provider: str = "none"
    model: str = ""
    error: str = ""


class LLMClient:
    """Minimal, dependency-free, non-blocking LLM client.

    Design constraints (see SAP-PI/CPI & PDEV & DAI-Engine skill, Route C/D):
      * Non-blocking: the platform must run with no AI key. When the selected
        provider is "none" or unconfigured, `is_enabled()` is False and callers
        keep using deterministic templates.
      * No secrets in code: API keys are read from `settings` (which loads them
        from the environment / .env). Keys are never logged or returned.
      * Stdlib only: uses urllib so no new runtime dependency is introduced.
      * Fail safe: any network, auth, quota, or parsing error returns
        `LLMResult(ok=False, ...)` rather than raising, so generation never
        breaks because of AI.
    """

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.provider = (provider or settings.ai_provider or "none").strip().lower()
        self.model = (
            model or (settings.ai_model or "").strip() or DEFAULT_MODELS.get(self.provider, "")
        )
        self.timeout_seconds = timeout_seconds

    # --- capability checks -------------------------------------------------

    def _api_key(self) -> str:
        return {
            "openai": settings.openai_api_key,
            "anthropic": settings.anthropic_api_key,
            "gemini": settings.gemini_api_key,
            "perplexity": settings.perplexity_api_key,
        }.get(self.provider, "")

    def is_enabled(self) -> bool:
        """True only when a supported provider is selected and has a key."""
        return self.provider in DEFAULT_MODELS and bool(self._api_key())

    def describe(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "enabled": self.is_enabled(),
        }

    # --- public API --------------------------------------------------------

    def complete(
        self, system_prompt: str, user_prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> LLMResult:
        """Return a completion, or LLMResult(ok=False) on any failure."""
        if not self.is_enabled():
            return LLMResult(
                ok=False, provider=self.provider, model=self.model, error="provider not configured"
            )
        try:
            if self.provider == "anthropic":
                return self._complete_anthropic(system_prompt, user_prompt, max_tokens)
            if self.provider == "openai":
                return self._complete_openai_chat(
                    system_prompt,
                    user_prompt,
                    max_tokens,
                    base_url="https://api.openai.com/v1/chat/completions",
                )
            if self.provider == "perplexity":
                return self._complete_openai_chat(
                    system_prompt,
                    user_prompt,
                    max_tokens,
                    base_url="https://api.perplexity.ai/chat/completions",
                )
            if self.provider == "gemini":
                return self._complete_gemini(system_prompt, user_prompt, max_tokens)
        except urllib.error.HTTPError as exc:
            return LLMResult(
                ok=False, provider=self.provider, model=self.model, error=f"http_error {exc.code}"
            )
        except urllib.error.URLError as exc:
            return LLMResult(
                ok=False, provider=self.provider, model=self.model, error=f"url_error {exc.reason}"
            )
        except (TimeoutError, OSError) as exc:
            return LLMResult(
                ok=False,
                provider=self.provider,
                model=self.model,
                error=f"network_error {exc.__class__.__name__}",
            )
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            return LLMResult(
                ok=False,
                provider=self.provider,
                model=self.model,
                error=f"parse_error {exc.__class__.__name__}",
            )
        return LLMResult(
            ok=False, provider=self.provider, model=self.model, error="unsupported provider"
        )

    # --- transport helpers -------------------------------------------------

    def _post_json(
        self, url: str, headers: dict[str, str], payload: dict[str, Any]
    ) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json", **headers}, method="POST"
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _complete_anthropic(
        self, system_prompt: str, user_prompt: str, max_tokens: int
    ) -> LLMResult:
        body = self._post_json(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": self._api_key(), "anthropic-version": "2023-06-01"},
            {
                "model": self.model,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
        )
        parts = [
            block.get("text", "")
            for block in body.get("content", [])
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        text = "\n".join(p for p in parts if p).strip()
        return self._as_result(text)

    def _complete_openai_chat(
        self, system_prompt: str, user_prompt: str, max_tokens: int, base_url: str
    ) -> LLMResult:
        body = self._post_json(
            base_url,
            {"Authorization": f"Bearer {self._api_key()}"},
            {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        choices = body.get("choices", [])
        text = (choices[0]["message"]["content"] if choices else "").strip()
        return self._as_result(text)

    def _complete_gemini(self, system_prompt: str, user_prompt: str, max_tokens: int) -> LLMResult:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self._api_key()}"
        body = self._post_json(
            url,
            {},
            {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {"maxOutputTokens": max_tokens},
            },
        )
        candidates = body.get("candidates", [])
        text = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "\n".join(
                part.get("text", "") for part in parts if isinstance(part, dict)
            ).strip()
        return self._as_result(text)

    def _as_result(self, text: str) -> LLMResult:
        if not text:
            return LLMResult(
                ok=False, provider=self.provider, model=self.model, error="empty_completion"
            )
        return LLMResult(ok=True, text=text, provider=self.provider, model=self.model)
