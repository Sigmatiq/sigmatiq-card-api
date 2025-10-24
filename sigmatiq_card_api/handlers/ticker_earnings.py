"""
Earnings Calendar Handler - Upcoming and past earnings events.

Shows earnings calendar data:
- Next earnings date
- EPS estimate vs actual
- Earnings surprise history
- Reaction to earnings

Data source: sb.earnings_calendar (expected table)
"""

from datetime import date
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class EarningsCalendarHandler(BaseCardHandler):
    """Handler for ticker_earnings card - earnings calendar and history."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Fetch earnings calendar data for the given symbol.

        Args:
            mode: Response complexity level
            symbol: Stock symbol (required)
            trading_date: Current trading date (for context)

        Returns:
            Formatted card data based on mode

        Raises:
            HTTPException: If symbol not provided or data not found
        """
        if not symbol:
            raise HTTPException(
                status_code=400,
                detail="Symbol is required for ticker_earnings card",
            )

        # Fetch upcoming earnings
        upcoming_query = """
            SELECT
                symbol,
                earnings_date,
                eps_estimate,
                revenue_estimate,
                fiscal_quarter,
                fiscal_year,
                earnings_time  -- 'BMO' (before market open) or 'AMC' (after market close)
            FROM sb.earnings_calendar
            WHERE symbol = $1
              AND earnings_date >= $2
            ORDER BY earnings_date ASC
            LIMIT 1
        """

        # Fetch recent earnings history
        history_query = """
            SELECT
                earnings_date,
                eps_estimate,
                eps_actual,
                eps_surprise_pct,
                revenue_estimate,
                revenue_actual,
                price_change_1d_pct
            FROM sb.earnings_calendar
            WHERE symbol = $1
              AND earnings_date < $2
              AND eps_actual IS NOT NULL
            ORDER BY earnings_date DESC
            LIMIT 4
        """

        upcoming = await self._fetch_one(upcoming_query, {"symbol": symbol, "earnings_date": trading_date})
        history = await self._fetch_all(history_query, {"symbol": symbol, "earnings_date": trading_date})

        if not upcoming and not history:
            raise HTTPException(
                status_code=404,
                detail=f"No earnings data for {symbol}",
            )

        # Format based on mode
        if mode == CardMode.beginner:
            return self._format_beginner(symbol, upcoming, history)
        elif mode == CardMode.intermediate:
            return self._format_intermediate(symbol, upcoming, history)
        else:
            return self._format_advanced(symbol, upcoming, history)

    def _format_beginner(
        self,
        symbol: str,
        upcoming: Optional[dict],
        history: list[dict],
    ) -> dict[str, Any]:
        """Format for beginner mode - simple earnings overview."""
        result = {
            "symbol": symbol,
            "educational_tip": "Earnings reports show company profits. Stock often moves sharply on earnings day. Wait until after the report if you're unsure.",
        }

        if upcoming:
            earnings_date = upcoming["earnings_date"]
            days_until = (earnings_date - date.today()).days

            result.update({
                "next_earnings_date": str(earnings_date),
                "days_until_earnings": days_until,
                "earnings_time": self._get_earnings_time_label(upcoming.get("earnings_time")),
                "fiscal_period": f"Q{upcoming['fiscal_quarter']} {upcoming['fiscal_year']}" if upcoming.get("fiscal_quarter") else None,
                "advice": self._get_beginner_advice(days_until),
            })

        if history:
            # Calculate average surprise
            surprises = [h["eps_surprise_pct"] for h in history if h.get("eps_surprise_pct") is not None]
            avg_surprise = sum(surprises) / len(surprises) if surprises else None

            recent_surprises = [{"date": str(h["earnings_date"]), "surprise_pct": round(h["eps_surprise_pct"], 1)} for h in history[:2] if h.get("eps_surprise_pct") is not None]

            result.update({
                "recent_performance": "Usually beats expectations" if avg_surprise and avg_surprise > 0 else "Often misses expectations" if avg_surprise and avg_surprise < 0 else "Mixed results",
                "recent_surprises": recent_surprises,
                "interpretation": self._get_beginner_interpretation(avg_surprise),
            })

        return result

    def _format_intermediate(
        self,
        symbol: str,
        upcoming: Optional[dict],
        history: list[dict],
    ) -> dict[str, Any]:
        """Format for intermediate mode - earnings metrics."""
        result = {"symbol": symbol}

        if upcoming:
            result["upcoming_earnings"] = {
                "earnings_date": str(upcoming["earnings_date"]),
                "earnings_time": upcoming.get("earnings_time"),
                "fiscal_period": f"Q{upcoming['fiscal_quarter']} {upcoming['fiscal_year']}" if upcoming.get("fiscal_quarter") else None,
                "eps_estimate": round(upcoming["eps_estimate"], 2) if upcoming.get("eps_estimate") else None,
                "revenue_estimate": upcoming.get("revenue_estimate"),
                "days_until": (upcoming["earnings_date"] - date.today()).days,
            }

        if history:
            result["earnings_history"] = [
                {
                    "date": str(h["earnings_date"]),
                    "eps_estimate": round(h["eps_estimate"], 2) if h.get("eps_estimate") else None,
                    "eps_actual": round(h["eps_actual"], 2) if h.get("eps_actual") else None,
                    "surprise_pct": round(h["eps_surprise_pct"], 1) if h.get("eps_surprise_pct") is not None else None,
                    "price_reaction": f"{h['price_change_1d_pct']:+.1f}%" if h.get("price_change_1d_pct") is not None else None,
                }
                for h in history
            ]

            # Calculate statistics
            surprises = [h["eps_surprise_pct"] for h in history if h.get("eps_surprise_pct") is not None]
            reactions = [h["price_change_1d_pct"] for h in history if h.get("price_change_1d_pct") is not None]

            result["statistics"] = {
                "avg_surprise_pct": round(sum(surprises) / len(surprises), 1) if surprises else None,
                "avg_price_reaction_pct": round(sum(reactions) / len(reactions), 1) if reactions else None,
                "beat_rate": f"{sum(1 for s in surprises if s > 0) / len(surprises) * 100:.0f}%" if surprises else None,
            }

        return result

    def _format_advanced(
        self,
        symbol: str,
        upcoming: Optional[dict],
        history: list[dict],
    ) -> dict[str, Any]:
        """Format for advanced mode - full earnings analysis."""
        result = {"symbol": symbol}

        if upcoming:
            result["upcoming_earnings"] = {
                "earnings_date": str(upcoming["earnings_date"]),
                "earnings_time": upcoming.get("earnings_time"),
                "fiscal_quarter": upcoming.get("fiscal_quarter"),
                "fiscal_year": upcoming.get("fiscal_year"),
                "eps_estimate": round(upcoming["eps_estimate"], 4) if upcoming.get("eps_estimate") else None,
                "revenue_estimate": upcoming.get("revenue_estimate"),
                "days_until": (upcoming["earnings_date"] - date.today()).days,
            }

        if history:
            result["earnings_history"] = [
                {
                    "date": str(h["earnings_date"]),
                    "eps": {
                        "estimate": round(h["eps_estimate"], 4) if h.get("eps_estimate") else None,
                        "actual": round(h["eps_actual"], 4) if h.get("eps_actual") else None,
                        "surprise_pct": round(h["eps_surprise_pct"], 4) if h.get("eps_surprise_pct") is not None else None,
                    },
                    "revenue": {
                        "estimate": h.get("revenue_estimate"),
                        "actual": h.get("revenue_actual"),
                    },
                    "price_reaction_1d_pct": round(h["price_change_1d_pct"], 4) if h.get("price_change_1d_pct") is not None else None,
                }
                for h in history
            ]

            # Advanced statistics
            surprises = [h["eps_surprise_pct"] for h in history if h.get("eps_surprise_pct") is not None]
            reactions = [h["price_change_1d_pct"] for h in history if h.get("price_change_1d_pct") is not None]
            beats = [h for h in history if h.get("eps_surprise_pct") is not None and h["eps_surprise_pct"] > 0]
            misses = [h for h in history if h.get("eps_surprise_pct") is not None and h["eps_surprise_pct"] < 0]

            result["advanced_stats"] = {
                "avg_surprise_pct": round(sum(surprises) / len(surprises), 4) if surprises else None,
                "median_surprise_pct": round(sorted(surprises)[len(surprises) // 2], 4) if surprises else None,
                "avg_price_reaction_pct": round(sum(reactions) / len(reactions), 4) if reactions else None,
                "beat_rate": round(len(beats) / len(surprises) * 100, 2) if surprises else None,
                "avg_beat_surprise": round(sum(h["eps_surprise_pct"] for h in beats) / len(beats), 4) if beats else None,
                "avg_miss_surprise": round(sum(h["eps_surprise_pct"] for h in misses) / len(misses), 4) if misses else None,
                "consistency": self._assess_consistency(surprises),
            }

            result["trading_insights"] = {
                "earnings_volatility": "high" if reactions and sum(abs(r) for r in reactions) / len(reactions) > 5 else "moderate",
                "reliability": self._assess_reliability(surprises),
                "recommendation": self._get_trading_recommendation(surprises, reactions),
            }

        return result

    @staticmethod
    def _get_earnings_time_label(earnings_time: Optional[str]) -> str:
        """Get human-readable earnings time."""
        if earnings_time == "BMO":
            return "Before Market Open"
        elif earnings_time == "AMC":
            return "After Market Close"
        else:
            return "Not specified"

    @staticmethod
    def _get_beginner_advice(days_until: int) -> str:
        """Get beginner trading advice."""
        if days_until <= 0:
            return "Earnings are today! Avoid trading until after the report. Prices can swing wildly."
        elif days_until <= 7:
            return "Earnings coming soon. Consider waiting until after the report to avoid surprise moves."
        elif days_until <= 14:
            return "Earnings in 2 weeks. Watch for position buildup. Consider reducing position size before earnings."
        else:
            return "Earnings are more than 2 weeks away. Normal trading conditions."

    @staticmethod
    def _get_beginner_interpretation(avg_surprise: Optional[float]) -> str:
        """Get beginner interpretation of earnings history."""
        if avg_surprise is None:
            return "No recent earnings history available."
        if avg_surprise > 5:
            return "Company consistently beats expectations. Strong track record."
        elif avg_surprise > 0:
            return "Company usually meets or slightly beats expectations."
        elif avg_surprise > -5:
            return "Company has missed expectations recently. Be cautious."
        else:
            return "Company frequently misses estimates. High risk around earnings."

    @staticmethod
    def _assess_consistency(surprises: list[float]) -> str:
        """Assess earnings consistency."""
        if not surprises or len(surprises) < 2:
            return "insufficient_data"

        # Calculate standard deviation
        avg = sum(surprises) / len(surprises)
        variance = sum((s - avg) ** 2 for s in surprises) / len(surprises)
        std_dev = variance ** 0.5

        if std_dev < 2:
            return "highly_consistent"
        elif std_dev < 5:
            return "moderately_consistent"
        else:
            return "inconsistent"

    @staticmethod
    def _assess_reliability(surprises: list[float]) -> str:
        """Assess earnings reliability."""
        if not surprises:
            return "unknown"

        beat_rate = sum(1 for s in surprises if s > 0) / len(surprises)

        if beat_rate >= 0.8:
            return "highly_reliable"
        elif beat_rate >= 0.6:
            return "moderately_reliable"
        elif beat_rate >= 0.4:
            return "mixed"
        else:
            return "unreliable"

    @staticmethod
    def _get_trading_recommendation(surprises: list[float], reactions: list[float]) -> str:
        """Get trading recommendation."""
        if not surprises or not reactions:
            return "insufficient_data"

        avg_surprise = sum(surprises) / len(surprises)
        avg_reaction = sum(abs(r) for r in reactions) / len(reactions)

        if avg_surprise > 5 and avg_reaction < 3:
            return "Consider holding through earnings - company has strong track record with muted reactions"
        elif avg_surprise > 0 and avg_reaction > 5:
            return "High volatility on earnings - consider reducing position or using options"
        elif avg_surprise < 0:
            return "Company has missed recently - consider exiting before earnings or using protective puts"
        else:
            return "Mixed results - use small position size or wait until after earnings"
