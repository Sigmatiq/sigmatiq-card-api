"""
Ticker 52-Week Range Handler.

Provides 52-week high/low analysis with current price context.
"""

from datetime import date
from typing import Any, Optional

import asyncpg
from fastapi import HTTPException

from .base import BaseCardHandler
from ..models.cards import CardMode


class Ticker52WHandler(BaseCardHandler):
    """Handler for ticker_52w card."""

    async def fetch(
        self, mode: CardMode, symbol: Optional[str], trading_date: date
    ) -> dict[str, Any]:
        """
        Fetch 52-week range data.

        Data sources:
        - sb.symbol_52w_levels: high_52w, low_52w
        - sb.symbol_derived_eod: current close
        """
        if not symbol:
            raise HTTPException(status_code=400, detail="Symbol is required for ticker_52w card")

        # Get 52w levels
        query_52w = """
            SELECT high_52w, low_52w
            FROM sb.symbol_52w_levels
            WHERE symbol = $1 AND trading_date = $2
        """

        row_52w = await self._fetch_one(
            query_52w, {"symbol": symbol.upper(), "trading_date": trading_date}
        )

        if not row_52w or not row_52w["high_52w"] or not row_52w["low_52w"]:
            raise HTTPException(
                status_code=404,
                detail=f"No 52-week data available for {symbol} on {trading_date}",
            )

        # Get current price
        query_price = """
            SELECT close, r_1d_pct, volume, rvol
            FROM sb.symbol_derived_eod
            WHERE symbol = $1 AND trading_date = $2
        """

        row_price = await self._fetch_one(
            query_price, {"symbol": symbol.upper(), "trading_date": trading_date}
        )

        if not row_price or not row_price["close"]:
            raise HTTPException(
                status_code=404,
                detail=f"No price data available for {symbol} on {trading_date}",
            )

        high_52w = float(row_52w["high_52w"])
        low_52w = float(row_52w["low_52w"])
        close = float(row_price["close"])
        r_1d_pct = float(row_price["r_1d_pct"]) if row_price["r_1d_pct"] else None
        volume = int(row_price["volume"]) if row_price["volume"] else None
        rvol = float(row_price["rvol"]) if row_price["rvol"] else None

        # Calculate position in range
        range_52w = high_52w - low_52w
        pct_from_high = ((high_52w - close) / high_52w) * 100 if high_52w > 0 else 0
        pct_from_low = ((close - low_52w) / low_52w) * 100 if low_52w > 0 else 0
        position_in_range = ((close - low_52w) / range_52w) * 100 if range_52w > 0 else 50

        if mode == CardMode.beginner:
            return self._format_beginner(
                symbol, close, high_52w, low_52w, position_in_range, pct_from_high, r_1d_pct
            )
        elif mode == CardMode.intermediate:
            return self._format_intermediate(
                symbol,
                close,
                high_52w,
                low_52w,
                position_in_range,
                pct_from_high,
                pct_from_low,
                r_1d_pct,
                volume,
                rvol,
            )
        else:
            return self._format_advanced(
                symbol,
                close,
                high_52w,
                low_52w,
                position_in_range,
                pct_from_high,
                pct_from_low,
                range_52w,
                r_1d_pct,
                volume,
                rvol,
            )

    def _format_beginner(
        self,
        symbol: str,
        close: float,
        high_52w: float,
        low_52w: float,
        position_in_range: float,
        pct_from_high: float,
        r_1d_pct: Optional[float],
    ) -> dict[str, Any]:
        """Beginner: Simple range visualization."""
        # Determine position label
        if position_in_range >= 90:
            position_label = "📈 Near 52-Week High"
            interpretation = "Stock is trading close to its highest price in a year. It's strong!"
        elif position_in_range >= 70:
            position_label = "🟢 Upper Half of Range"
            interpretation = "Stock is in the upper part of its yearly range. Showing strength."
        elif position_in_range >= 30:
            position_label = "🟡 Middle of Range"
            interpretation = "Stock is in the middle of its yearly range. Not too high, not too low."
        elif position_in_range >= 10:
            position_label = "🔴 Lower Half of Range"
            interpretation = "Stock is in the lower part of its yearly range. Has been weak."
        else:
            position_label = "📉 Near 52-Week Low"
            interpretation = "Stock is trading close to its lowest price in a year. Very weak."

        return {
            "symbol": symbol,
            "current_price": f"${close:.2f}",
            "range_52w": f"${low_52w:.2f} - ${high_52w:.2f}",
            "position": position_label,
            "percent_from_high": f"{pct_from_high:.1f}% below high",
            "interpretation": interpretation,
            "tip": "Stocks near 52-week highs are often strong. Stocks near lows may be weak or value opportunities.",
        }

    def _format_intermediate(
        self,
        symbol: str,
        close: float,
        high_52w: float,
        low_52w: float,
        position_in_range: float,
        pct_from_high: float,
        pct_from_low: float,
        r_1d_pct: Optional[float],
        volume: Optional[int],
        rvol: Optional[float],
    ) -> dict[str, Any]:
        """Intermediate: Detailed range analysis."""
        return {
            "symbol": symbol,
            "price_action": {
                "close": close,
                "change_1d_pct": r_1d_pct,
                "high_52w": high_52w,
                "low_52w": low_52w,
            },
            "range_metrics": {
                "position_pct": round(position_in_range, 1),
                "from_high_pct": round(pct_from_high, 1),
                "from_low_pct": round(pct_from_low, 1),
            },
            "volume": {"today": volume, "relative": rvol},
            "signals": self._generate_signals(position_in_range, pct_from_high, rvol),
        }

    def _format_advanced(
        self,
        symbol: str,
        close: float,
        high_52w: float,
        low_52w: float,
        position_in_range: float,
        pct_from_high: float,
        pct_from_low: float,
        range_52w: float,
        r_1d_pct: Optional[float],
        volume: Optional[int],
        rvol: Optional[float],
    ) -> dict[str, Any]:
        """Advanced: Full range data with support/resistance."""
        return {
            "symbol": symbol,
            "close": close,
            "change_1d_pct": r_1d_pct,
            "range_52w": {
                "high": high_52w,
                "low": low_52w,
                "range_dollars": range_52w,
                "position_pct": position_in_range,
            },
            "distance_metrics": {
                "from_high_pct": pct_from_high,
                "from_low_pct": pct_from_low,
                "from_high_dollars": high_52w - close,
                "from_low_dollars": close - low_52w,
            },
            "volume": {"absolute": volume, "relative": rvol},
            "key_levels": {
                "resistance": high_52w,
                "support": low_52w,
                "midpoint": (high_52w + low_52w) / 2,
            },
            "breakout_watch": pct_from_high < 5 and (rvol or 0) > 1.5,
        }

    def _generate_signals(
        self, position_in_range: float, pct_from_high: float, rvol: Optional[float]
    ) -> list[str]:
        """Generate trading signals."""
        signals = []

        # Near 52w high
        if position_in_range >= 95:
            signals.append("At 52-week high - potential breakout setup")
        elif position_in_range >= 85:
            signals.append("Near 52-week high - strong momentum")

        # Near 52w low
        if position_in_range <= 5:
            signals.append("At 52-week low - potential oversold bounce or breakdown")
        elif position_in_range <= 15:
            signals.append("Near 52-week low - weak or potential value opportunity")

        # Volume confirmation
        if rvol and rvol > 2 and pct_from_high < 10:
            signals.append("High volume near highs - breakout potential")

        # Middle of range
        if 40 <= position_in_range <= 60:
            signals.append("Mid-range - no clear technical edge")

        return signals if signals else ["No notable signals"]
