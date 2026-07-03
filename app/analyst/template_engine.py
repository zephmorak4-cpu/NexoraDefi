from __future__ import annotations

from dataclasses import dataclass

MANDATORY_SECTIONS = (
    "Token",
    "Wallet Activity",
    "Why It Matters",
    "Risk Summary",
    "Confidence Score",
    "Suggested Action",
)


@dataclass(frozen=True)
class AnalystReport:
    report_type: str
    format: str
    language: str
    content: str
    evidence: dict


class TemplateEngine:
    def render(
        self,
        report_type: str,
        sections: dict[str, str | list[str]],
        output_format: str = "markdown",
        language: str = "en",
    ) -> AnalystReport:
        missing = [section for section in MANDATORY_SECTIONS if section not in sections]
        if missing:
            raise ValueError(f"missing analyst report sections: {', '.join(missing)}")
        if language != "en":
            raise ValueError("only English analyst templates are currently supported")
        if output_format == "telegram":
            content = self._telegram(sections)
        elif output_format == "plain":
            content = self._plain(sections)
        else:
            content = self._markdown(sections)
        return AnalystReport(report_type=report_type, format=output_format, language=language, content=content, evidence={})

    @staticmethod
    def _markdown(sections: dict[str, str | list[str]]) -> str:
        parts = []
        for section in MANDATORY_SECTIONS:
            body = sections[section]
            if isinstance(body, list):
                body = "\n".join(f"- {item}" for item in body) if body else "- None observed in structured evidence."
            parts.append(f"## {section}\n{body}")
        return "\n\n".join(parts)

    @staticmethod
    def _plain(sections: dict[str, str | list[str]]) -> str:
        parts = []
        for section in MANDATORY_SECTIONS:
            body = sections[section]
            if isinstance(body, list):
                body = "\n".join(f"* {item}" for item in body) if body else "* None observed in structured evidence."
            parts.append(f"{section}\n{body}")
        return "\n\n".join(parts)

    @staticmethod
    def _telegram(sections: dict[str, str | list[str]]) -> str:
        parts = []
        for section in MANDATORY_SECTIONS:
            body = sections[section]
            if isinstance(body, list):
                body = "\n".join(f"- {item}" for item in body) if body else "- None observed in structured evidence."
            parts.append(f"*{section}*\n{body}")
        return "\n\n".join(parts)
