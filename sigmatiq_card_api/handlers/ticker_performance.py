"""
Ticker Performance card handler.

Provides single stock analysis: price change, volume, technical indicators.
"""

from datetime import date
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class TickerPerformanceHandler(BaseCardHandler):
    """Handler for ticker performance card."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Fetch ticker performance data.

        Args:
            mode: Complexity level
            symbol: Stock symbol (required)
            trading_date: Trading date

        Returns:
            Formatted ticker performance data

        Raises:
            ValueError: If symbol not provided
            HTTPException: If data not found
        """
        if not symbol:
            raise ValueError("Symbol is required for ticker_performance card")

        # Query symbol-specific data
        query = """
            SELECT
                symbol,
                close,
                r_1d_pct,
                volume,
                rvol,
                atr_pct,
                rsi_14,
                macd,
                macd_signal,
                bb_position,
                dist_ma20,
                dist_ma50,
                dist_ma200
            FROM sb.symbol_derived_eod
            WHERE symbol = $1 AND trading_date = $2
        """

        row = await self._fetch_one(query, {"symbol": symbol.upper(), "trading_date": trading_date})

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No data available for {symbol} on {trading_date}",
            )

        # Extract values
        close = row["close"] or 0
        r_1d_pct = row["r_1d_pct"] or 0
        volume = row["volume"] or 0
        rvol = row["rvol"] or 1.0
        atr_pct = row["atr_pct"] or 0
        rsi_14 = row["rsi_14"] or 50
        macd = row["macd"] or 0
        macd_signal = row["macd_signal"] or 0
        bb_position = row["bb_position"] or 0.5
        dist_ma20 = row["dist_ma20"] or 0
        dist_ma50 = row["dist_ma50"] or 0
        dist_ma200 = row["dist_ma200"] or 0

        # Format based on mode
        if mode == CardMode.beginner:
            return self._format_beginner(
                symbol=symbol.upper(),
                close=close,
                r_1d_pct=r_1d_pct,
                volume=volume,
                rvol=rvol,
                rsi_14=rsi_14,
            )

        elif mode == CardMode.intermediate:
            return self._format_intermediate(
                symbol=symbol.upper(),
                close=close,
                r_1d_pct=r_1d_pct,
                volume=volume,
                rvol=rvol,
                atr_pct=atr_pct,
                rsi_14=rsi_14,
                macd=macd,
                macd_signal=macd_signal,
                dist_ma20=dist_ma20,
                dist_ma50=dist_ma50,
            )

        else:  # advanced
            return self._format_advanced(row)

    def _format_beginner(
        self,
        symbol: str,
        close: float,
        r_1d_pct: float,
        volume: int,
        rvol: float,
        rsi_14: float,
    ) -> dict[str, Any]:
        """Format for beginner mode (simplified, plain language)."""
        # Determine price direction
        if r_1d_pct > 0:
            price_direction = "up"
            price_emoji = "↑"
        elif r_1d_pct < 0:
            price_direction = "down"
            price_emoji = "↓"
        else:
            price_direction = "flat"
            price_emoji = "→"

        # Volume assessment
        if rvol > 1.5:
            volume_status = "high"
            volume_label = f"{rvol:.1f}x normal volume (strong interest)"
        elif rvol < 0.7:
            volume_status = "low"
            volume_label = f"{rvol:.1f}x normal volume (light trading)"
        else:
            volume_status = "normal"
            volume_label = f"{rvol:.1f}x normal volume"

        # RSI assessment
        if rsi_14 > 70:
            momentum = "overbought"
            momentum_label = f"RSI {rsi_14:.0f} - May be overbought (consider taking profits)"
        elif rsi_14 < 30:
            momentum = "oversold"
            momentum_label = f"RSI {rsi_14:.0f} - May be oversold (potential bounce)"
        else:
            momentum = "neutral"
            momentum_label = f"RSI {rsi_14:.0f} - Momentum is neutral"

        return {
            "symbol": symbol,
            "price": close,
            "price_change_pct": r_1d_pct,
            "price_label": f"{price_emoji} {abs(r_1d_pct):.2f}% {price_direction} today",
            "volume": volume,
            "volume_status": volume_status,
            "volume_label": volume_label,
            "momentum": momentum,
            "momentum_label": momentum_label,
            "educational_tip": self._add_educational_tip("ticker_performance", CardMode.beginner),
        }

    def _format_intermediate(
        self,
        symbol: str,
        close: float,
        r_1d_pct: float,
        volume: int,
        rvol: float,
        atr_pct: float,
        rsi_14: float,
        macd: float,
        macd_signal: float,
        dist_ma20: float,
        dist_ma50: float,
    ) -> dict[str, Any]:
        """Format for intermediate mode (more technical terms)."""
        # MACD interpretation
        macd_cross = macd - macd_signal
        if macd_cross > 0:
            macd_status = "bullish"
        elif macd_cross < 0:
            macd_status = "bearish"
        else:
            macd_status = "neutral"

        # Moving average trend
        above_ma20 = dist_ma20 > 0
        above_ma50 = dist_ma50 > 0

        if above_ma20 and above_ma50:
            trend = "uptrend"
        elif not above_ma20 and not above_ma50:
            trend = "downtrend"
        else:
            trend = "mixed"

        return {
            "symbol": symbol,
            "price": close,
            "r_1d_pct": r_1d_pct,
            "volume": volume,
            "rvol": rvol,
            "atr_pct": atr_pct,
            "volatility": "high" if atr_pct > 3 else "low" if atr_pct < 1 else "normal",
            "rsi_14": rsi_14,
            "macd": macd,
            "macd_signal": macd_signal,
            "macd_status": macd_status,
            "dist_ma20": dist_ma20,
            "dist_ma50": dist_ma50,
            "above_ma20": above_ma20,
            "above_ma50": above_ma50,
            "trend": trend,
            "summary": self._get_intermediate_summary(
                r_1d_pct, rvol, rsi_14, macd_status, trend
            ),
        }

    def _format_advanced(self, row: Any) -> dict[str, Any]:
        """Format for advanced mode (all fields, no labels)."""
        return {
            "symbol": row["symbol"],
            "close": row["close"],
            "r_1d_pct": row["r_1d_pct"],
            "volume": row["volume"],
            "rvol": row["rvol"],
            "atr_pct": row["atr_pct"],
            "rsi_14": row["rsi_14"],
            "macd": row["macd"],
            "macd_signal": row["macd_signal"],
            "macd_hist": (row["macd"] or 0) - (row["macd_signal"] or 0),
            "bb_position": row["bb_position"],
            "dist_ma20": row["dist_ma20"],
            "dist_ma50": row["dist_ma50"],
            "dist_ma200": row["dist_ma200"],
        }

    def _get_intermediate_summary(
        self, r_1d_pct: float, rvol: float, rsi_14: float, macd_status: str, trend: str
    ) -> str:
        """Generate summary for intermediate mode."""
        parts = []

        # Price action
        if abs(r_1d_pct) > 2:
            parts.append(f"Strong {'up' if r_1d_pct > 0 else 'down'} move ({r_1d_pct:+.2f}%)")
        elif abs(r_1d_pct) > 1:
            parts.append(f"Moderate {'gain' if r_1d_pct > 0 else 'loss'} ({r_1d_pct:+.2f}%)")
        else:
            parts.append(f"Minimal change ({r_1d_pct:+.2f}%)")

        # Volume
        if rvol > 1.5:
            parts.append("on heavy volume")
        elif rvol < 0.7:
            parts.append("on light volume")

        # Technical alignment
        if macd_status == trend != "mixed":
            parts.append(f"with aligned {trend} signals")
        elif macd_status != trend:
            parts.append("with mixed technical signals")

        # RSI extremes
        if rsi_14 > 70:
            parts.append("(overbought territory)")
        elif rsi_14 < 30:
            parts.append("(oversold territory)")

        return " ".join(parts)
