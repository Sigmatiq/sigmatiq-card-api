"""
Relative Strength Handler - Stock performance vs peers.

Shows relative strength percentiles comparing stock performance to all others:
- RS percentiles for 20/60/120 day periods
- Sector comparison
- RS trend (improving or declining)

Data sources:
- sb.symbol_cross_sectional_eod (RS percentiles, liquidity ranks)
- sb.symbol_fundamentals_cache (sector information)
"""

from datetime import date
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class RelativeStrengthHandler(BaseCardHandler):
    """Handler for ticker_relative_strength card - relative strength percentiles."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Fetch relative strength data for the given symbol and trading date.

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
                detail="Symbol is required for ticker_relative_strength card",
            )

        # Fetch RS data from cross-sectional table
        query = """
            SELECT
                x.trading_date,
                x.symbol,
                x.rs_pct_20,
                x.rs_pct_60,
                x.rs_pct_120,
                f.sector
            FROM sb.symbol_cross_sectional_eod x
            LEFT JOIN sb.symbol_fundamentals_cache f ON f.symbol = x.symbol
            WHERE x.symbol = $1 AND x.trading_date = $2
            LIMIT 1
        """
        row = await self._fetch_one(query, {"symbol": symbol, "trading_date": trading_date})

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No relative strength data for {symbol} on {trading_date}",
            )

        # Extract values
        rs_20 = float(row["rs_pct_20"]) if row["rs_pct_20"] is not None else None
        rs_60 = float(row["rs_pct_60"]) if row["rs_pct_60"] is not None else None
        rs_120 = float(row["rs_pct_120"]) if row["rs_pct_120"] is not None else None
        sector = row["sector"] if row["sector"] else "Unknown"

        # Use 60-day RS as primary metric
        if rs_60 is None:
            raise HTTPException(
                status_code=404,
                detail=f"No 60-day RS data available for {symbol}",
            )

        # Classify RS
        rs_category = self._classify_rs(rs_60)

        # Detect trend (comparing 20-day vs 60-day)
        rs_trend = self._detect_rs_trend(rs_20, rs_60)

        # Format based on mode
        if mode == CardMode.beginner:
            return self._format_beginner(
                symbol,
                rs_60,
                rs_category,
                sector,
            )
        elif mode == CardMode.intermediate:
            return self._format_intermediate(
                symbol,
                rs_20,
                rs_60,
                rs_120,
                rs_category,
                rs_trend,
                sector,
            )
        else:
            return self._format_advanced(
                symbol,
                rs_20,
                rs_60,
                rs_120,
                rs_category,
                rs_trend,
                sector,
            )

    @staticmethod
    def _classify_rs(rs_60: float) -> str:
        """
        Classify RS into category based on percentile.

        Args:
            rs_60: 60-day RS percentile

        Returns:
            RS category: top_10, top_25, above_avg, below_avg, or bottom_25
        """
        if rs_60 >= 90:
            return "top_10"
        elif rs_60 >= 75:
            return "top_25"
        elif rs_60 >= 50:
            return "above_avg"
        elif rs_60 >= 25:
            return "below_avg"
        else:
            return "bottom_25"

    @staticmethod
    def _detect_rs_trend(rs_20: Optional[float], rs_60: Optional[float]) -> str:
        """
        Detect if RS is improving or declining.

        Args:
            rs_20: 20-day RS percentile
            rs_60: 60-day RS percentile

        Returns:
            Trend: improving, declining, or stable
        """
        if rs_20 is None or rs_60 is None:
            return "unknown"

        diff = rs_20 - rs_60
        if diff > 10:
            return "improving"
        elif diff < -10:
            return "declining"
        else:
            return "stable"

    def _format_beginner(
        self,
        symbol: str,
        rs_60: float,
        category: str,
        sector: str,
    ) -> dict[str, Any]:
        """Format for beginner mode - simple percentile and category."""
        # Get emoji for category
        emoji = {
            "top_10": "🚀",
            "top_25": "📈",
            "above_avg": "⚖️",
            "below_avg": "📉",
            "bottom_25": "🔻",
        }.get(category, "➡️")

        # Get label
        if category == "top_10":
            label = f"Top {100 - round(rs_60)}% performer"
        elif category == "top_25":
            label = f"Top {100 - round(rs_60)}% performer"
        else:
            label = f"Beating {round(rs_60)}% of stocks"

        return {
            "symbol": symbol,
            "rs_percentile": round(rs_60),
            "rs_label": f"{emoji} {label}",
            "category": category,
            "category_label": self._get_category_label(category),
            "sector": sector,
            "interpretation": self._get_beginner_interpretation(category),
            "educational_tip": "Relative Strength shows how a stock performs vs all others. High RS often continues - the trend is your friend.",
            "action_block": self._build_action_block_rs(rs_60, category, None),
        }

    def _format_intermediate(
        self,
        symbol: str,
        rs_20: Optional[float],
        rs_60: float,
        rs_120: Optional[float],
        category: str,
        trend: str,
        sector: str,
    ) -> dict[str, Any]:
        """Format for intermediate mode - multi-period RS and trend."""
        return {
            "symbol": symbol,
            "rs_percentiles": {
                "rs_20d": round(rs_20) if rs_20 is not None else None,
                "rs_60d": round(rs_60),
                "rs_120d": round(rs_120) if rs_120 is not None else None,
            },
            "category": category,
            "category_label": self._get_category_label(category),
            "trend": trend,
            "trend_label": self._get_trend_label(trend),
            "sector": sector,
            "interpretation": self._get_intermediate_interpretation(category, trend),
        }

    def _format_advanced(
        self,
        symbol: str,
        rs_20: Optional[float],
        rs_60: float,
        rs_120: Optional[float],
        category: str,
        trend: str,
        sector: str,
    ) -> dict[str, Any]:
        """Format for advanced mode - full RS details and analysis."""
        return {
            "symbol": symbol,
            "raw_percentiles": {
                "rs_20_day": round(rs_20, 2) if rs_20 is not None else None,
                "rs_60_day": round(rs_60, 2),
                "rs_120_day": round(rs_120, 2) if rs_120 is not None else None,
            },
            "classification": {
                "category": category,
                "category_label": self._get_category_label(category),
                "rank_vs_market": round(rs_60, 2),
            },
            "trend_analysis": {
                "trend": trend,
                "trend_label": self._get_trend_label(trend),
                "short_term_change": round(rs_20 - rs_60, 2) if rs_20 is not None else None,
                "long_term_change": round(rs_60 - rs_120, 2) if rs_120 is not None else None,
            },
            "context": {
                "sector": sector,
            },
            "thresholds": {
                "top_10": 90,
                "top_25": 75,
                "above_avg": 50,
                "below_avg": 25,
            },
            "action_block": self._build_action_block_rs(rs_60, category, trend),
        }

    def _build_action_block_rs(self, rs_60: float, category: str, trend: Optional[str]) -> dict[str, Any]:
        """Action guidance based on RS percentile and RS trend."""
        strong = rs_60 >= 80
        improving = trend == "improving"
        if strong and (improving or trend is None):
            return {
                "entry": "Favor pullbacks in RS leaders",
                "invalidation": "Lose 20-day or RS drop below ~60",
                "risk_note": "Normal sizing; leaders tend to trend",
                "targets": ["+1R", "+2R"],
                "confidence": 75,
            }
        if rs_60 <= 25:
            return {
                "entry": "Avoid weak RS longs; only defined-risk ideas",
                "invalidation": "N/A",
                "risk_note": "Weak RS underperforms; be defensive",
                "targets": [],
                "confidence": 40,
            }
        return {
            "entry": "Prefer improving RS names over declining",
            "invalidation": "N/A",
            "risk_note": "Be selective; wait for trend alignment",
            "targets": ["+1R"],
            "confidence": 60 if improving else 50,
        }

    @staticmethod
    def _get_category_label(category: str) -> str:
        """Get human-readable label for RS category."""
        labels = {
            "top_10": "Elite Performer (Top 10%)",
            "top_25": "Strong Performer (Top 25%)",
            "above_avg": "Above Average",
            "below_avg": "Below Average",
            "bottom_25": "Weak Performer (Bottom 25%)",
        }
        return labels.get(category, "Unknown")

    @staticmethod
    def _get_trend_label(trend: str) -> str:
        """Get human-readable label for RS trend."""
        labels = {
            "improving": "Improving (RS accelerating)",
            "declining": "Declining (RS weakening)",
            "stable": "Stable (RS steady)",
            "unknown": "Unknown",
        }
        return labels.get(trend, trend)

    @staticmethod
    def _get_beginner_interpretation(category: str) -> str:
        """Get beginner-friendly interpretation."""
        interpretations = {
            "top_10": "Elite momentum stock - outperforming 90%+ of the market. Strong relative strength often continues.",
            "top_25": "Strong momentum - outperforming most stocks. Good candidate for trend-following strategies.",
            "above_avg": "Slightly above average performance. No clear momentum edge either direction.",
            "below_avg": "Underperforming most stocks. Avoid for momentum strategies unless fundamentals support turnaround.",
            "bottom_25": "Weak momentum - lagging the market badly. High risk unless you see a specific catalyst for reversal.",
        }
        return interpretations.get(category, "No clear signal")

    @staticmethod
    def _get_intermediate_interpretation(category: str, trend: str) -> str:
        """Get intermediate-level interpretation with trend context."""
        base = {
            "top_10": "Elite relative strength",
            "top_25": "Strong relative strength",
            "above_avg": "Moderate relative strength",
            "below_avg": "Weak relative strength",
            "bottom_25": "Very weak relative strength",
        }.get(category, "Unknown RS")

        trend_context = {
            "improving": "and accelerating. Best time to establish or add to positions.",
            "declining": "but weakening. Consider tightening stops or taking partial profits.",
            "stable": "and holding steady. Position can be maintained with normal risk management.",
            "unknown": "trend unclear.",
        }.get(trend, "")

        return f"{base} {trend_context}"
