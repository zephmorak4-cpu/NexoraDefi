from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings


@dataclass(frozen=True)
class ProviderResult:
    content: str
    provider: str
    model: str


class AnalystProvider(Protocol):
    async def generate(self, prompt: str, fallback_content: str) -> ProviderResult:
        ...


class TemplateProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate(self, prompt: str, fallback_content: str) -> ProviderResult:
        return ProviderResult(content=fallback_content, provider="template", model=self.settings.analyst_model)


class OllamaProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate(self, prompt: str, fallback_content: str) -> ProviderResult:
        async with httpx.AsyncClient(timeout=self.settings.http_timeout_seconds) as client:
            response = await client.post(
                f"{self.settings.analyst_base_url.rstrip('/')}/api/generate",
                json={"model": self.settings.analyst_model, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            payload = response.json()
        return ProviderResult(content=payload.get("response") or fallback_content, provider="ollama", model=self.settings.analyst_model)


class OpenAICompatibleProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate(self, prompt: str, fallback_content: str) -> ProviderResult:
        headers = {"Authorization": f"Bearer {self.settings.analyst_api_key}"} if self.settings.analyst_api_key else {}
        async with httpx.AsyncClient(timeout=self.settings.http_timeout_seconds) as client:
            response = await client.post(
                f"{self.settings.analyst_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json={
                    "model": self.settings.analyst_model,
                    "messages": [
                        {"role": "system", "content": "Use only provided structured evidence."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0,
                },
            )
            response.raise_for_status()
            payload = response.json()
        content = payload.get("choices", [{}])[0].get("message", {}).get("content") or fallback_content
        return ProviderResult(content=content, provider="openai_compatible", model=self.settings.analyst_model)


class OpenAIProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate(self, prompt: str, fallback_content: str) -> ProviderResult:
        headers = {"Authorization": f"Bearer {self.settings.openai_api_key}"}
        async with httpx.AsyncClient(timeout=self.settings.http_timeout_seconds) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json={
                    "model": self.settings.analyst_model,
                    "messages": [
                        {"role": "system", "content": "Use only provided structured evidence. Do not invent facts."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0,
                },
            )
            response.raise_for_status()
            payload = response.json()
        content = payload.get("choices", [{}])[0].get("message", {}).get("content") or fallback_content
        return ProviderResult(content=content, provider="openai", model=self.settings.analyst_model)


def build_provider(settings: Settings) -> AnalystProvider:
    if settings.analyst_provider == "ollama":
        return OllamaProvider(settings)
    if settings.analyst_provider == "openai":
        return OpenAIProvider(settings)
    if settings.analyst_provider == "openai_compatible":
        return OpenAICompatibleProvider(settings)
    return TemplateProvider(settings)
