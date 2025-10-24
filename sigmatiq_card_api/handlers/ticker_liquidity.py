"""
Liquidity Handler - Stock trading liquidity metrics.

Shows liquidity metrics to determine ease of trading:
- Dollar volume percentile
- RVOL (relative volume) percentile
- Liquidity classification (high/moderate/low)

Data sources:
- sb.symbol_cross_sectional_eod (liquidity ranks)
- sb.symbol_derived_eod (volume, rvol, close for dollar volume calculation)
"""

from datetime import date
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class LiquidityHandler(BaseCardHandler):
    """Handler for ticker_liquidity card - trading liquidity metrics."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Fetch liquidity metrics for the given symbol and trading date.

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
                detail="Symbol is required for ticker_liquidity card",
            )

        # Fetch liquidity data
        query = """
            SELECT
                x.trading_date,
                x.symbol,
                x.liq_dollar_rank_20,
                x.rvol_pctile_20,
                d.volume,
                d.rvol,
                d.close
            FROM sb.symbol_cross_sectional_eod x
            JOIN sb.symbol_derived_eod d ON d.symbol = x.symbol AND d.trading_date = x.trading_date
            WHERE x.symbol = $1 AND x.trading_date = $2
            LIMIT 1
        """
        row = await self._fetch_one(query, {"symbol": symbol, "trading_date": trading_date})

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No liquidity data for {symbol} on {trading_date}",
            )

        # Extract values
        liq_rank = float(row["liq_dollar_rank_20"]) if row["liq_dollar_rank_20"] is not None else None
        rvol_pct = float(row["rvol_pctile_20"]) if row["rvol_pctile_20"] is not None else None
        volume = int(row["volume"]) if row["volume"] else 0
        rvol = float(row["rvol"]) if row["rvol"] is not None else None
        close = float(row["close"]) if row["close"] else 0

        # Calculate dollar volume
        dollar_volume = volume * close if volume and close else 0

        # Classify liquidity
        if liq_rank is None:
            liquidity_class = "unknown"
        elif liq_rank >= 80:
            liquidity_class = "high"
        elif liq_rank >= 40:
            liquidity_class = "moderate"
        else:
            liquidity_class = "low"

        # Format based on mode
        if mode == CardMode.beginner:
            return self._format_beginner(
                symbol,
                liquidity_class,
                dollar_volume,
                rvol,
            )
        elif mode == CardMode.intermediate:
            return self._format_intermediate(
                symbol,
                liquidity_class,
                liq_rank,
                rvol_pct,
                dollar_volume,
                volume,
                rvol,
            )
        else:
            return self._format_advanced(
                symbol,
                liquidity_class,
                liq_rank,
                rvol_pct,
                dollar_volume,
                volume,
                rvol,
                close,
            )

    def _format_beginner(
        self,
        symbol: str,
        liquidity_class: str,
        dollar_volume: float,
        rvol: Optional[float],
    ) -> dict[str, Any]:
        """Format for beginner mode - simple classification and guidance."""
        # Get emoji for liquidity class
        emoji = {
            "high": "✅",
            "moderate": "⚠️",
            "low": "❌",
            "unknown": "❓",
        }.get(liquidity_class, "➡️")

        return {
            "symbol": symbol,
            "liquidity": liquidity_class,
            "liquidity_label": self._get_liquidity_label(liquidity_class),
            "dollar_volume": round(dollar_volume),
            "dollar_volume_label": self._format_dollar_volume(dollar_volume),
            "relative_volume": round(rvol, 2) if rvol is not None else None,
            "sizing_hint": (
                "Normal sizing" if liquidity_class == "high" else
                "Moderate size; watch spreads" if liquidity_class == "moderate" else
                "Small size only; illiquid conditions"
            ),
            "description": self._get_beginner_description(liquidity_class),
            "trading_advice": self._get_trading_advice(liquidity_class),
            "educational_tip": "High liquidity stocks have tighter bid-ask spreads and less slippage on orders. Dollar volume (shares × price) matters more than just share volume.",
        }

    def _format_intermediate(
        self,
        symbol: str,
        liquidity_class: str,
        liq_rank: Optional[float],
        rvol_pct: Optional[float],
        dollar_volume: float,
        volume: int,
        rvol: Optional[float],
    ) -> dict[str, Any]:
        """Format for intermediate mode - detailed metrics."""
        return {
            "symbol": symbol,
            "liquidity_classification": liquidity_class,
            "liquidity_label": self._get_liquidity_label(liquidity_class),
            "metrics": {
                "dollar_volume_rank": round(liq_rank) if liq_rank is not None else None,
                "rvol_percentile": round(rvol_pct) if rvol_pct is not None else None,
                "dollar_volume": round(dollar_volume),
                "share_volume": volume,
                "relative_volume": round(rvol, 2) if rvol is not None else None,
            },
            "interpretation": self._get_intermediate_interpretation(liquidity_class, liq_rank, rvol),
            "trading_guidance": self._get_trading_advice(liquidity_class),
        }

    def _format_advanced(
        self,
        symbol: str,
        liquidity_class: str,
        liq_rank: Optional[float],
        rvol_pct: Optional[float],
        dollar_volume: float,
        volume: int,
        rvol: Optional[float],
        close: float,
    ) -> dict[str, Any]:
        """Format for advanced mode - full liquidity analysis."""
        return {
            "symbol": symbol,
            "classification": liquidity_class,
            "raw_metrics": {
                "dollar_volume_rank_20d": round(liq_rank, 2) if liq_rank is not None else None,
                "rvol_percentile_20d": round(rvol_pct, 2) if rvol_pct is not None else None,
                "dollar_volume": round(dollar_volume, 2),
                "share_volume": volume,
                "relative_volume": round(rvol, 4) if rvol is not None else None,
                "close_price": round(close, 2),
            },
            "derived_metrics": {
                "volume_vs_average": f"{round((rvol - 1) * 100)}%" if rvol else None,
                "dollars_per_share": round(close, 2),
            },
            "thresholds": {
                "high_liquidity": "80+ percentile",
                "moderate_liquidity": "40-80 percentile",
                "low_liquidity": "<40 percentile",
            },
            "risk_assessment": {
                "slippage_risk": "Low" if liquidity_class == "high" else "Moderate" if liquidity_class == "moderate" else "High",
                "execution_quality": "Excellent" if liquidity_class == "high" else "Good" if liquidity_class == "moderate" else "Poor",
            },
        }

    @staticmethod
    def _get_liquidity_label(liquidity_class: str) -> str:
        """Get human-readable label for liquidity class."""
        labels = {
            "high": "High Liquidity",
            "moderate": "Moderate Liquidity",
            "low": "Low Liquidity",
            "unknown": "Unknown",
        }
        return labels.get(liquidity_class, liquidity_class)

    @staticmethod
    def _format_dollar_volume(dollar_volume: float) -> str:
        """Format dollar volume for display."""
        if dollar_volume >= 1_000_000_000:
            return f"${dollar_volume / 1_000_000_000:.2f}B daily volume"
        elif dollar_volume >= 1_000_000:
            return f"${dollar_volume / 1_000_000:.1f}M daily volume"
        elif dollar_volume >= 1_000:
            return f"${dollar_volume / 1_000:.0f}K daily volume"
        else:
            return f"${dollar_volume:.0f} daily volume"

    @staticmethod
    def _get_beginner_description(liquidity_class: str) -> str:
        """Get beginner-friendly description."""
        descriptions = {
            "high": "Easy to trade with tight spreads. You can enter and exit positions quickly at fair prices.",
            "moderate": "Decent liquidity for most traders. Use limit orders for larger positions.",
            "low": "Hard to trade - wide spreads and potential slippage. Use small positions and limit orders only.",
            "unknown": "Liquidity data unavailable for this stock.",
        }
        return descriptions.get(liquidity_class, "Unknown liquidity")

    @staticmethod
    def _get_trading_advice(liquidity_class: str) -> str:
        """Get trading advice based on liquidity."""
        advice = {
            "high": "Safe for all position sizes. Market orders acceptable for normal-sized trades.",
            "moderate": "Use limit orders for positions. Consider impact on spreads for larger trades.",
            "low": "Always use limit orders. Keep position sizes small. Avoid during low-volume periods (open/close). Consider alternatives with better liquidity.",
            "unknown": "Exercise caution - verify liquidity before trading.",
        }
        return advice.get(liquidity_class, "Assess liquidity carefully")

    @staticmethod
    def _get_intermediate_interpretation(
        liquidity_class: str,
        liq_rank: Optional[float],
        rvol: Optional[float],
    ) -> str:
        """Get intermediate-level interpretation."""
        base = f"Liquidity rank: {round(liq_rank)}th percentile" if liq_rank else "Liquidity rank unknown"

        volume_context = ""
        if rvol is not None:
            if rvol > 1.5:
                volume_context = ". Today's volume is well above average - exceptionally liquid today."
            elif rvol < 0.5:
                volume_context = ". Today's volume is below average - be cautious with execution."

        return f"{base}{volume_context}"
