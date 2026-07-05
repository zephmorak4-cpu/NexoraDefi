from __future__ import annotations

from pathlib import Path

from app.intelligence.wallet_report import WalletIntelligenceReport


class WalletPDFRenderer:
    def render(
        self,
        reports: list[WalletIntelligenceReport],
        rankings: list[WalletIntelligenceReport],
        summary: dict[str, object],
        output_path: Path,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "Wallet Intelligence Report",
            "==========================",
            "",
            "Executive Summary",
            f"Wallets analysed: {summary['total_wallets']}",
            f"Average copy performance: {summary['average_copy_performance']}",
            f"Average reputation: {summary['average_reputation']}",
            "",
            "Global Rankings",
        ]
        for index, report in enumerate(rankings, start=1):
            lines.append(
                f"{index}. {report.wallet_address} | copy={report.copy_performance_score:.2f} "
                f"reputation={report.wallet_reputation_score:.2f} risk={report.risk_score:.2f} "
                f"recommendation={report.administrator_recommendation}"
            )
        lines.extend(["", "Individual Wallet Reports"])
        for report in reports:
            lines.extend(
                [
                    "",
                    f"Wallet: {report.wallet_address}",
                    f"Chain: {report.chain}",
                    f"Status: {report.current_status}",
                    f"Trading Style: {report.trading_style}",
                    f"Copy Performance Score: {report.copy_performance_score:.2f}",
                    f"Wallet Reputation Score: {report.wallet_reputation_score:.2f}",
                    f"Historical Accuracy: {report.historical_accuracy:.2f}",
                    f"Risk: {report.risk_classification} ({report.risk_score:.2f})",
                    f"Recommendation: {report.administrator_recommendation}",
                    f"Reasoning: {report.recommendation_reasoning}",
                    f"Summary: {report.executive_summary}",
                ]
            )
        pdf_body = "\\n".join(lines).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content = (
            "%PDF-1.4\n"
            "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
            "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
            f"4 0 obj << /Length {len(pdf_body) + 64} >> stream\n"
            "BT /F1 9 Tf 40 760 Td 11 TL\n"
            f"({pdf_body[:6000]}) Tj\n"
            "ET\nendstream endobj\n"
            "5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
            "xref\n0 6\n0000000000 65535 f \n"
            "trailer << /Root 1 0 R /Size 6 >>\nstartxref\n0\n%%EOF\n"
        )
        output_path.write_text(content, encoding="latin-1")
        return output_path

