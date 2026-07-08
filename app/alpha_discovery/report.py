from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AlphaAlertHistory, AlphaScannedToken, AlphaWatchlistToken


class AlphaDiscoveryReportExporter:
    async def export(self, session: AsyncSession, output_dir: Path, limit: int = 100) -> dict[str, Any]:
        rows = list(
            (
                await session.scalars(
                    select(AlphaScannedToken)
                    .order_by(desc(AlphaScannedToken.final_score), desc(AlphaScannedToken.last_seen_at))
                    .limit(limit)
                )
            ).all()
        )
        watchlist = list(
            (
                await session.scalars(
                    select(AlphaWatchlistToken)
                    .order_by(desc(AlphaWatchlistToken.final_score), desc(AlphaWatchlistToken.created_at))
                    .limit(limit)
                )
            ).all()
        )
        alerts = list(
            (
                await session.scalars(
                    select(AlphaAlertHistory)
                    .order_by(desc(AlphaAlertHistory.created_at))
                    .limit(limit)
                )
            ).all()
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        docx_path = self._render_docx(rows, watchlist, alerts, output_dir / "Solana Alpha Discovery Report.docx")
        pdf_path = self._render_pdf(rows, watchlist, alerts, output_dir / "Solana Alpha Discovery Report.pdf")
        return {
            "summary": self._summary(rows, watchlist, alerts),
            "docx_path": str(docx_path),
            "pdf_path": str(pdf_path),
            "tokens": len(rows),
            "watchlist": len(watchlist),
            "alerts": len(alerts),
        }

    @staticmethod
    def _summary(rows: list[AlphaScannedToken], watchlist: list[AlphaWatchlistToken], alerts: list[AlphaAlertHistory]) -> dict[str, Any]:
        alert_count = sum(1 for row in rows if row.should_alert)
        rejected_count = sum(1 for row in rows if row.decision == "IGNORE")
        return {
            "tokens_reviewed": len(rows),
            "alpha_alerts": alert_count,
            "watchlist_tokens": len(watchlist),
            "rejected_tokens": rejected_count,
            "telegram_alert_records": len(alerts),
            "mode": "alert_only_manual_review_required",
        }

    def _render_docx(
        self,
        rows: list[AlphaScannedToken],
        watchlist: list[AlphaWatchlistToken],
        alerts: list[AlphaAlertHistory],
        output_path: Path,
    ) -> Path:
        body: list[str] = []
        body.append(self._paragraph("Solana Alpha Discovery Report", "Title"))
        body.append(self._paragraph("Alert-only token intelligence report for manual review.", "Subtitle"))
        body.append(self._heading("Executive Summary"))
        summary = self._summary(rows, watchlist, alerts)
        for key, value in summary.items():
            body.append(self._paragraph(f"{key.replace('_', ' ').title()}: {value}"))
        body.append(
            self._paragraph(
                "Important: this system does not buy, sell, place orders, or handle private keys. It only reports evidence."
            )
        )
        body.append(self._heading("Ranked Token Profiles"))
        for index, row in enumerate(rows, start=1):
            body.extend(self._token_profile(index, row))
        body.append(self._heading("Watchlist"))
        if not watchlist:
            body.append(self._paragraph("No watchlist tokens currently meet the configured watch threshold."))
        for index, row in enumerate(watchlist, start=1):
            body.append(
                self._paragraph(
                    f"{index}. Token Address: {row.token_address} | Score: {float(row.final_score):.2f}/100 | "
                    f"Decision: {row.decision} | Reason: {'; '.join(row.reasons[:4])}"
                )
            )
        xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{''.join(body)}"
            '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>'
            "</w:body></w:document>"
        )
        with ZipFile(output_path, "w", ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", self._content_types())
            archive.writestr("_rels/.rels", self._rels())
            archive.writestr("word/_rels/document.xml.rels", self._document_rels())
            archive.writestr("word/styles.xml", self._styles())
            archive.writestr("word/document.xml", xml)
        return output_path

    def _render_pdf(
        self,
        rows: list[AlphaScannedToken],
        watchlist: list[AlphaWatchlistToken],
        alerts: list[AlphaAlertHistory],
        output_path: Path,
    ) -> Path:
        lines = [
            "Solana Alpha Discovery Report",
            "================================",
            "Alert-only token intelligence report for manual review.",
            "",
            "Executive Summary",
        ]
        for key, value in self._summary(rows, watchlist, alerts).items():
            lines.append(f"{key.replace('_', ' ').title()}: {value}")
        lines.extend(["", "Ranked Token Profiles"])
        for index, row in enumerate(rows[:60], start=1):
            lines.extend(self._token_lines(index, row))
        lines.extend(["", "Watchlist"])
        if not watchlist:
            lines.append("No watchlist tokens currently meet the configured watch threshold.")
        for index, row in enumerate(watchlist[:30], start=1):
            lines.append(f"{index}. Token Address: {row.token_address} | Score: {float(row.final_score):.2f}/100 | {row.decision}")
        pdf_body = "\\n".join(lines).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content = (
            "%PDF-1.4\n"
            "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
            "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
            f"4 0 obj << /Length {len(pdf_body) + 64} >> stream\n"
            "BT /F1 8 Tf 40 760 Td 10 TL\n"
            f"({pdf_body[:9000]}) Tj\n"
            "ET\nendstream endobj\n"
            "5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
            "xref\n0 6\n0000000000 65535 f \n"
            "trailer << /Root 1 0 R /Size 6 >>\nstartxref\n0\n%%EOF\n"
        )
        output_path.write_text(content, encoding="latin-1")
        return output_path

    def _token_profile(self, index: int, row: AlphaScannedToken) -> list[str]:
        return [self._paragraph(line) for line in self._token_lines(index, row)]

    @staticmethod
    def _token_lines(index: int, row: AlphaScannedToken) -> list[str]:
        reasons = "; ".join((row.rejection_reasons or [])[:5]) or "No reasons recorded."
        scores = row.agent_scores or {}
        return [
            "",
            f"{index}. Token: {row.symbol or 'UNKNOWN'} - {row.name or 'Unknown'}",
            f"Token Address: {row.token_address}",
            f"Pair Address: {row.pair_address or 'unknown'}",
            f"DEX: {row.dex or 'unknown'} | Source: {row.source}",
            f"Score: {float(row.final_score):.2f}/100 | Decision: {row.decision} | Alert Sent: {row.should_alert}",
            f"Liquidity: ${float(row.liquidity_usd or 0):,.2f} | Market Cap: ${float(row.market_cap_usd or 0):,.2f} | Volume: ${float(row.volume_usd or 0):,.2f}",
            f"Buys/Sells: {row.buys}/{row.sells}",
            f"Agent Scores: launch={scores.get('launch_quality', 'n/a')}, developer={scores.get('developer_reputation', 'n/a')}, smart_money={scores.get('smart_money', 'n/a')}, momentum={scores.get('momentum', 'n/a')}, risk={scores.get('risk', 'n/a')}",
            f"Why: {reasons}",
        ]

    @staticmethod
    def _paragraph(text: str, style: str | None = None) -> str:
        style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        return f"<w:p>{style_xml}<w:r><w:t>{escape(text)}</w:t></w:r></w:p>"

    def _heading(self, text: str) -> str:
        return self._paragraph(text, "Heading1")

    @staticmethod
    def _content_types() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            "</Types>"
        )

    @staticmethod
    def _rels() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>"
        )

    @staticmethod
    def _document_rels() -> str:
        return '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'

    @staticmethod
    def _styles() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/></w:style>'
            '<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>'
            "</w:styles>"
        )


