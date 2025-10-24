"""
Institutional Ownership Handler - Institutional investor holdings.

Shows institutional ownership data:
- % owned by institutions
- Top institutional holders
- Recent changes in holdings
- Ownership concentration

Data source: sb.institutional_ownership (expected table)
"""

from datetime import date
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class InstitutionalOwnershipHandler(BaseCardHandler):
    """Handler for ticker_institutional card - institutional ownership analysis."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        if not symbol:
            raise HTTPException(400, "Symbol required for ticker_institutional")

        # Fetch latest institutional holdings
        holdings_query = """
            SELECT
                report_date,
                institution_name,
                shares_held,
                pct_of_shares,
                change_in_shares,
                change_pct
            FROM sb.institutional_ownership
            WHERE symbol = $1 AND report_date <= $2
            ORDER BY report_date DESC, shares_held DESC
            LIMIT 20
        """

        # Aggregate summary
        summary_query = """
            SELECT
                report_date,
                SUM(shares_held) as total_institutional_shares,
                COUNT(DISTINCT institution_name) as institution_count
            FROM sb.institutional_ownership
            WHERE symbol = $1 AND report_date <= $2
            GROUP BY report_date
            ORDER BY report_date DESC
            LIMIT 1
        """

        holdings = await self._fetch_all(holdings_query, {"symbol": symbol, "report_date": trading_date})
        summary = await self._fetch_one(summary_query, {"symbol": symbol, "report_date": trading_date})

        if not holdings and not summary:
            raise HTTPException(404, f"No institutional data for {symbol}")

        latest_report_date = holdings[0]["report_date"] if holdings else summary["report_date"]

        # Calculate metrics
        total_pct = sum(float(h["pct_of_shares"]) for h in holdings if h.get("pct_of_shares")) if holdings else 0
        increasing = sum(1 for h in holdings if h.get("change_in_shares") and float(h["change_in_shares"]) > 0)
        decreasing = sum(1 for h in holdings if h.get("change_in_shares") and float(h["change_in_shares"]) < 0)

        if mode == CardMode.beginner:
            return {
                "symbol": symbol,
                "institutional_ownership_pct": round(total_pct, 1),
                "ownership_level": "High" if total_pct > 70 else "Moderate" if total_pct > 40 else "Low",
                "top_holders": [
                    {"name": h["institution_name"], "shares_pct": round(float(h["pct_of_shares"]), 2)}
                    for h in holdings[:5]
                ],
                "recent_trend": "Increasing" if increasing > decreasing else "Decreasing" if decreasing > increasing else "Stable",
                "what_it_means": f"{total_pct:.0f}% owned by institutions (mutual funds, hedge funds). High ownership = professional confidence.",
                "educational_tip": "Institutional ownership shows how many 'smart money' investors own the stock. High ownership often means good fundamentals.",
                "report_date": str(latest_report_date),
            }
        elif mode == CardMode.intermediate:
            return {
                "symbol": symbol,
                "ownership_metrics": {
                    "total_institutional_pct": round(total_pct, 2),
                    "institution_count": int(summary["institution_count"]) if summary else len(holdings),
                    "top_10_concentration": round(sum(float(h["pct_of_shares"]) for h in holdings[:10] if h.get("pct_of_shares")), 2),
                },
                "recent_activity": {
                    "institutions_increasing": increasing,
                    "institutions_decreasing": decreasing,
                    "net_sentiment": "Bullish" if increasing > decreasing else "Bearish" if decreasing > increasing else "Neutral",
                },
                "top_holders": [
                    {
                        "institution": h["institution_name"],
                        "shares_held": int(h["shares_held"]) if h.get("shares_held") else None,
                        "pct_of_shares": round(float(h["pct_of_shares"]), 3) if h.get("pct_of_shares") else None,
                        "change_shares": int(h["change_in_shares"]) if h.get("change_in_shares") else None,
                        "change_pct": round(float(h["change_pct"]), 2) if h.get("change_pct") else None,
                    }
                    for h in holdings[:10]
                ],
                "report_date": str(latest_report_date),
                "interpretation": f"Institutional ownership: {total_pct:.1f}%. {increasing} increasing, {decreasing} decreasing positions.",
            }
        else:
            return {
                "symbol": symbol,
                "summary_metrics": {
                    "total_institutional_ownership_pct": round(total_pct, 4),
                    "total_institutions": int(summary["institution_count"]) if summary else len(holdings),
                    "total_shares_held": int(summary["total_institutional_shares"]) if summary and summary.get("total_institutional_shares") else None,
                },
                "concentration_analysis": {
                    "top_5_pct": round(sum(float(h["pct_of_shares"]) for h in holdings[:5] if h.get("pct_of_shares")), 4),
                    "top_10_pct": round(sum(float(h["pct_of_shares"]) for h in holdings[:10] if h.get("pct_of_shares")), 4),
                    "concentration_level": "High" if len(holdings) > 0 and float(holdings[0]["pct_of_shares"]) > 10 else "Moderate",
                },
                "activity_analysis": {
                    "increasing_positions": increasing,
                    "decreasing_positions": decreasing,
                    "stable_positions": len(holdings) - increasing - decreasing,
                    "net_flow": "accumulation" if increasing > decreasing else "distribution" if decreasing > increasing else "neutral",
                },
                "institutional_holders": [
                    {
                        "institution_name": h["institution_name"],
                        "shares_held": int(h["shares_held"]) if h.get("shares_held") else None,
                        "pct_of_shares": round(float(h["pct_of_shares"]), 6) if h.get("pct_of_shares") else None,
                        "change_in_shares": int(h["change_in_shares"]) if h.get("change_in_shares") else None,
                        "change_pct": round(float(h["change_pct"]), 4) if h.get("change_pct") else None,
                        "report_date": str(h["report_date"]),
                    }
                    for h in holdings
                ],
                "data_quality": {
                    "report_date": str(latest_report_date),
                    "data_age_days": (date.today() - latest_report_date).days,
                    "reporting_lag": "Quarterly filings (13F) - data is delayed",
                },
            }
