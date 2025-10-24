"""
IV Skew Handler - Implied Volatility and skew metrics.

Shows IV metrics for options trading:
- IV30 (30-day implied volatility)
- IV percentile (vs 1-year history)
- Skew (put IV vs call IV)
- Expected moves (1-day, 1-week)

Data source: sb.options_agg_eod
"""

from datetime import date
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class IVSkewHandler(BaseCardHandler):
    """Handler for options_iv_skew card - IV and skew metrics."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Fetch IV and skew data for the given symbol and trading date.

        Args:
            mode: Response complexity level
            symbol: Stock symbol (required)
            trading_date: Trading date to fetch data for

        Returns:
            Formatted card data based on mode

        Raises:
            HTTPException: If symbol not provided or data not found
        """
        if not symbol:
            raise HTTPException(
                status_code=400,
                detail="Symbol is required for options_iv_skew card",
            )

        # Fetch IV metrics
        query = """
            SELECT
                as_of,
                symbol,
                iv30,
                iv_rank,
                iv_percentile,
                skew,
                expected_move_1d,
                expected_move_1w
            FROM sb.options_agg_eod
            WHERE symbol = $1 AND as_of = $2
            LIMIT 1
        """
        row = await self._fetch_one(query, {"symbol": symbol, "as_of": trading_date})

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No options IV data for {symbol} on {trading_date}",
            )

        # Extract values
        iv30 = float(row["iv30"]) if row["iv30"] is not None else None
        iv_rank = float(row["iv_rank"]) if row["iv_rank"] is not None else None
        iv_percentile = float(row["iv_percentile"]) if row["iv_percentile"] is not None else None
        skew = float(row["skew"]) if row["skew"] is not None else None
        em_1d = float(row["expected_move_1d"]) if row["expected_move_1d"] is not None else None
        em_1w = float(row["expected_move_1w"]) if row["expected_move_1w"] is not None else None

        # Classify IV
        if iv_percentile is not None:
            iv_class = self._classify_iv(iv_percentile)
        else:
            iv_class = "unknown"

        # Format based on mode
        if mode == CardMode.beginner:
            return self._format_beginner(
                symbol,
                iv30,
                iv_percentile,
                iv_class,
                em_1d,
                em_1w,
            )
        elif mode == CardMode.intermediate:
            return self._format_intermediate(
                symbol,
                iv30,
                iv_rank,
                iv_percentile,
                iv_class,
                skew,
                em_1d,
                em_1w,
            )
        else:
            return self._format_advanced(
                symbol,
                iv30,
                iv_rank,
                iv_percentile,
                iv_class,
                skew,
                em_1d,
                em_1w,
            )

    @staticmethod
    def _classify_iv(iv_percentile: float) -> str:
        """Classify IV based on percentile."""
        if iv_percentile >= 75:
            return "expensive"
        elif iv_percentile <= 25:
            return "cheap"
        else:
            return "fair"

    def _format_beginner(
        self,
        symbol: str,
        iv30: Optional[float],
        iv_percentile: Optional[float],
        iv_class: str,
        em_1d: Optional[float],
        em_1w: Optional[float],
    ) -> dict[str, Any]:
        """Format for beginner mode - simple IV classification."""
        emoji = {
            "expensive": "💰",
            "cheap": "💎",
            "fair": "📊",
            "unknown": "❓",
        }.get(iv_class, "➡️")

        return {
            "symbol": symbol,
            "iv_percentile": round(iv_percentile) if iv_percentile is not None else None,
            "iv_label": f"{emoji} {self._get_iv_label(iv_class, iv_percentile)}",
            "iv_class": iv_class,
            "expected_move_1d": round(em_1d, 1) if em_1d is not None else None,
            "expected_move_1d_label": f"±{round(em_1d, 1)}% expected tomorrow" if em_1d else None,
            "expected_move_1w": round(em_1w, 1) if em_1w is not None else None,
            "expected_move_1w_label": f"±{round(em_1w, 1)}% expected this week" if em_1w else None,
            "interpretation": self._get_beginner_interpretation(iv_class, iv_percentile),
            "trading_advice": self._get_beginner_advice(iv_class),
            "educational_tip": "IV percentile compares current IV to past year. High = expensive options (sell premium). Low = cheap options (buy premium).",
        }

    def _format_intermediate(
        self,
        symbol: str,
        iv30: Optional[float],
        iv_rank: Optional[float],
        iv_percentile: Optional[float],
        iv_class: str,
        skew: Optional[float],
        em_1d: Optional[float],
        em_1w: Optional[float],
    ) -> dict[str, Any]:
        """Format for intermediate mode - IV metrics and skew."""
        return {
            "symbol": symbol,
            "iv_metrics": {
                "iv30": round(iv30, 2) if iv30 is not None else None,
                "iv_rank": round(iv_rank, 1) if iv_rank is not None else None,
                "iv_percentile": round(iv_percentile, 1) if iv_percentile is not None else None,
                "iv_classification": iv_class,
            },
            "skew": {
                "skew_value": round(skew, 2) if skew is not None else None,
                "skew_interpretation": self._interpret_skew(skew),
            },
            "expected_moves": {
                "one_day_pct": round(em_1d, 2) if em_1d is not None else None,
                "one_week_pct": round(em_1w, 2) if em_1w is not None else None,
            },
            "interpretation": self._get_intermediate_interpretation(iv_class, iv_percentile, skew),
            "strategy_suggestions": self._get_strategy_suggestions(iv_class),
        }

    def _format_advanced(
        self,
        symbol: str,
        iv30: Optional[float],
        iv_rank: Optional[float],
        iv_percentile: Optional[float],
        iv_class: str,
        skew: Optional[float],
        em_1d: Optional[float],
        em_1w: Optional[float],
    ) -> dict[str, Any]:
        """Format for advanced mode - full IV analysis."""
        return {
            "symbol": symbol,
            "raw_metrics": {
                "iv30_annualized": round(iv30, 4) if iv30 is not None else None,
                "iv_rank": round(iv_rank, 4) if iv_rank is not None else None,
                "iv_percentile": round(iv_percentile, 4) if iv_percentile is not None else None,
            },
            "classification": {
                "iv_class": iv_class,
                "premium_level": self._get_premium_level(iv_percentile),
            },
            "skew_analysis": {
                "skew": round(skew, 4) if skew is not None else None,
                "skew_type": self._classify_skew(skew),
                "interpretation": self._interpret_skew(skew),
            },
            "expected_moves": {
                "one_day": {
                    "percent": round(em_1d, 4) if em_1d is not None else None,
                    "one_std_dev": True,
                    "probability": "68%",
                },
                "one_week": {
                    "percent": round(em_1w, 4) if em_1w is not None else None,
                    "one_std_dev": True,
                    "probability": "68%",
                },
            },
            "trading_implications": {
                "premium_selling_favorable": iv_class == "expensive",
                "premium_buying_favorable": iv_class == "cheap",
                "put_skew_present": skew is not None and skew > 0,
            },
            "thresholds": {
                "expensive": ">75 percentile",
                "fair": "25-75 percentile",
                "cheap": "<25 percentile",
            },
        }

    @staticmethod
    def _get_iv_label(iv_class: str, iv_percentile: Optional[float]) -> str:
        """Get human-readable IV label."""
        if iv_percentile is None:
            return "Unknown IV"

        percentile_str = f"{round(iv_percentile)}th percentile"

        if iv_class == "expensive":
            return f"Options expensive ({percentile_str})"
        elif iv_class == "cheap":
            return f"Options cheap ({percentile_str})"
        else:
            return f"Options fairly priced ({percentile_str})"

    @staticmethod
    def _interpret_skew(skew: Optional[float]) -> str:
        """Interpret skew value."""
        if skew is None:
            return "Unknown"
        if skew > 0.1:
            return "High put skew - fear premium in puts"
        elif skew < -0.1:
            return "Call skew - unusual, calls more expensive"
        else:
            return "Balanced - puts and calls similarly priced"

    @staticmethod
    def _classify_skew(skew: Optional[float]) -> str:
        """Classify skew type."""
        if skew is None:
            return "unknown"
        if skew > 0.05:
            return "put_skew"
        elif skew < -0.05:
            return "call_skew"
        else:
            return "balanced"

    @staticmethod
    def _get_premium_level(iv_percentile: Optional[float]) -> str:
        """Get premium level description."""
        if iv_percentile is None:
            return "unknown"
        if iv_percentile >= 90:
            return "very expensive"
        elif iv_percentile >= 75:
            return "expensive"
        elif iv_percentile >= 50:
            return "moderate"
        elif iv_percentile >= 25:
            return "reasonable"
        else:
            return "cheap"

    @staticmethod
    def _get_beginner_interpretation(iv_class: str, iv_percentile: Optional[float]) -> str:
        """Get beginner-friendly interpretation."""
        if iv_percentile is None:
            return "IV data unavailable"

        interpretations = {
            "expensive": f"Options are expensive - IV is at {round(iv_percentile)}th percentile. Options premium is elevated compared to historical levels. Good time to sell options (credit spreads, covered calls).",
            "cheap": f"Options are cheap - IV is at {round(iv_percentile)}th percentile. Options premium is low compared to historical levels. Good time to buy options (long calls/puts, debit spreads).",
            "fair": f"Options are fairly priced - IV is at {round(iv_percentile)}th percentile. No clear edge from IV levels. Other factors should drive strategy selection.",
        }
        return interpretations.get(iv_class, "IV level unknown")

    @staticmethod
    def _get_beginner_advice(iv_class: str) -> str:
        """Get beginner trading advice."""
        advice = {
            "expensive": "Consider selling premium: credit spreads, iron condors, covered calls. Avoid buying naked options - they're overpriced.",
            "cheap": "Consider buying options: debit spreads, long calls/puts. Premium is cheap, good risk/reward for directional bets.",
            "fair": "No strong IV edge. Focus on directional view and fundamentals rather than IV strategies.",
            "unknown": "Wait for IV data before making options trades.",
        }
        return advice.get(iv_class, "Assess risk carefully")

    @staticmethod
    def _get_intermediate_interpretation(iv_class: str, iv_percentile: Optional[float], skew: Optional[float]) -> str:
        """Get intermediate interpretation."""
        base = f"IV classification: {iv_class}"

        if iv_percentile is not None:
            base += f" ({round(iv_percentile)}th percentile)"

        skew_context = ""
        if skew is not None and abs(skew) > 0.05:
            skew_type = "put skew" if skew > 0 else "call skew"
            skew_context = f". {skew_type.capitalize()} present ({round(skew * 100, 1)}%)"

        return base + skew_context

    @staticmethod
    def _get_strategy_suggestions(iv_class: str) -> list[str]:
        """Get strategy suggestions based on IV."""
        suggestions = {
            "expensive": [
                "Credit spreads (sell premium)",
                "Iron condors (neutral, collect premium)",
                "Covered calls (if you own stock)",
                "Cash-secured puts (sell put premium)",
            ],
            "cheap": [
                "Debit spreads (limited risk directional)",
                "Long calls/puts (directional bets)",
                "Calendar spreads (buy cheap, sell expensive later)",
            ],
            "fair": [
                "Focus on directional view",
                "No clear IV advantage",
                "Consider stock instead of options",
            ],
        }
        return suggestions.get(iv_class, ["Wait for clearer IV signals"])
