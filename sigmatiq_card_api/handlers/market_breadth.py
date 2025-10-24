"""
Market Breadth card handler.

Provides overall market health metrics: advancing vs declining stocks, new highs/lows, etc.
"""

from datetime import date
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class MarketBreadthHandler(BaseCardHandler):
    """Handler for market breadth card."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Fetch market breadth data.

        Args:
            mode: Complexity level
            symbol: Not used (market-wide card)
            trading_date: Trading date

        Returns:
            Formatted market breadth data
        """
        # Query market breadth data (Azure schema)
        query = """
            SELECT
                above_ma50_pct,
                above_ma200_pct,
                advance,
                decline,
                new_52w_highs,
                new_52w_lows,
                advance_decline_ratio,
                total_volume,
                advancing_volume,
                declining_volume
            FROM sb.market_breadth_daily
            WHERE trading_date = $1
            AND preset_id = 'all_active'
            ORDER BY trading_date DESC
            LIMIT 1
        """

        row = await self._fetch_one(query, {"trading_date": trading_date})

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No market breadth data available for {trading_date}",
            )

        # Extract values (Azure schema)
        pct_above_ma50 = row["above_ma50_pct"] or 0
        pct_above_ma200 = row["above_ma200_pct"] or 0
        advancing = row["advance"] or 0
        declining = row["decline"] or 0
        new_highs = row["new_52w_highs"] or 0
        new_lows = row["new_52w_lows"] or 0
        net_advances = advancing - declining  # Calculate from advance/decline
        ad_ratio = row["advance_decline_ratio"] or 0

        # Format based on mode
        if mode == CardMode.beginner:
            return self._format_beginner(
                pct_above_ma50=pct_above_ma50,
                advancing=advancing,
                declining=declining,
                new_highs=new_highs,
                new_lows=new_lows,
            )

        elif mode == CardMode.intermediate:
            return self._format_intermediate(
                pct_above_ma50=pct_above_ma50,
                pct_above_ma200=pct_above_ma200,
                advancing=advancing,
                declining=declining,
                new_highs=new_highs,
                new_lows=new_lows,
                net_advances=net_advances,
                ad_ratio=ad_ratio,
            )

        else:  # advanced
            return self._format_advanced(row)

    def _format_beginner(
        self,
        pct_above_ma50: float,
        advancing: int,
        declining: int,
        new_highs: int,
        new_lows: int,
    ) -> dict[str, Any]:
        """Format for beginner mode (simplified, plain language)."""
        breadth_health = self._get_health_label(
            pct_above_ma50, {"good": 60, "bad": 40}
        )

        return {
            "pct_above_ma50": pct_above_ma50,
            "pct_above_ma50_label": f"{pct_above_ma50:.0f}% of stocks above 50-day average",
            "breadth_health": breadth_health,
            "breadth_health_label": self._get_breadth_health_description(
                breadth_health, new_highs, new_lows
            ),
            "advancing": advancing,
            "declining": declining,
            "ad_label": f"{advancing} stocks up, {declining} stocks down",
            "educational_tip": self._add_educational_tip("market_breadth", CardMode.beginner),
            "bias_block": self._build_bias_block(pct_above_ma50, None, new_highs, new_lows),
        }

    def _format_intermediate(
        self,
        pct_above_ma50: float,
        pct_above_ma200: float,
        advancing: int,
        declining: int,
        new_highs: int,
        new_lows: int,
        net_advances: int,
        ad_ratio: float,
    ) -> dict[str, Any]:
        """Format for intermediate mode (more technical terms)."""
        return {
            "pct_above_ma50": pct_above_ma50,
            "pct_above_ma200": pct_above_ma200,
            "advancing": advancing,
            "declining": declining,
            "net_advances": net_advances,
            "ad_ratio": ad_ratio,
            "new_highs": new_highs,
            "new_lows": new_lows,
            "hl_spread": new_highs - new_lows,
            "breadth_health": self._get_health_label(
                pct_above_ma50, {"good": 60, "bad": 40}
            ),
            "interpretation": self._get_intermediate_interpretation(
                pct_above_ma50, ad_ratio, new_highs, new_lows
            ),
            "bias_block": self._build_bias_block(pct_above_ma50, ad_ratio, new_highs, new_lows),
        }

    def _build_bias_block(
        self, pct_above_ma50: float, ad_ratio: Optional[float], new_highs: int, new_lows: int
    ) -> dict[str, Any]:
        """Construct a simple risk bias from breadth metrics."""
        bias = "neutral"
        focus = "stock-picking; favor RS leaders"
        guardrails = "Reduce risk if new lows expand intraday"
        if pct_above_ma50 > 60 and (ad_ratio is None or ad_ratio > 1.0) and new_highs >= new_lows:
            bias = "risk_on"
            focus = "favor long continuation; growth/tech if leaders"
            guardrails = "If AD ratio < 1 by midday, scale back risk"
        elif pct_above_ma50 < 40 and (ad_ratio is None or ad_ratio < 1.0) and new_lows > new_highs:
            bias = "risk_off"
            focus = "defensive; avoid new longs; tighten stops"
            guardrails = "Only take A+ setups with small size"
        return {"bias": bias, "focus": focus, "guardrails": guardrails}

    def _format_advanced(self, row: Any) -> dict[str, Any]:
        """Format for advanced mode (all fields, no labels)."""
        return {
            "pct_above_ma50": row["above_ma50_pct"],
            "pct_above_ma200": row["above_ma200_pct"],
            "advancing": row["advance"],
            "declining": row["decline"],
            "new_highs": row["new_52w_highs"],
            "new_lows": row["new_52w_lows"],
            "net_advances": (row["advance"] or 0) - (row["decline"] or 0),
            "advance_decline_ratio": row["advance_decline_ratio"],
            "total_volume": row["total_volume"],
            "advancing_volume": row["advancing_volume"],
            "declining_volume": row["declining_volume"],
            "hl_spread": (row["new_52w_highs"] or 0) - (row["new_52w_lows"] or 0),
            "volume_ratio": (
                row["advancing_volume"] / row["declining_volume"]
                if row["declining_volume"] and row["declining_volume"] > 0
                else None
            ),
        }

    def _get_breadth_health_description(
        self, health: str, new_highs: int, new_lows: int
    ) -> str:
        """Get plain-language description of breadth health."""
        if health == "healthy":
            return f"Market is healthy. More stocks hitting highs ({new_highs}) vs lows ({new_lows})."
        elif health == "weak":
            return f"Market is weak. More stocks hitting lows ({new_lows}) vs highs ({new_highs})."
        else:
            return "Market breadth is mixed. Watch for a clearer trend."

    def _get_intermediate_interpretation(
        self, pct_above_ma50: float, ad_ratio: float, new_highs: int, new_lows: int
    ) -> str:
        """Get interpretation for intermediate mode."""
        if pct_above_ma50 > 60 and ad_ratio > 1.5 and new_highs > new_lows:
            return "Strong breadth: broad participation in rally"
        elif pct_above_ma50 < 40 and ad_ratio < 0.7 and new_lows > new_highs:
            return "Weak breadth: broad selling pressure"
        elif pct_above_ma50 > 60 and ad_ratio < 1.0:
            return "Mixed: index rally but declining internals (potential divergence)"
        else:
            return "Neutral breadth: no clear directional bias"
