"""Market Context Intelligence acceptance checks.

This module documents the production requirements covered by automated tests:
- reconstructed positions receive market context rows
- unavailable market metrics remain null instead of being invented
- consensus and context scores are derived from stored evidence
- position intelligence reports expose market context summaries
"""
