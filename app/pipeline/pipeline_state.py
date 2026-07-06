from __future__ import annotations

from enum import StrEnum


class PipelineStage(StrEnum):
    DISCOVERED = "DISCOVERED"
    TRANSACTIONS_DOWNLOADED = "TRANSACTIONS_DOWNLOADED"
    PORTFOLIO_DOWNLOADED = "PORTFOLIO_DOWNLOADED"
    TOKEN_HISTORY_DOWNLOADED = "TOKEN_HISTORY_DOWNLOADED"
    PROFILE_BUILT = "PROFILE_BUILT"
    BACKTEST_COMPLETED = "BACKTEST_COMPLETED"
    COPY_SCORE_COMPLETED = "COPY_SCORE_COMPLETED"
    REPUTATION_COMPLETED = "REPUTATION_COMPLETED"
    CONVICTION_COMPLETED = "CONVICTION_COMPLETED"
    RANKED = "RANKED"
    REPORT_GENERATED = "REPORT_GENERATED"


class PipelineStatus(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    INSUFFICIENT_PORTFOLIO_DATA = "INSUFFICIENT_PORTFOLIO_DATA"
    INSUFFICIENT_TOKEN_HISTORY = "INSUFFICIENT_TOKEN_HISTORY"
    INSUFFICIENT_BACKTEST_DATA = "INSUFFICIENT_BACKTEST_DATA"
    FAILED = "FAILED"


STAGE_ORDER = tuple(PipelineStage)
STAGE_INDEX = {stage: index for index, stage in enumerate(STAGE_ORDER)}


def normalize_stage(value: str | PipelineStage | None) -> PipelineStage:
    if value is None:
        return PipelineStage.DISCOVERED
    return PipelineStage(str(value))


def stage_at_least(value: str | PipelineStage | None, required: PipelineStage) -> bool:
    return STAGE_INDEX[normalize_stage(value)] >= STAGE_INDEX[required]