def build_alpha_report_message(export: dict[str, Any]) -> str:
    summary = export["summary"]
    return "\n".join(
        [
            "*Solana Alpha Discovery Report Ready*",
            "",
            f"Tokens Reviewed: {summary['tokens_reviewed']}",
            f"Alpha Alerts: {summary['alpha_alerts']}",
            f"Watchlist Tokens: {summary['watchlist_tokens']}",
            f"Rejected Tokens: {summary['rejected_tokens']}",
            "",
            "Mode: Alert only. Manual review required. No auto-buying or auto-selling.",
        ]
    )


def build_watchlist_digest(watchlist: list[AlphaWatchlistToken]) -> str:
    lines = ["*Solana Alpha Watchlist Digest*", "", "These are watchlist tokens, not buy instructions."]
    if not watchlist:
        lines.append("No watchlist tokens currently meet the configured threshold.")
        return "\n".join(lines)
    for index, row in enumerate(watchlist, start=1):
        main_issue = next(
            (reason for reason in row.reasons if "smart" in reason.lower() or "liquidity" in reason.lower()),
            row.reasons[0] if row.reasons else "No issue recorded",
        )
        lines.append("")
        lines.append(f"{index}. Token: UNKNOWN")
        lines.append(f"Address: {row.token_address}")
        lines.append(f"Score: {float(row.final_score):.2f}/100")
        lines.append(f"Decision: {row.decision}")
        lines.append(f"Main issue: {main_issue}")
        lines.append("Why:")
        lines.extend(f"- {reason}" for reason in row.reasons[:5])
    return "\n".join(lines)
