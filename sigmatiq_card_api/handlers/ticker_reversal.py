"""
Reversal Watch Handler - Overbought/oversold reversal signals.

Detects when stocks are extended and due for mean reversion:
- Overbought/oversold status
- Close position in day range
- Multiple oscillators (RSI, Stochastic)
- Distance from moving averages

Data sources:
- sb.symbol_derived_eod (overbought/oversold flags, z-score, range position)
- sb.symbol_indicators_daily (RSI, Stochastic, CCI)
"""

from datetime import date
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class ReversalWatchHandler(BaseCardHandler):
    """Handler for ticker_reversal card - reversal/mean reversion signals."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Fetch reversal signals for the given symbol and trading date.

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
                detail="Symbol is required for ticker_reversal card",
            )

        # Fetch reversal indicators
        query = """
            SELECT
                d.trading_date,
                d.symbol,
                d.is_overbought,
                d.is_oversold,
                d.close_position_in_range,
                d.dist_to_ma20_pct,
                d.zscore_20,
                i.rsi_14,
                i.stoch_k,
                i.stoch_d
            FROM sb.symbol_derived_eod d
            LEFT JOIN sb.symbol_indicators_daily i ON i.symbol = d.symbol AND i.trading_date = d.trading_date
            WHERE d.symbol = $1 AND d.trading_date = $2
            LIMIT 1
        """
        row = await self._fetch_one(query, {"symbol": symbol, "trading_date": trading_date})

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No reversal data for {symbol} on {trading_date}",
            )

        # Extract values
        is_overbought = bool(row["is_overbought"])
        is_oversold = bool(row["is_oversold"])
        close_pos_in_range = float(row["close_position_in_range"]) if row["close_position_in_range"] is not None else None
        dist_to_ma20 = float(row["dist_to_ma20_pct"]) if row["dist_to_ma20_pct"] is not None else None
        zscore = float(row["zscore_20"]) if row["zscore_20"] is not None else None
        rsi = float(row["rsi_14"]) if row["rsi_14"] is not None else None
        stoch_k = float(row["stoch_k"]) if row["stoch_k"] is not None else None
        stoch_d = float(row["stoch_d"]) if row["stoch_d"] is not None else None

        # Determine reversal status
        status = self._determine_status(is_overbought, is_oversold, rsi, stoch_k)
        confidence = self._assess_confidence(is_overbought, is_oversold, rsi, stoch_k, zscore)

        # Format based on mode
        if mode == CardMode.beginner:
            return self._format_beginner(
                symbol,
                status,
                confidence,
                rsi,
                close_pos_in_range,
            )
        elif mode == CardMode.intermediate:
            return self._format_intermediate(
                symbol,
                status,
                confidence,
                rsi,
                stoch_k,
                stoch_d,
                close_pos_in_range,
                dist_to_ma20,
            )
        else:
            return self._format_advanced(
                symbol,
                status,
                confidence,
                is_overbought,
                is_oversold,
                rsi,
                stoch_k,
                stoch_d,
                close_pos_in_range,
                dist_to_ma20,
                zscore,
            )

    @staticmethod
    def _determine_status(
        is_overbought: bool,
        is_oversold: bool,
        rsi: Optional[float],
        stoch_k: Optional[float],
    ) -> str:
        """Determine reversal status."""
        if is_overbought or (rsi and rsi > 70) or (stoch_k and stoch_k > 80):
            return "overbought"
        elif is_oversold or (rsi and rsi < 30) or (stoch_k and stoch_k < 20):
            return "oversold"
        else:
            return "neutral"

    @staticmethod
    def _assess_confidence(
        is_overbought: bool,
        is_oversold: bool,
        rsi: Optional[float],
        stoch_k: Optional[float],
        zscore: Optional[float],
    ) -> str:
        """Assess reversal signal confidence."""
        signals = 0

        # Count extreme signals
        if is_overbought or is_oversold:
            signals += 1
        if rsi and (rsi > 75 or rsi < 25):
            signals += 1
        if stoch_k and (stoch_k > 85 or stoch_k < 15):
            signals += 1
        if zscore and abs(zscore) > 2:
            signals += 1

        if signals >= 3:
            return "high"
        elif signals >= 2:
            return "moderate"
        else:
            return "low"

    def _format_beginner(
        self,
        symbol: str,
        status: str,
        confidence: str,
        rsi: Optional[float],
        close_pos: Optional[float],
    ) -> dict[str, Any]:
        """Format for beginner mode - simple status and advice."""
        emoji = {
            "overbought": "⚠️",
            "oversold": "💎",
            "neutral": "➡️",
        }.get(status, "➡️")

        status_labels = {
            "overbought": "Extended (May Pull Back)",
            "oversold": "Oversold (May Bounce)",
            "neutral": "Neutral",
        }

        return {
            "symbol": symbol,
            "status": status,
            "status_label": status_labels.get(status, status),
            "confidence": confidence,
            "description": self._get_beginner_description(status, confidence),
            "rsi": round(rsi) if rsi is not None else None,
            "position_in_range": f"{round(close_pos * 100)}%" if close_pos is not None else None,
            "advice": self._get_beginner_advice(status, confidence),
            "educational_tip": "Overbought doesn't mean sell immediately - it means be cautious of short-term pullbacks. In strong trends, stocks can stay overbought for weeks.",
            "action_block": self._build_action_block_reversal(status, confidence),
        }

    def _format_intermediate(
        self,
        symbol: str,
        status: str,
        confidence: str,
        rsi: Optional[float],
        stoch_k: Optional[float],
        stoch_d: Optional[float],
        close_pos: Optional[float],
        dist_to_ma20: Optional[float],
    ) -> dict[str, Any]:
        """Format for intermediate mode - oscillators and metrics."""
        return {
            "symbol": symbol,
            "reversal_status": status,
            "confidence": confidence,
            "oscillators": {
                "rsi_14": round(rsi, 2) if rsi is not None else None,
                "rsi_signal": self._get_rsi_signal(rsi),
                "stochastic_k": round(stoch_k, 2) if stoch_k is not None else None,
                "stochastic_d": round(stoch_d, 2) if stoch_d is not None else None,
                "stoch_signal": self._get_stoch_signal(stoch_k),
            },
            "position_metrics": {
                "close_position_in_range": round(close_pos * 100, 1) if close_pos is not None else None,
                "distance_to_ma20_pct": round(dist_to_ma20, 2) if dist_to_ma20 is not None else None,
            },
            "interpretation": self._get_intermediate_interpretation(status, confidence, rsi, dist_to_ma20),
            "trading_guidance": self._get_intermediate_guidance(status, confidence),
            "action_block": self._build_action_block_reversal(status, confidence),
        }

    def _build_action_block_reversal(self, status: str, confidence: str) -> dict[str, Any]:
        """Construct action guidance for mean reversion setups."""
        conf = {"low": 40, "moderate": 60, "high": 75}.get(confidence, 50)
        if status == "oversold":
            return {
                "entry": "Mean-reversion buy into 20-day after stabilization",
                "invalidation": "New low on increasing momentum",
                "risk_note": "Reduce size in high volatility; use ATR stops",
                "targets": ["20-day MA", "+1R"],
                "confidence": conf,
            }
        if status == "overbought":
            return {
                "entry": "Avoid chasing; consider fade only with confirmation",
                "invalidation": "Momentum re-accelerates up",
                "risk_note": "Defined-risk only for counter-trend",
                "targets": ["Mean reversion to 20-day"],
                "confidence": conf,
            }
        return {
            "entry": "Wait for cleaner setup",
            "invalidation": "N/A",
            "risk_note": "Neutral context",
            "targets": [],
            "confidence": 50,
        }

    def _format_advanced(
        self,
        symbol: str,
        status: str,
        confidence: str,
        is_overbought: bool,
        is_oversold: bool,
        rsi: Optional[float],
        stoch_k: Optional[float],
        stoch_d: Optional[float],
        close_pos: Optional[float],
        dist_to_ma20: Optional[float],
        zscore: Optional[float],
    ) -> dict[str, Any]:
        """Format for advanced mode - full reversal analysis."""
        return {
            "symbol": symbol,
            "reversal_assessment": {
                "status": status,
                "confidence": confidence,
                "is_overbought_flag": is_overbought,
                "is_oversold_flag": is_oversold,
            },
            "oscillator_readings": {
                "rsi_14": round(rsi, 4) if rsi is not None else None,
                "rsi_zone": self._get_rsi_zone(rsi),
                "stochastic_k": round(stoch_k, 4) if stoch_k is not None else None,
                "stochastic_d": round(stoch_d, 4) if stoch_d is not None else None,
                "stoch_zone": self._get_stoch_zone(stoch_k),
                "k_d_crossover": self._detect_crossover(stoch_k, stoch_d),
            },
            "statistical_metrics": {
                "close_position_in_range": round(close_pos, 4) if close_pos is not None else None,
                "distance_to_ma20_pct": round(dist_to_ma20, 4) if dist_to_ma20 is not None else None,
                "zscore_20d": round(zscore, 4) if zscore is not None else None,
                "zscore_interpretation": self._interpret_zscore(zscore),
            },
            "reversal_probability": self._estimate_reversal_probability(status, confidence, zscore),
            "thresholds": {
                "rsi_overbought": 70,
                "rsi_oversold": 30,
                "stoch_overbought": 80,
                "stoch_oversold": 20,
                "extreme_zscore": 2.0,
            },
        }

    @staticmethod
    def _get_rsi_signal(rsi: Optional[float]) -> str:
        """Get RSI signal."""
        if rsi is None:
            return "unknown"
        if rsi > 70:
            return "overbought"
        elif rsi < 30:
            return "oversold"
        else:
            return "neutral"

    @staticmethod
    def _get_stoch_signal(stoch_k: Optional[float]) -> str:
        """Get Stochastic signal."""
        if stoch_k is None:
            return "unknown"
        if stoch_k > 80:
            return "overbought"
        elif stoch_k < 20:
            return "oversold"
        else:
            return "neutral"

    @staticmethod
    def _get_rsi_zone(rsi: Optional[float]) -> str:
        """Get RSI zone."""
        if rsi is None:
            return "unknown"
        if rsi > 70:
            return "overbought (>70)"
        elif rsi < 30:
            return "oversold (<30)"
        else:
            return f"neutral ({round(rsi)})"

    @staticmethod
    def _get_stoch_zone(stoch_k: Optional[float]) -> str:
        """Get Stochastic zone."""
        if stoch_k is None:
            return "unknown"
        if stoch_k > 80:
            return "overbought (>80)"
        elif stoch_k < 20:
            return "oversold (<20)"
        else:
            return f"neutral ({round(stoch_k)})"

    @staticmethod
    def _detect_crossover(stoch_k: Optional[float], stoch_d: Optional[float]) -> Optional[str]:
        """Detect Stochastic crossover."""
        if stoch_k is None or stoch_d is None:
            return None
        if stoch_k > stoch_d:
            return "bullish (K>D)"
        else:
            return "bearish (K<D)"

    @staticmethod
    def _interpret_zscore(zscore: Optional[float]) -> str:
        """Interpret z-score."""
        if zscore is None:
            return "unknown"
        if zscore > 2:
            return "extremely high (>2 std dev)"
        elif zscore > 1:
            return "high (1-2 std dev)"
        elif zscore < -2:
            return "extremely low (<-2 std dev)"
        elif zscore < -1:
            return "low (-1 to -2 std dev)"
        else:
            return "normal range"

    @staticmethod
    def _get_beginner_description(status: str, confidence: str) -> str:
        """Get beginner-friendly description."""
        descriptions = {
            "overbought": "Stock has moved up quickly and may need to cool off. Short-term pullback possible.",
            "oversold": "Stock has fallen quickly and may be due for a bounce. Potential buying opportunity if fundamentals are sound.",
            "neutral": "Stock is not showing extreme readings. No clear reversal signal.",
        }
        conf_suffix = " (High confidence)" if confidence == "high" else " (Moderate confidence)" if confidence == "moderate" else ""
        return descriptions.get(status, "") + conf_suffix

    @staticmethod
    def _get_beginner_advice(status: str, confidence: str) -> str:
        """Get beginner trading advice."""
        if status == "overbought":
            if confidence == "high":
                return "Consider waiting for a pullback before entering. If you own it, consider taking partial profits."
            else:
                return "Stock is extended but not extreme. Monitor for reversal signs before taking action."
        elif status == "oversold":
            if confidence == "high":
                return "Potential buying opportunity if fundamentals are solid. Wait for signs of stabilization first."
            else:
                return "Stock is weak but not extremely oversold. Wait for clearer signals."
        else:
            return "No extreme readings. Normal trading strategies apply."

    @staticmethod
    def _get_intermediate_interpretation(status: str, confidence: str, rsi: Optional[float], dist_ma20: Optional[float]) -> str:
        """Get intermediate interpretation."""
        base = f"{status.capitalize()} with {confidence} confidence. "

        rsi_context = ""
        if rsi is not None:
            rsi_context = f"RSI at {round(rsi)}. "

        ma_context = ""
        if dist_ma20 is not None:
            if abs(dist_ma20) > 5:
                ma_context = f"Price {abs(round(dist_ma20))}% {'above' if dist_ma20 > 0 else 'below'} 20-day MA (extended)."

        return base + rsi_context + ma_context

    @staticmethod
    def _get_intermediate_guidance(status: str, confidence: str) -> str:
        """Get intermediate trading guidance."""
        if status == "overbought" and confidence in ["high", "moderate"]:
            return "Reduce new long entries. Tighten stops on existing positions. Consider taking profits on rips."
        elif status == "oversold" and confidence in ["high", "moderate"]:
            return "Watch for reversal confirmation. Consider scaling into longs on bounces off support."
        else:
            return "No extreme levels. Maintain normal position sizing and risk management."

    @staticmethod
    def _estimate_reversal_probability(status: str, confidence: str, zscore: Optional[float]) -> dict[str, Any]:
        """Estimate reversal probability."""
        if status == "neutral":
            return {"probability": "low", "note": "No extreme readings"}

        probability = "moderate"
        if confidence == "high" and zscore and abs(zscore) > 2:
            probability = "high"
        elif confidence == "low":
            probability = "low"

        expected_magnitude = "3-5%" if probability == "high" else "2-3%" if probability == "moderate" else "1-2%"

        return {
            "probability": probability,
            "expected_magnitude": expected_magnitude,
            "timeframe": "1-5 days",
        }
