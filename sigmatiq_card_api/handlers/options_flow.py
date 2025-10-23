"""
Options Flow Handler.

Provides options flow analysis including put/call ratio and unusual activity.
"""

from datetime import date
from typing import Any, Optional

import asyncpg
from fastapi import HTTPException

from .base import BaseCardHandler
from ..models.cards import CardMode


class OptionsFlowHandler(BaseCardHandler):
    """Handler for options_flow card."""

    async def fetch(
        self, mode: CardMode, symbol: Optional[str], trading_date: date
    ) -> dict[str, Any]:
        """
        Fetch options flow data.

        Data source: sb.options_agg_eod + features field
        """
        if not symbol:
            raise HTTPException(
                status_code=400, detail="Symbol is required for options_flow card"
            )

        query = """
            SELECT symbol, as_of, iv30, features
            FROM sb.options_agg_eod
            WHERE symbol = $1 AND as_of = $2
        """

        row = await self._fetch_one(
            query, {"symbol": symbol.upper(), "as_of": trading_date}
        )

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No options flow data available for {symbol} on {trading_date}",
            )

        features = row["features"] or {}

        # Extract flow metrics from features
        put_call_ratio = features.get("put_call_ratio")
        put_volume = features.get("put_volume")
        call_volume = features.get("call_volume")
        total_volume = features.get("total_options_volume")

        if mode == CardMode.beginner:
            return self._format_beginner(
                symbol, put_call_ratio, put_volume, call_volume, total_volume
            )
        elif mode == CardMode.intermediate:
            return self._format_intermediate(
                symbol, put_call_ratio, put_volume, call_volume, total_volume, features
            )
        else:
            return self._format_advanced(
                symbol, put_call_ratio, put_volume, call_volume, total_volume, features, row
            )

    def _format_beginner(
        self,
        symbol: str,
        put_call_ratio: Optional[float],
        put_volume: Optional[int],
        call_volume: Optional[int],
        total_volume: Optional[int],
    ) -> dict[str, Any]:
        """Beginner: Simple flow interpretation."""
        if put_call_ratio is None:
            sentiment = "❓ No Flow Data"
            explanation = "Options flow data not available."
            interpretation = "Unable to determine market sentiment from options."
        elif put_call_ratio > 1.5:
            sentiment = "🐻 Bearish Flow"
            explanation = f"More puts than calls trading. Put/Call ratio: {put_call_ratio:.2f}"
            interpretation = "Traders are buying protection or betting on downside."
        elif put_call_ratio > 0.7:
            sentiment = "😐 Neutral Flow"
            explanation = f"Balanced put and call activity. Put/Call ratio: {put_call_ratio:.2f}"
            interpretation = "No clear directional bias from options traders."
        else:
            sentiment = "🐂 Bullish Flow"
            explanation = f"More calls than puts trading. Put/Call ratio: {put_call_ratio:.2f}"
            interpretation = "Traders are buying calls or betting on upside."

        return {
            "symbol": symbol,
            "sentiment": sentiment,
            "explanation": explanation,
            "interpretation": interpretation,
            "what_it_means": "Low put/call ratio = bullish (more calls). High put/call ratio = bearish (more puts).",
            "tip": self._add_educational_tip("options_flow", CardMode.beginner),
        }

    def _format_intermediate(
        self,
        symbol: str,
        put_call_ratio: Optional[float],
        put_volume: Optional[int],
        call_volume: Optional[int],
        total_volume: Optional[int],
        features: dict,
    ) -> dict[str, Any]:
        """Intermediate: Detailed flow analysis."""
        sentiment = self._determine_sentiment(put_call_ratio)
        flow_strength = self._assess_flow_strength(total_volume)

        return {
            "symbol": symbol,
            "put_call_ratio": {
                "value": put_call_ratio,
                "sentiment": sentiment,
                "interpretation": self._interpret_pcr(put_call_ratio),
            },
            "volume_breakdown": {
                "puts": put_volume,
                "calls": call_volume,
                "total": total_volume,
                "flow_strength": flow_strength,
            },
            "analysis": {
                "dominant_flow": "Put-heavy" if (put_call_ratio or 0) > 1 else "Call-heavy",
                "conviction_level": self._assess_conviction(put_call_ratio, total_volume),
            },
            "additional_metrics": self._extract_flow_metrics(features),
            "signals": self._generate_flow_signals(put_call_ratio, total_volume),
        }

    def _format_advanced(
        self,
        symbol: str,
        put_call_ratio: Optional[float],
        put_volume: Optional[int],
        call_volume: Optional[int],
        total_volume: Optional[int],
        features: dict,
        row: asyncpg.Record,
    ) -> dict[str, Any]:
        """Advanced: Full flow data with statistics."""
        return {
            "symbol": symbol,
            "as_of": row["as_of"].isoformat() if row["as_of"] else None,
            "flow_metrics": {
                "put_call_ratio": put_call_ratio,
                "put_volume": put_volume,
                "call_volume": call_volume,
                "total_options_volume": total_volume,
                "pcr_zscore": self._calculate_pcr_zscore(put_call_ratio),
            },
            "sentiment_analysis": {
                "primary_sentiment": self._determine_sentiment(put_call_ratio),
                "conviction": self._assess_conviction(put_call_ratio, total_volume),
                "contrarian_signal": self._check_contrarian(put_call_ratio),
            },
            "additional_features": features,
            "raw_data": dict(row),
        }

    def _determine_sentiment(self, put_call_ratio: Optional[float]) -> str:
        """Determine sentiment from put/call ratio."""
        if put_call_ratio is None:
            return "Unknown"
        if put_call_ratio > 1.5:
            return "Bearish"
        elif put_call_ratio > 1.0:
            return "Mildly Bearish"
        elif put_call_ratio > 0.7:
            return "Neutral"
        elif put_call_ratio > 0.5:
            return "Mildly Bullish"
        else:
            return "Bullish"

    def _interpret_pcr(self, put_call_ratio: Optional[float]) -> str:
        """Interpret put/call ratio."""
        if put_call_ratio is None:
            return "No data available"
        if put_call_ratio > 2.0:
            return "Extreme bearish positioning - potential contrarian buy signal"
        elif put_call_ratio > 1.5:
            return "Heavy put buying - protective hedging or bearish bets"
        elif put_call_ratio > 1.0:
            return "More puts than calls - cautious sentiment"
        elif put_call_ratio > 0.7:
            return "Balanced activity - neutral sentiment"
        elif put_call_ratio > 0.5:
            return "More calls than puts - bullish sentiment"
        else:
            return "Heavy call buying - speculative bullish bets or extreme optimism"

    def _assess_flow_strength(self, total_volume: Optional[int]) -> str:
        """Assess strength of options flow."""
        if total_volume is None:
            return "Unknown"
        # Simplified categorization
        if total_volume > 1000000:
            return "Very Strong"
        elif total_volume > 500000:
            return "Strong"
        elif total_volume > 100000:
            return "Moderate"
        else:
            return "Light"

    def _assess_conviction(
        self, put_call_ratio: Optional[float], total_volume: Optional[int]
    ) -> str:
        """Assess conviction level."""
        if put_call_ratio is None or total_volume is None:
            return "Unknown"

        # High volume + extreme ratio = high conviction
        volume_high = total_volume > 500000
        ratio_extreme = put_call_ratio > 1.5 or put_call_ratio < 0.5

        if volume_high and ratio_extreme:
            return "High"
        elif volume_high or ratio_extreme:
            return "Moderate"
        else:
            return "Low"

    def _extract_flow_metrics(self, features: dict) -> dict[str, Any]:
        """Extract additional flow metrics from features."""
        return {
            "open_interest_pcr": features.get("oi_put_call_ratio"),
            "volume_pcr": features.get("volume_put_call_ratio"),
            "unusual_activity_flags": features.get("unusual_activity", []),
        }

    def _generate_flow_signals(
        self, put_call_ratio: Optional[float], total_volume: Optional[int]
    ) -> list[str]:
        """Generate trading signals from flow."""
        signals = []

        if put_call_ratio:
            if put_call_ratio > 2.0:
                signals.append("Extreme bearish positioning - contrarian buy setup")
            elif put_call_ratio > 1.5:
                signals.append("Heavy put buying - protective hedging active")
            elif put_call_ratio < 0.4:
                signals.append("Extreme bullish positioning - contrarian sell setup")
            elif put_call_ratio < 0.6:
                signals.append("Heavy call buying - bullish speculation")

        if total_volume and total_volume > 1000000:
            signals.append("Very high options volume - increased market attention")

        if put_call_ratio and 0.8 <= put_call_ratio <= 1.2:
            signals.append("Balanced flow - no strong directional bias")

        return signals if signals else ["No significant flow signals"]

    def _check_contrarian(self, put_call_ratio: Optional[float]) -> bool:
        """Check if at contrarian extreme."""
        if put_call_ratio is None:
            return False
        return put_call_ratio > 2.0 or put_call_ratio < 0.3

    def _calculate_pcr_zscore(self, put_call_ratio: Optional[float]) -> Optional[float]:
        """Calculate PCR z-score (simplified)."""
        if put_call_ratio is None:
            return None
        # Assume mean=1.0, stddev=0.4
        return (put_call_ratio - 1.0) / 0.4
