"""
Volume Profile Handler.

Provides volume analysis including relative volume, volume trends, and unusual activity.
"""

from datetime import date
from typing import Any, Optional

import asyncpg
from fastapi import HTTPException

from .base import BaseCardHandler
from ..models.cards import CardMode


class VolumeProfileHandler(BaseCardHandler):
    """Handler for volume_profile card."""

    async def fetch(
        self, mode: CardMode, symbol: Optional[str], trading_date: date
    ) -> dict[str, Any]:
        """
        Fetch volume profile data.

        Data source: sb.symbol_derived_eod
        """
        if not symbol:
            raise HTTPException(
                status_code=400, detail="Symbol is required for volume_profile card"
            )

        query = """
            SELECT symbol, close, r_1d_pct, volume, rvol,
                   dist_ma20, dist_ma50
            FROM sb.symbol_derived_eod
            WHERE symbol = $1 AND trading_date = $2
        """

        row = await self._fetch_one(
            query, {"symbol": symbol.upper(), "trading_date": trading_date}
        )

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No volume data available for {symbol} on {trading_date}",
            )

        if mode == CardMode.beginner:
            return self._format_beginner(symbol, row)
        elif mode == CardMode.intermediate:
            return self._format_intermediate(symbol, row)
        else:
            return self._format_advanced(symbol, row)

    def _format_beginner(self, symbol: str, row: asyncpg.Record) -> dict[str, Any]:
        """Beginner: Simple volume interpretation."""
        volume = int(row["volume"]) if row["volume"] else 0
        rvol = float(row["rvol"]) if row["rvol"] else 1.0
        r_1d_pct = float(row["r_1d_pct"]) if row["r_1d_pct"] else 0
        close = float(row["close"]) if row["close"] else 0

        # Categorize volume
        if rvol >= 2.5:
            volume_label = "🔥 Very High Volume"
            explanation = f"{symbol} is seeing explosive trading activity - {rvol:.1f}x normal!"
        elif rvol >= 1.5:
            volume_label = "📊 High Volume"
            explanation = f"{symbol} is trading with above-average interest - {rvol:.1f}x normal."
        elif rvol >= 0.75:
            volume_label = "➡️ Normal Volume"
            explanation = f"{symbol} is trading at typical volume levels."
        else:
            volume_label = "💤 Low Volume"
            explanation = f"{symbol} is trading quietly - only {rvol:.1f}x normal volume."

        # Interpret volume with price
        if rvol >= 1.5:
            if r_1d_pct > 2:
                signal = "✅ Bullish confirmation - price rising on high volume"
            elif r_1d_pct < -2:
                signal = "⚠️ Bearish pressure - price falling on high volume"
            else:
                signal = "❓ High volume but no clear direction"
        else:
            signal = "Low volume - moves may not be reliable"

        return {
            "symbol": symbol,
            "price": f"${close:.2f}",
            "price_change": f"{r_1d_pct:+.2f}%",
            "volume_label": volume_label,
            "volume_vs_avg": f"{rvol:.1f}x",
            "explanation": explanation,
            "signal": signal,
            "tip": "High volume confirms price moves. Low volume moves are less reliable.",
        }

    def _format_intermediate(self, symbol: str, row: asyncpg.Record) -> dict[str, Any]:
        """Intermediate: Detailed volume analysis."""
        volume = int(row["volume"]) if row["volume"] else None
        rvol = float(row["rvol"]) if row["rvol"] else None
        r_1d_pct = float(row["r_1d_pct"]) if row["r_1d_pct"] else None
        close = float(row["close"]) if row["close"] else None
        dist_ma20 = float(row["dist_ma20"]) if row["dist_ma20"] else None
        dist_ma50 = float(row["dist_ma50"]) if row["dist_ma50"] else None

        # Calculate volume metrics
        volume_category = self._categorize_volume(rvol)
        price_volume_relationship = self._analyze_price_volume(r_1d_pct, rvol)

        # Detect patterns
        patterns = self._detect_volume_patterns(rvol, r_1d_pct, dist_ma20)

        return {
            "symbol": symbol,
            "price": close,
            "price_change_pct": r_1d_pct,
            "volume": {
                "absolute": volume,
                "relative": rvol,
                "category": volume_category,
            },
            "analysis": {
                "price_volume_relationship": price_volume_relationship,
                "trend_confirmation": self._check_trend_confirmation(
                    dist_ma20, dist_ma50, rvol
                ),
            },
            "patterns": patterns,
            "signals": self._generate_volume_signals(rvol, r_1d_pct, dist_ma20),
        }

    def _format_advanced(self, symbol: str, row: asyncpg.Record) -> dict[str, Any]:
        """Advanced: Full volume data with statistics."""
        volume = int(row["volume"]) if row["volume"] else None
        rvol = float(row["rvol"]) if row["rvol"] else None
        r_1d_pct = float(row["r_1d_pct"]) if row["r_1d_pct"] else None

        return {
            "symbol": symbol,
            "volume_data": {
                "today": volume,
                "relative": rvol,
                "avg_volume": int(volume / rvol) if volume and rvol and rvol > 0 else None,
            },
            "price_data": {
                "close": float(row["close"]) if row["close"] else None,
                "change_pct": r_1d_pct,
                "dist_ma20_pct": float(row["dist_ma20"]) if row["dist_ma20"] else None,
                "dist_ma50_pct": float(row["dist_ma50"]) if row["dist_ma50"] else None,
            },
            "volume_analysis": {
                "category": self._categorize_volume(rvol),
                "z_score": self._calculate_volume_zscore(rvol),
                "percentile": self._volume_percentile(rvol),
            },
            "price_volume_correlation": self._analyze_price_volume(r_1d_pct, rvol),
            "raw_data": dict(row),
        }

    def _categorize_volume(self, rvol: Optional[float]) -> str:
        """Categorize volume level."""
        if rvol is None:
            return "Unknown"
        if rvol >= 3.0:
            return "Extreme"
        elif rvol >= 2.0:
            return "Very High"
        elif rvol >= 1.5:
            return "High"
        elif rvol >= 0.75:
            return "Normal"
        elif rvol >= 0.5:
            return "Low"
        else:
            return "Very Low"

    def _analyze_price_volume(
        self, price_change: Optional[float], rvol: Optional[float]
    ) -> str:
        """Analyze price-volume relationship."""
        if price_change is None or rvol is None:
            return "Insufficient data"

        if rvol >= 1.5:
            if price_change > 2:
                return "Bullish (accumulation on strength)"
            elif price_change > 0:
                return "Mildly bullish (buying interest)"
            elif price_change < -2:
                return "Bearish (distribution on weakness)"
            else:
                return "Mildly bearish (selling pressure)"
        else:
            if abs(price_change) > 2:
                return "Questionable (large move on light volume)"
            else:
                return "Neutral (low conviction)"

    def _detect_volume_patterns(
        self,
        rvol: Optional[float],
        price_change: Optional[float],
        dist_ma20: Optional[float],
    ) -> list[str]:
        """Detect volume-based patterns."""
        patterns = []

        if rvol and rvol >= 2.5:
            patterns.append("Volume spike detected")

        if rvol and price_change:
            if rvol >= 1.5 and price_change > 3:
                patterns.append("Breakout with volume confirmation")
            elif rvol >= 1.5 and price_change < -3:
                patterns.append("Breakdown with volume confirmation")

        if rvol and rvol < 0.5:
            patterns.append("Low conviction move (light volume)")

        if dist_ma20 and rvol:
            if abs(dist_ma20) > 5 and rvol >= 2:
                patterns.append("Trend acceleration (high volume at extremes)")

        return patterns if patterns else ["No significant patterns"]

    def _check_trend_confirmation(
        self,
        dist_ma20: Optional[float],
        dist_ma50: Optional[float],
        rvol: Optional[float],
    ) -> str:
        """Check if volume confirms trend."""
        if dist_ma20 is None or rvol is None:
            return "Unable to assess"

        if dist_ma20 > 3 and rvol >= 1.2:
            return "Uptrend confirmed by volume"
        elif dist_ma20 < -3 and rvol >= 1.2:
            return "Downtrend confirmed by volume"
        elif abs(dist_ma20) > 3 and rvol < 0.8:
            return "Trend lacks volume support (weak)"
        else:
            return "No clear trend"

    def _generate_volume_signals(
        self,
        rvol: Optional[float],
        price_change: Optional[float],
        dist_ma20: Optional[float],
    ) -> list[str]:
        """Generate trading signals based on volume."""
        signals = []

        if rvol and rvol >= 2.5:
            signals.append("Unusual volume spike - watch for follow-through")

        if rvol and price_change:
            if rvol >= 1.5 and price_change > 2:
                signals.append("Strong buying pressure - bullish")
            elif rvol >= 1.5 and price_change < -2:
                signals.append("Strong selling pressure - bearish")

        if rvol and rvol < 0.6:
            signals.append("Low volume - wait for confirmation")

        if dist_ma20 and rvol:
            if abs(dist_ma20) < 2 and rvol >= 2:
                signals.append("High volume near MAs - potential breakout/breakdown")

        return signals if signals else ["No clear signals"]

    def _calculate_volume_zscore(self, rvol: Optional[float]) -> Optional[float]:
        """Calculate approximate z-score for volume (simplified)."""
        if rvol is None:
            return None
        # Simplified: assume mean=1.0, stddev=0.5
        return (rvol - 1.0) / 0.5

    def _volume_percentile(self, rvol: Optional[float]) -> Optional[int]:
        """Estimate volume percentile (simplified)."""
        if rvol is None:
            return None
        if rvol >= 3.0:
            return 99
        elif rvol >= 2.0:
            return 95
        elif rvol >= 1.5:
            return 80
        elif rvol >= 1.0:
            return 50
        elif rvol >= 0.75:
            return 30
        else:
            return 10
