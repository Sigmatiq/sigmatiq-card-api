"""
Ticker Trend Analysis Handler.

Provides trend strength analysis using moving averages, ADX, and momentum indicators.
"""

from datetime import date
from typing import Any, Optional

import asyncpg
from fastapi import HTTPException

from .base import BaseCardHandler
from ..models.cards import CardMode


class TickerTrendHandler(BaseCardHandler):
    """Handler for ticker_trend card."""

    async def fetch(
        self, mode: CardMode, symbol: Optional[str], trading_date: date
    ) -> dict[str, Any]:
        """
        Fetch ticker trend analysis data.

        Data source: sb.symbol_derived_eod
        """
        if not symbol:
            raise HTTPException(status_code=400, detail="Symbol is required for ticker_trend card")

        query = """
            SELECT symbol, close, r_1d_pct, r_5d_pct, r_1m_pct,
                   dist_ma20, dist_ma50, dist_ma200,
                   rsi_14, macd, macd_signal, macd_hist,
                   atr_pct, volume, rvol
            FROM sb.symbol_derived_eod
            WHERE symbol = $1 AND trading_date = $2
        """

        row = await self._fetch_one(
            query, {"symbol": symbol.upper(), "trading_date": trading_date}
        )

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No trend data available for {symbol} on {trading_date}",
            )

        if mode == CardMode.beginner:
            return self._format_beginner(symbol, row)
        elif mode == CardMode.intermediate:
            return self._format_intermediate(symbol, row)
        else:
            return self._format_advanced(symbol, row)

    def _format_beginner(self, symbol: str, row: asyncpg.Record) -> dict[str, Any]:
        """Beginner: Simple trend direction with emoji."""
        close = float(row["close"]) if row["close"] else 0
        dist_ma50 = float(row["dist_ma50"]) if row["dist_ma50"] else 0
        r_1m_pct = float(row["r_1m_pct"]) if row["r_1m_pct"] else 0

        # Determine trend
        trend = self._determine_simple_trend(dist_ma50, r_1m_pct)

        trend_labels = {
            "strong_up": "🚀 Strong Uptrend",
            "up": "📈 Uptrend",
            "neutral": "➡️ Sideways",
            "down": "📉 Downtrend",
            "strong_down": "⬇️ Strong Downtrend",
        }

        trend_explanations = {
            "strong_up": f"{symbol} is in a powerful uptrend. Price is well above its average and rising fast.",
            "up": f"{symbol} is trending up. Price is above its average and moving higher.",
            "neutral": f"{symbol} is moving sideways. No clear direction right now.",
            "down": f"{symbol} is trending down. Price is below its average and falling.",
            "strong_down": f"{symbol} is in a steep downtrend. Price is well below its average and dropping fast.",
        }

        trend_advice = {
            "strong_up": "Look for dips to buy. Let winners run. Use trailing stops.",
            "up": "Good time to hold or buy on pullbacks. Trend is your friend.",
            "neutral": "Wait for a breakout. No edge in sideways markets.",
            "down": "Be cautious. Consider selling rallies or staying out.",
            "strong_down": "Avoid or wait for stabilization. Falling knives are dangerous.",
        }

        return {
            "symbol": symbol,
            "price": f"${close:.2f}",
            "trend": self._clean_trend_label(trend),
            "explanation": trend_explanations[trend],
            "what_to_do": trend_advice[trend],
            "tip": self._add_educational_tip("ticker_trend", CardMode.beginner),
            "trend_clean": self._clean_trend_label(trend),
            "action_block": self._build_action_block_basic(trend),
        }

    def _format_intermediate(self, symbol: str, row: asyncpg.Record) -> dict[str, Any]:
        """Intermediate: Trend with technical indicators."""
        close = float(row["close"]) if row["close"] else None
        dist_ma20 = float(row["dist_ma20"]) if row["dist_ma20"] else None
        dist_ma50 = float(row["dist_ma50"]) if row["dist_ma50"] else None
        dist_ma200 = float(row["dist_ma200"]) if row["dist_ma200"] else None
        rsi_14 = float(row["rsi_14"]) if row["rsi_14"] else None
        macd = float(row["macd"]) if row["macd"] else None
        macd_signal = float(row["macd_signal"]) if row["macd_signal"] else None
        macd_hist = float(row["macd_hist"]) if row["macd_hist"] else None
        r_1m_pct = float(row["r_1m_pct"]) if row["r_1m_pct"] else None

        trend_strength = self._calculate_trend_strength(dist_ma50, r_1m_pct)

        return {
            "symbol": symbol,
            "price": close,
            "trend_strength": trend_strength,
            "moving_averages": {
                "vs_20d_pct": dist_ma20,
                "vs_50d_pct": dist_ma50,
                "vs_200d_pct": dist_ma200,
                "alignment": self._check_ma_alignment(dist_ma20, dist_ma50, dist_ma200),
            },
            "momentum": {
                "rsi_14": rsi_14,
                "macd": macd,
                "macd_signal": macd_signal,
                "macd_histogram": macd_hist,
                "macd_crossover": self._detect_macd_cross(macd, macd_signal, macd_hist),
            },
            "performance_1m_pct": r_1m_pct,
            "signals": self._generate_trend_signals(
                dist_ma20, dist_ma50, dist_ma200, rsi_14, macd_hist
            ),
            "action_block": self._build_action_block_intermediate(dist_ma20, dist_ma50, rsi_14, macd_hist),
        }

    def _format_advanced(self, symbol: str, row: asyncpg.Record) -> dict[str, Any]:
        """Advanced: Full trend data with volatility."""
        return {
            "symbol": symbol,
            "price_data": {
                "close": float(row["close"]) if row["close"] else None,
                "r_1d_pct": float(row["r_1d_pct"]) if row["r_1d_pct"] else None,
                "r_5d_pct": float(row["r_5d_pct"]) if row["r_5d_pct"] else None,
                "r_1m_pct": float(row["r_1m_pct"]) if row["r_1m_pct"] else None,
            },
            "moving_averages": {
                "dist_ma20_pct": float(row["dist_ma20"]) if row["dist_ma20"] else None,
                "dist_ma50_pct": float(row["dist_ma50"]) if row["dist_ma50"] else None,
                "dist_ma200_pct": float(row["dist_ma200"]) if row["dist_ma200"] else None,
            },
            "oscillators": {
                "rsi_14": float(row["rsi_14"]) if row["rsi_14"] else None,
                "macd": float(row["macd"]) if row["macd"] else None,
                "macd_signal": float(row["macd_signal"]) if row["macd_signal"] else None,
                "macd_hist": float(row["macd_hist"]) if row["macd_hist"] else None,
            },
            "volatility": {
                "atr_pct": float(row["atr_pct"]) if row["atr_pct"] else None,
            },
            "volume": {
                "absolute": int(row["volume"]) if row["volume"] else None,
                "relative": float(row["rvol"]) if row["rvol"] else None,
            },
            "raw_data": dict(row),
        }

    def _determine_simple_trend(self, dist_ma50: float, r_1m_pct: float) -> str:
        """Determine simple trend category."""
        if dist_ma50 > 10 and r_1m_pct > 10:
            return "strong_up"
        elif dist_ma50 > 2 and r_1m_pct > 0:
            return "up"
        elif dist_ma50 < -10 and r_1m_pct < -10:
            return "strong_down"
        elif dist_ma50 < -2 and r_1m_pct < 0:
            return "down"
        else:
            return "neutral"

    def _calculate_trend_strength(
        self, dist_ma50: Optional[float], r_1m_pct: Optional[float]
    ) -> str:
        """Calculate trend strength label."""
        if dist_ma50 is None:
            return "Unknown"

        if abs(dist_ma50) > 15:
            return "Very Strong"
        elif abs(dist_ma50) > 8:
            return "Strong"
        elif abs(dist_ma50) > 3:
            return "Moderate"
        else:
            return "Weak"

    def _check_ma_alignment(
        self,
        dist_ma20: Optional[float],
        dist_ma50: Optional[float],
        dist_ma200: Optional[float],
    ) -> str:
        """Check if moving averages are aligned (bullish/bearish)."""
        if dist_ma20 is None or dist_ma50 is None or dist_ma200 is None:
            return "Incomplete"

        # Bullish: price > MA20 > MA50 > MA200
        if dist_ma20 > 0 and dist_ma50 > 0 and dist_ma200 > 0:
            return "Bullish (price above all MAs)"
        # Bearish: price < MA20 < MA50 < MA200
        elif dist_ma20 < 0 and dist_ma50 < 0 and dist_ma200 < 0:
            return "Bearish (price below all MAs)"
        else:
            return "Mixed (no clear alignment)"

    def _clean_trend_label(self, trend: str) -> str:
        """Return a clean ASCII trend label for the given trend key."""
        mapping = {
            "strong_up": "Strong Uptrend",
            "up": "Uptrend",
            "neutral": "Sideways",
            "down": "Downtrend",
            "strong_down": "Strong Downtrend",
        }
        return mapping.get(trend, trend)

    def _build_action_block_basic(self, trend: str) -> dict[str, Any]:
        """Basic action guidance by trend category."""
        if trend in ("strong_up", "up"):
            return {
                "entry": "Buy pullbacks in trend",
                "invalidation": "Lose 20-day with momentum rollover",
                "risk_note": "Use ATR-based stops",
                "targets": ["+1R", "+2R"],
                "confidence": 70 if trend == "up" else 80,
            }
        if trend in ("strong_down", "down"):
            return {
                "entry": "Avoid longs; if shorting, sell rallies into resistance",
                "invalidation": "Reclaim of 20-day",
                "risk_note": "Define risk strictly",
                "targets": ["+1R"],
                "confidence": 70 if trend == "down" else 80,
            }
        return {
            "entry": "Wait for breakout from range",
            "invalidation": "N/A",
            "risk_note": "No edge in sideways markets",
            "targets": [],
            "confidence": 50,
        }

    def _build_action_block_intermediate(
        self,
        dist_ma20: Optional[float],
        dist_ma50: Optional[float],
        rsi_14: Optional[float],
        macd_hist: Optional[float],
    ) -> dict[str, Any]:
        """Action guidance with simple confluence scoring."""
        trend_up = (dist_ma20 or 0) > 0 and (dist_ma50 or 0) > 0
        momentum_ok = (rsi_14 or 0) >= 50 and (macd_hist or 0) > 0
        entry = (
            "Buy pullback to 20-day with RSI>50"
            if trend_up and momentum_ok
            else "Wait for reclaim of 20-day with momentum turn"
        )
        confidence = 80 if trend_up and momentum_ok else 55 if trend_up else 40
        return {
            "entry": entry,
            "invalidation": "Below 20-day − ~1×ATR",
            "risk_note": "Use ATR% for sizing (1%/stop%)",
            "targets": ["+1R", "+2R"],
            "confidence": confidence,
        }

    def _detect_macd_cross(
        self,
        macd: Optional[float],
        macd_signal: Optional[float],
        macd_hist: Optional[float],
    ) -> Optional[str]:
        """Detect MACD crossover signals."""
        if macd is None or macd_signal is None or macd_hist is None:
            return None

        # Recent crossover if histogram is small but MACD above signal
        if macd > macd_signal and abs(macd_hist) < 0.5:
            return "Bullish crossover (recent)"
        elif macd < macd_signal and abs(macd_hist) < 0.5:
            return "Bearish crossover (recent)"
        elif macd > macd_signal:
            return "Bullish (MACD above signal)"
        else:
            return "Bearish (MACD below signal)"

    def _generate_trend_signals(
        self,
        dist_ma20: Optional[float],
        dist_ma50: Optional[float],
        dist_ma200: Optional[float],
        rsi_14: Optional[float],
        macd_hist: Optional[float],
    ) -> list[str]:
        """Generate actionable trend signals."""
        signals = []

        # MA signals
        if dist_ma50 and dist_ma50 > 5:
            signals.append("Price well above 50-day MA - strong uptrend")
        elif dist_ma50 and dist_ma50 < -5:
            signals.append("Price well below 50-day MA - strong downtrend")

        # Golden/Death cross approximation
        if dist_ma50 and dist_ma200:
            if dist_ma50 > 0 and dist_ma200 < 0:
                signals.append("Emerging bullish trend (50d crossing above 200d)")
            elif dist_ma50 < 0 and dist_ma200 > 0:
                signals.append("Emerging bearish trend (50d crossing below 200d)")

        # RSI signals
        if rsi_14:
            if rsi_14 > 70:
                signals.append("RSI overbought (>70) - potential pullback")
            elif rsi_14 < 30:
                signals.append("RSI oversold (<30) - potential bounce")

        # MACD momentum
        if macd_hist:
            if macd_hist > 0:
                signals.append("MACD bullish - upward momentum")
            else:
                signals.append("MACD bearish - downward momentum")

        return signals if signals else ["No clear signals"]
