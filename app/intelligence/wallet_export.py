from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from app.intelligence.wallet_docx import WalletDocxRenderer
from app.intelligence.wallet_pdf import WalletPDFRenderer
from app.intelligence.wallet_ranking import WalletRankingEngine
from app.intelligence.wallet_report import WalletIntelligenceReport
from app.intelligence.wallet_summary import WalletPortfolioSummary


class WalletReportExporter:
    def export(self, reports: list[WalletIntelligenceReport], output_dir: Path) -> dict[str, object]:
        rankings = WalletRankingEngine().rank(reports)
        summary = WalletPortfolioSummary().build(reports)
        docx_path = WalletDocxRenderer().render(
            reports,
            rankings,
            summary,
            output_dir / "Wallet Intelligence Report.docx",
        )
        pdf_path = WalletPDFRenderer().render(
            reports,
            rankings,
            summary,
            output_dir / "Wallet Intelligence Report.pdf",
        )
        return {
            "reports": [asdict(report) for report in reports],
            "rankings": [asdict(report) for report in rankings],
            "summary": summary,
            "docx_path": str(docx_path),
            "pdf_path": str(pdf_path),
        }
