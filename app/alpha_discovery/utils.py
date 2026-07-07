from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.core.logging import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


async def safe_api_call(stage: str, call: Callable[[], Awaitable[T]], default: T) -> T:
    try:
        return await call()
    except Exception as exc:
        logger.warning("alpha_safe_api_call_failed", stage=stage, error=type(exc).__name__)
        return default


def number(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
