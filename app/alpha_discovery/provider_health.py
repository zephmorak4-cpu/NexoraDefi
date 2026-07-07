from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ProviderStatus:
    name: str
    status: str = "ONLINE"
    failures: int = 0
    last_error: str | None = None


class ProviderHealthService:
    def __init__(self, failure_threshold: int = 2) -> None:
        self.failure_threshold = failure_threshold
        self._providers: dict[str, ProviderStatus] = {}

    def success(self, provider: str) -> None:
        status = self._providers.setdefault(provider, ProviderStatus(name=provider))
        status.failures = 0
        status.status = "ONLINE"
        status.last_error = None

    def failure(self, provider: str, error: str | None = None) -> None:
        status = self._providers.setdefault(provider, ProviderStatus(name=provider))
        status.failures += 1
        status.last_error = error
        status.status = "DEGRADED" if status.failures < self.failure_threshold else "OFFLINE"
        logger.warning(
            "alpha_provider_health_failure",
            provider=provider,
            status=status.status,
            failures=status.failures,
            error=error,
        )

    def snapshot(self) -> dict[str, dict[str, object]]:
        return {
            provider: {"status": status.status, "failures": status.failures, "last_error": status.last_error}
            for provider, status in self._providers.items()
        }
