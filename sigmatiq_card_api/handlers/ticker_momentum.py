"""
Momentum Pulse Handler - Ticker-specific momentum indicators.

Shows key momentum indicators:
- RSI (Relative Strength Index)
- MACD histogram
- Stochastic oscillator
- Composite momentum classification

Data source: sb.symbol_indicators_daily
"""

from datetime import date
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class MomentumPulseHandler(BaseCardHandler):
    """Handler for ticker_momentum card - momentum indicators."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Fetch momentum indicators for the given symbol and trading date.

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
                detail="Symbol is required for ticker_momentum card",
            )

        # Fetch momentum indicators from database
        query = """
            SELECT rsi_14, macd, macd_signal, macd_histogram,
                   stoch_k, stoch_d
            FROM sb.symbol_indicators_daily
            WHERE trading_date = $1 AND symbol = $2
            LIMIT 1
        """
        row = await self._fetch_one(query, {"trading_date": trading_date, "symbol": symbol})

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No momentum data for {symbol} on {trading_date}",
            )

        # Extract indicator values
        rsi = float(row["rsi_14"]) if row["rsi_14"] is not None else None
        macd = float(row["macd"]) if row["macd"] is not None else None
        macd_signal = float(row["macd_signal"]) if row["macd_signal"] is not None else None
        macd_histogram = float(row["macd_histogram"]) if row["macd_histogram"] is not None else None
        stoch_k = float(row["stoch_k"]) if row["stoch_k"] is not None else None
        stoch_d = float(row["stoch_d"]) if row["stoch_d"] is not None else None

        # Classify momentum based on indicators
        momentum_classification = self._classify_momentum(rsi, macd_histogram, stoch_k)
        momentum_score = self._calculate_momentum_score(rsi, macd_histogram, stoch_k)

        # Format based on mode
        if mode == CardMode.beginner:
            return self._format_beginner(
                symbol,
                momentum_classification,
                momentum_score,
                rsi,
                macd_histogram,
                stoch_k,
            )
        elif mode == CardMode.intermediate:
            return self._format_intermediate(
                symbol,
                momentum_classification,
                momentum_score,
                rsi,
                macd,
                macd_signal,
                macd_histogram,
                stoch_k,
                stoch_d,
            )
        else:
            return self._format_advanced(
                symbol,
                momentum_classification,
                momentum_score,
                rsi,
                macd,
                macd_signal,
                macd_histogram,
                stoch_k,
                stoch_d,
            )

    @staticmethod
    def _classify_momentum(
        rsi: Optional[float],
        macd_hist: Optional[float],
        stoch_k: Optional[float],
    ) -> str:
        """
        Classify overall momentum based on indicator signals.

        Args:
            rsi: RSI value (0-100)
            macd_hist: MACD histogram value
            stoch_k: Stochastic %K value (0-100)

        Returns:
            Momentum classification: Strong Bullish, Moderate Bullish, Neutral, Weak, or Bearish
        """
        # Count bullish and bearish signals
        bullish_signals = 0
        bearish_signals = 0

        # RSI signals
        if rsi is not None:
            if rsi > 60:
                bullish_signals += 1
            elif rsi < 40:
                bearish_signals += 1

        # MACD histogram signals
        if macd_hist is not None:
            if macd_hist > 0:
                bullish_signals += 1
            else:
                bearish_signals += 1

        # Stochastic signals
        if stoch_k is not None:
            if stoch_k > 60:
                bullish_signals += 1
            elif stoch_k < 40:
                bearish_signals += 1

        # Classify based on signal counts
        if bullish_signals >= 2 and bearish_signals == 0:
            return "Strong Bullish"
        elif bullish_signals > bearish_signals:
            return "Moderate Bullish"
        elif bearish_signals >= 2 and bullish_signals == 0:
            return "Bearish"
        elif bearish_signals > bullish_signals:
            return "Weak"
        else:
            return "Neutral"

    @staticmethod
    def _calculate_momentum_score(
        rsi: Optional[float],
        macd_hist: Optional[float],
        stoch_k: Optional[float],
    ) -> int:
        """
        Calculate composite momentum score (0-100).

        Args:
            rsi: RSI value
            macd_hist: MACD histogram
            stoch_k: Stochastic %K

        Returns:
            Momentum score 0-100
        """
        score = 50  # Neutral default

        # RSI contribution (0-100 scale)
        if rsi is not None:
            score = (score + rsi) / 2

        # Stochastic contribution (0-100 scale)
        if stoch_k is not None:
            score = (score + stoch_k) / 2

        # MACD histogram contribution (normalize to 0-100)
        if macd_hist is not None:
            # Positive histogram boosts score, negative reduces it
            if macd_hist > 0:
                score = min(100, score + 10)
            else:
                score = max(0, score - 10)

        return round(score)

    def _format_beginner(
        self,
        symbol: str,
        classification: str,
        score: int,
        rsi: Optional[float],
        macd_hist: Optional[float],
        stoch_k: Optional[float],
    ) -> dict[str, Any]:
        """Format for beginner mode - simple classification and guidance."""
        # Get emoji for classification
        emoji = {
            "Strong Bullish": "🚀",
            "Moderate Bullish": "📈",
            "Neutral": "➡️",
            "Weak": "📉",
            "Bearish": "🔻",
        }.get(classification, "➡️")

        return {
            "symbol": symbol,
            "momentum_score": score,
            "momentum_label": f"{classification} Momentum",
            "simple_summary": self._get_beginner_summary(classification, rsi, macd_hist, stoch_k),
            "key_signals": self._get_key_signals_beginner(rsi, macd_hist, stoch_k),
            "action_block": self._build_action_block_beginner(symbol, classification),
        }

    def _build_action_block_beginner(self, symbol: str, classification: str) -> dict[str, Any]:
        """Action guidance based on momentum classification."""
        if classification == "Strong Bullish":
            entry = "Buy first pullback with RSI>50 and MACD>0"
            invalidation = "RSI<45 or MACD histogram < 0"
            confidence = 80
        elif classification == "Moderate Bullish":
            entry = "Buy pullback; wait for higher low or MACD turn"
            invalidation = "RSI<45 or price loses 20-day"
            confidence = 65
        elif classification == "Weak":
            entry = "Avoid longs; consider waiting or small mean-reversion only"
            invalidation = "N/A"
            confidence = 35
        elif classification == "Bearish":
            entry = "Avoid longs; if shorting, use defined risk"
            invalidation = "N/A"
            confidence = 25
        else:
            entry = "Wait for clearer momentum"
            invalidation = "N/A"
            confidence = 50
        return {
            "entry": entry,
            "invalidation": invalidation,
            "risk_note": "Use ATR-based stops from Performance card",
            "targets": ["+1R", "+2R"],
            "confidence": confidence,
        }

    def _format_intermediate(
        self,
        symbol: str,
        classification: str,
        score: int,
        rsi: Optional[float],
        macd: Optional[float],
        macd_signal: Optional[float],
        macd_hist: Optional[float],
        stoch_k: Optional[float],
        stoch_d: Optional[float],
    ) -> dict[str, Any]:
        """Format for intermediate mode - indicator breakdown."""
        return {
            "symbol": symbol,
            "momentum_score": score,
            "momentum_classification": classification,
            "indicators": {
                "rsi": {
                    "value": round(rsi, 2) if rsi is not None else None,
                    "signal": self._get_rsi_signal(rsi),
                    "interpretation": self._get_rsi_interpretation(rsi),
                },
                "macd": {
                    "macd": round(macd, 4) if macd is not None else None,
                    "signal": round(macd_signal, 4) if macd_signal is not None else None,
                    "histogram": round(macd_hist, 4) if macd_hist is not None else None,
                    "signal_type": "Bullish" if macd_hist and macd_hist > 0 else "Bearish" if macd_hist else "Neutral",
                },
                "stochastic": {
                    "k": round(stoch_k, 2) if stoch_k is not None else None,
                    "d": round(stoch_d, 2) if stoch_d is not None else None,
                    "signal": self._get_stoch_signal(stoch_k),
                },
            },
            "trading_guidance": self._get_trading_guidance(classification),
        }

    def _format_advanced(
        self,
        symbol: str,
        classification: str,
        score: int,
        rsi: Optional[float],
        macd: Optional[float],
        macd_signal: Optional[float],
        macd_hist: Optional[float],
        stoch_k: Optional[float],
        stoch_d: Optional[float],
    ) -> dict[str, Any]:
        """Format for advanced mode - full indicator details and divergence analysis."""
        return {
            "symbol": symbol,
            "composite_score": score,
            "classification": classification,
            "raw_indicators": {
                "rsi_14": round(rsi, 4) if rsi is not None else None,
                "macd": {
                    "value": round(macd, 6) if macd is not None else None,
                    "signal_line": round(macd_signal, 6) if macd_signal is not None else None,
                    "histogram": round(macd_hist, 6) if macd_hist is not None else None,
                    "crossover": "Bullish" if macd_hist and macd_hist > 0 else "Bearish" if macd_hist else None,
                },
                "stochastic": {
                    "percent_k": round(stoch_k, 4) if stoch_k is not None else None,
                    "percent_d": round(stoch_d, 4) if stoch_d is not None else None,
                    "crossover": self._detect_stoch_crossover(stoch_k, stoch_d),
                },
            },
            "signal_analysis": {
                "rsi": {
                    "zone": self._get_rsi_zone(rsi),
                    "signal": self._get_rsi_signal(rsi),
                    "strength": self._get_rsi_strength(rsi),
                },
                "macd": {
                    "trend": "Bullish" if macd_hist and macd_hist > 0 else "Bearish" if macd_hist else "Neutral",
                    "strength": abs(macd_hist) if macd_hist else 0,
                },
                "stochastic": {
                    "zone": self._get_stoch_zone(stoch_k),
                    "signal": self._get_stoch_signal(stoch_k),
                },
            },
            "thresholds": {
                "rsi": {"overbought": 70, "oversold": 30},
                "stochastic": {"overbought": 80, "oversold": 20},
            },
        }

    @staticmethod
    def _get_beginner_summary(
        classification: str,
        rsi: Optional[float],
        macd_hist: Optional[float],
        stoch_k: Optional[float],
    ) -> str:
        """Get plain-language summary for beginners."""
        summaries = {
            "Strong Bullish": "Strong upward momentum. Multiple indicators confirm buying pressure. Good for trend-following strategies.",
            "Moderate Bullish": "Positive momentum but not all indicators aligned. Watch for confirmation before entering positions.",
            "Neutral": "Mixed signals. Momentum unclear. Wait for clearer direction before trading.",
            "Weak": "Weakening momentum. Some bearish signals present. Consider reducing position size or tightening stops.",
            "Bearish": "Negative momentum. Multiple indicators show selling pressure. Avoid longs or consider shorts.",
        }
        return summaries.get(classification, "Momentum direction unclear.")

    @staticmethod
    def _get_key_signals_beginner(
        rsi: Optional[float],
        macd_hist: Optional[float],
        stoch_k: Optional[float],
    ) -> list[str]:
        """Get key signals in plain language for beginners."""
        signals = []

        if rsi is not None:
            if rsi > 70:
                signals.append("RSI overbought - stock may be overextended")
            elif rsi > 60:
                signals.append("RSI strong - good momentum")
            elif rsi < 30:
                signals.append("RSI oversold - stock may be due for bounce")
            elif rsi < 40:
                signals.append("RSI weak - momentum declining")

        if macd_hist is not None:
            if macd_hist > 0:
                signals.append("MACD bullish - buyers in control")
            else:
                signals.append("MACD bearish - sellers in control")

        if stoch_k is not None:
            if stoch_k > 80:
                signals.append("Stochastic overbought - caution on new longs")
            elif stoch_k < 20:
                signals.append("Stochastic oversold - potential reversal setup")

        return signals if signals else ["No clear signals - wait for better setup"]

    @staticmethod
    def _get_rsi_signal(rsi: Optional[float]) -> str:
        """Get RSI signal classification."""
        if rsi is None:
            return "No data"
        if rsi > 70:
            return "Overbought"
        elif rsi > 60:
            return "Strong"
        elif rsi < 30:
            return "Oversold"
        elif rsi < 40:
            return "Weak"
        else:
            return "Neutral"

    @staticmethod
    def _get_rsi_interpretation(rsi: Optional[float]) -> str:
        """Get RSI interpretation."""
        if rsi is None:
            return "No data"
        if rsi > 70:
            return "May be overextended, watch for reversal"
        elif rsi > 60:
            return "Positive momentum, trend likely continues"
        elif rsi < 30:
            return "Deeply oversold, potential bounce"
        elif rsi < 40:
            return "Weak momentum, avoid longs"
        else:
            return "Neutral zone, wait for clearer signal"

    @staticmethod
    def _get_rsi_zone(rsi: Optional[float]) -> str:
        """Get RSI zone classification."""
        if rsi is None:
            return "Unknown"
        if rsi > 70:
            return "Overbought (>70)"
        elif rsi < 30:
            return "Oversold (<30)"
        else:
            return f"Neutral ({round(rsi)})"

    @staticmethod
    def _get_rsi_strength(rsi: Optional[float]) -> str:
        """Get RSI strength assessment."""
        if rsi is None:
            return "Unknown"
        if rsi > 60:
            return "Strong"
        elif rsi < 40:
            return "Weak"
        else:
            return "Moderate"

    @staticmethod
    def _get_stoch_signal(stoch_k: Optional[float]) -> str:
        """Get Stochastic signal classification."""
        if stoch_k is None:
            return "No data"
        if stoch_k > 80:
            return "Overbought"
        elif stoch_k < 20:
            return "Oversold"
        else:
            return "Neutral"

    @staticmethod
    def _get_stoch_zone(stoch_k: Optional[float]) -> str:
        """Get Stochastic zone classification."""
        if stoch_k is None:
            return "Unknown"
        if stoch_k > 80:
            return "Overbought (>80)"
        elif stoch_k < 20:
            return "Oversold (<20)"
        else:
            return f"Neutral ({round(stoch_k)})"

    @staticmethod
    def _detect_stoch_crossover(stoch_k: Optional[float], stoch_d: Optional[float]) -> Optional[str]:
        """Detect Stochastic crossover (would need historical data for proper detection)."""
        if stoch_k is None or stoch_d is None:
            return None
        if stoch_k > stoch_d:
            return "Bullish (K>D)"
        else:
            return "Bearish (K<D)"

    @staticmethod
    def _get_trading_guidance(classification: str) -> str:
        """Get trading guidance based on momentum classification."""
        guidance = {
            "Strong Bullish": "Consider long positions or adding to existing longs. Momentum favors continuation.",
            "Moderate Bullish": "Selective longs on pullbacks. Wait for confirmation on breakouts.",
            "Neutral": "Stand aside or use tight stops. No clear edge in either direction.",
            "Weak": "Reduce position size. Tighten stops on longs. Consider profit-taking.",
            "Bearish": "Avoid new longs. Consider shorts or defensive positioning.",
        }
        return guidance.get(classification, "No clear guidance - assess risk carefully.")
