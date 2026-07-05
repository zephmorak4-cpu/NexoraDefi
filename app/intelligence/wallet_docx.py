from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from app.intelligence.wallet_report import WalletIntelligenceReport


class WalletDocxRenderer:
    def render(
        self,
        reports: list[WalletIntelligenceReport],
        rankings: list[WalletIntelligenceReport],
        summary: dict[str, object],
        output_path: Path,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        document_xml = self._document_xml(reports, rankings, summary)
        with ZipFile(output_path, "w", ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", self._content_types())
            archive.writestr("_rels/.rels", self._rels())
            archive.writestr("word/_rels/document.xml.rels", self._document_rels())
            archive.writestr("word/styles.xml", self._styles())
            archive.writestr("word/document.xml", document_xml)
        return output_path

    def _document_xml(
        self,
        reports: list[WalletIntelligenceReport],
        rankings: list[WalletIntelligenceReport],
        summary: dict[str, object],
    ) -> str:
        body: list[str] = []
        body.append(self._paragraph("Wallet Intelligence Report", style="Title"))
        body.append(self._paragraph("Administrator review document for discovered candidate wallets.", style="Subtitle"))
        body.append(self._heading("Executive Summary", 1))
        for label, value in (
            ("Total Wallets Analysed", summary["total_wallets"]),
            ("Average Copy Performance", summary["average_copy_performance"]),
            ("Average Reputation", summary["average_reputation"]),
            ("Average Historical Accuracy", summary["average_historical_accuracy"]),
            ("Average Risk Drawdown", summary["average_drawdown"]),
        ):
            body.append(self._paragraph(f"{label}: {value}"))
        body.append(self._paragraph("Important: candidate wallets are not approved for Smart Money alerts until an administrator manually approves them."))

        body.append(self._heading("Global Rankings", 1))
        for index, report in enumerate(rankings, start=1):
            body.append(
                self._paragraph(
                    f"{index}. Candidate Wallet Address: {report.wallet_address} | "
                    f"Copy Performance: {report.copy_performance_score:.2f}/100 | "
                    f"Reputation: {report.wallet_reputation_score:.2f}/100 | "
                    f"Risk: {report.risk_classification} ({report.risk_score:.2f}/100) | "
                    f"Recommendation: {report.administrator_recommendation}"
                )
            )

        body.append(self._heading("Individual Wallet Profiles", 1))
        for index, report in enumerate(rankings, start=1):
            body.extend(self._wallet_profile(index, report))

        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{''.join(body)}"
            '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>'
            "</w:body></w:document>"
        )

    def _wallet_profile(self, index: int, report: WalletIntelligenceReport) -> list[str]:
        rows: list[str] = [
            self._heading(f"Wallet {index}: {report.wallet_address}", 2),
            self._heading("1. Wallet Identity", 3),
            self._kv("Wallet Address", report.wallet_address),
            self._kv("Address Type", "Solana candidate wallet address"),
            self._kv("Chain", report.chain),
            self._kv("Current Status", report.current_status),
            self._kv("Wallet Age", f"{report.wallet_age_days} days"),
            self._kv("Current Portfolio Value Estimate", f"${report.current_portfolio_value:.2f}"),
            self._kv("Review Status", report.review_status),
            self._kv("Approved For Signals", "Yes" if report.approved_for_signals else "No"),
            self._heading("2. Trading Behaviour", 3),
            self._kv("Total Trades Observed", report.total_trades),
            self._kv("Average Trades Per Day", f"{report.average_trades_per_day:.2f}"),
            self._kv("Average Trades Per Week", f"{report.average_trades_per_week:.2f}"),
            self._kv("Average Trades Per Month", f"{report.average_trades_per_month:.2f}"),
            self._kv("Average Buy Size", f"${report.average_buy_size:.2f}"),
            self._kv("Average Sell Size", f"${report.average_sell_size:.2f}"),
            self._kv("Largest Buy", f"${report.largest_buy:.2f}"),
            self._kv("Largest Sell", f"${report.largest_sell:.2f}"),
            self._heading("3. Holding Behaviour", 3),
            self._kv("Average Holding Time", f"{report.average_holding_time_days:.2f} days"),
            self._kv("Median Holding Time", f"{report.median_holding_time_days:.2f} days"),
            self._kv("Longest Hold", f"{report.longest_hold_days:.2f} days"),
            self._kv("Shortest Hold", f"{report.shortest_hold_days:.2f} days"),
            self._kv("Held Less Than 24 Hours", f"{report.held_less_than_24h_percentage:.2f}%"),
            self._kv("Held More Than 30 Days", f"{report.held_more_than_30d_percentage:.2f}%"),
            self._heading("4. Trading Style Classification", 3),
            self._kv("Classification", report.trading_style),
            self._paragraph(report.trading_style_explanation),
            self._heading("5. Copy Performance Simulation", 3),
            self._kv("Copy Performance Score", f"{report.copy_performance_score:.2f}/100"),
            self._kv("Average ROI", f"{report.average_roi:.2f}%"),
            self._kv("Median ROI", f"{report.median_roi:.2f}%"),
            self._kv("Total ROI", f"{report.total_roi:.2f}%"),
            self._kv("Maximum Drawdown", f"{report.maximum_drawdown:.2f}%"),
            self._kv("Profit Factor", f"{report.profit_factor:.2f}"),
            self._kv("Sharpe Ratio", f"{report.sharpe_ratio:.2f}"),
            self._kv("Consistency", f"{report.consistency:.2f}/100"),
            self._heading("6. Wallet Reputation", 3),
            self._kv("Wallet Reputation Score", f"{report.wallet_reputation_score:.2f}/100"),
            self._kv("Historical Accuracy", f"{report.historical_accuracy:.2f}/100"),
            self._kv("Reputation Explanation", "Score is based on observed candidate history and will improve as more evidence is collected."),
            self._heading("7. Conviction Analysis", 3),
            self._kv("Conviction Score", f"{report.conviction_score:.2f}/100"),
            self._kv("Explanation", "Conviction reflects observed activity, repeat token interactions, and candidate score. It is not approval."),
            self._heading("8. Token Preferences", 3),
            self._paragraph(str(report.token_preferences)),
            self._heading("9. Risk Analysis", 3),
            self._kv("Risk Classification", report.risk_classification),
            self._kv("Risk Score", f"{report.risk_score:.2f}/100"),
            self._paragraph("Higher risk score means lower observed risk. Limited history can still make a wallet unsuitable for approval."),
            self._heading("10. AI Executive Summary", 3),
            self._paragraph(report.executive_summary),
            self._heading("11. Administrator Recommendation", 3),
            self._kv("Recommendation", report.administrator_recommendation),
            self._paragraph(report.recommendation_reasoning),
            self._paragraph("Manual approval is required before this wallet can generate Smart Money alerts."),
            self._page_break(),
        ]
        return rows

    def _kv(self, label: str, value: object) -> str:
        return self._paragraph(f"{label}: {value}")

    @staticmethod
    def _paragraph(text: str, style: str | None = None) -> str:
        style_xml = f'<w:pStyle w:val="{style}"/>' if style else ""
        return f"<w:p><w:pPr>{style_xml}</w:pPr><w:r><w:t>{escape(str(text))}</w:t></w:r></w:p>"

    def _heading(self, text: str, level: int) -> str:
        return self._paragraph(text, style=f"Heading{level}")

    @staticmethod
    def _page_break() -> str:
        return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'

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
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
        )

    @staticmethod
    def _styles() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:sz w:val="22"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:b/><w:sz w:val="40"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:rPr><w:i/><w:sz w:val="24"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>'
            "</w:styles>"
        )
