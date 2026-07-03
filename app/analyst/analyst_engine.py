from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyst.explanation_engine import ExplanationEngine, assert_safe_language
from app.analyst.prompt_builder import PromptBuilder
from app.analyst.providers import build_provider
from app.analyst.template_engine import AnalystReport, TemplateEngine
from app.core.config import Settings
from app.models import MomentumMetric, RiskEvent, SmartMoneySignal, Token, TokenGrowthMetric, TokenRiskMetric


class AnalystEngine:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.prompts = PromptBuilder()
        self.templates = TemplateEngine()
        self.explanations = ExplanationEngine()
        self.provider = build_provider(settings)

    async def token_report(
        self, token_id: int, output_format: str | None = None, language: str | None = None
    ) -> AnalystReport:
        evidence = await self.token_evidence(token_id)
        sections = self.explanations.token_sections(evidence)
        return await self._render("smart_money_alert", sections, evidence, output_format, language)

    async def watchlist_reports(self, limit: int = 20, output_format: str | None = None) -> list[AnalystReport]:
        latest_ids = select(func.max(SmartMoneySignal.id)).group_by(SmartMoneySignal.token_id)
        signals = list(
            (
                await self.session.scalars(
                    select(SmartMoneySignal)
                    .where(SmartMoneySignal.id.in_(latest_ids))
                    .order_by(SmartMoneySignal.signal_strength.desc(), SmartMoneySignal.id.desc())
                    .limit(limit)
                )
            ).all()
        )
        reports = []
        for signal in signals:
            evidence = await self.token_evidence(signal.token_id)
            sections = self.explanations.token_sections(evidence)
            reports.append(await self._render("smart_money_alert", sections, evidence, output_format, None))
        return reports

    async def smart_money_report(self, output_format: str | None = None, limit: int = 20) -> AnalystReport:
        signals = list(
            (
                await self.session.scalars(
                    select(SmartMoneySignal)
                    .order_by(SmartMoneySignal.created_at.desc(), SmartMoneySignal.id.desc())
                    .limit(limit)
                )
            ).all()
        )
        evidence = {
            "smart_money_signals": [self._row(signal) for signal in signals],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        sections = self.explanations.smart_money_sections(evidence)
        return await self._render("smart_money_summary", sections, evidence, output_format, None)

    async def token_evidence(self, token_id: int) -> dict:
        token = await self.session.get(Token, token_id)
        if token is None:
            raise ValueError("token not found")
        latest = {
            "risk": await self._latest(TokenRiskMetric, token_id),
            "growth": await self._latest(TokenGrowthMetric, token_id),
            "momentum": await self._latest(MomentumMetric, token_id),
            "smart_money_signal": await self._latest(SmartMoneySignal, token_id),
        }
        smart_money_signals = list(
            (
                await self.session.scalars(
                    select(SmartMoneySignal)
                    .where(SmartMoneySignal.token_id == token_id)
                    .order_by(SmartMoneySignal.created_at.desc(), SmartMoneySignal.id.desc())
                    .limit(5)
                )
            ).all()
        )
        risk_events = list(
            (
                await self.session.scalars(
                    select(RiskEvent)
                    .where(RiskEvent.token_id == token_id)
                    .order_by(RiskEvent.created_at.desc(), RiskEvent.id.desc())
                    .limit(5)
                )
            ).all()
        )
        return {
            "token": self._row(token),
            "latest_smart_money_signal": self._row(latest["smart_money_signal"]),
            "smart_money_signals": [self._row(row) for row in smart_money_signals],
            "risk": self._row(latest["risk"]),
            "growth": self._row(latest["growth"]),
            "momentum": self._row(latest["momentum"]),
            "risk_events": [self._row(row) for row in risk_events],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _render(
        self,
        report_type: str,
        sections: dict,
        evidence: dict,
        output_format: str | None,
        language: str | None,
    ) -> AnalystReport:
        fmt = output_format or self.settings.analyst_default_format
        lang = language or self.settings.analyst_default_language
        fallback = self.templates.render(report_type, sections, fmt, lang)
        prompt = self.prompts.build(report_type, evidence, lang)
        result = await self.provider.generate(prompt, fallback.content)
        assert_safe_language(result.content)
        return AnalystReport(report_type=report_type, format=fmt, language=lang, content=result.content, evidence=evidence)

    async def _latest(self, model, token_id: int):
        return await self.session.scalar(select(model).where(model.token_id == token_id).order_by(model.id.desc()).limit(1))

    @staticmethod
    def _row(row) -> dict:
        if row is None:
            return {}
        payload = {}
        for key, value in row.__dict__.items():
            if key.startswith("_"):
                continue
            payload[key] = value
        return payload
