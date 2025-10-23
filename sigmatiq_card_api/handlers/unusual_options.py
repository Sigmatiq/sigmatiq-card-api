"""
Unusual Options Activity Handler.

Provides unusual options activity analysis including IV, skew, and expected moves.
"""

from datetime import date
from typing import Any, Optional

import asyncpg
from fastapi import HTTPException

from .base import BaseCardHandler
from ..models.cards import CardMode


class UnusualOptionsHandler(BaseCardHandler):
    """Handler for unusual_options card."""

    async def fetch(
        self, mode: CardMode, symbol: Optional[str], trading_date: date
    ) -> dict[str, Any]:
        """
        Fetch unusual options activity data.

        Data source: sb.options_agg_eod
        """
        if not symbol:
            raise HTTPException(
                status_code=400, detail="Symbol is required for unusual_options card"
            )

        query = """
            SELECT symbol, as_of, iv30, skew, expected_move_1d, gex, features
            FROM sb.options_agg_eod
            WHERE symbol = $1 AND as_of = $2
        """

        row = await self._fetch_one(
            query, {"symbol": symbol.upper(), "as_of": trading_date}
        )

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No options data available for {symbol} on {trading_date}",
            )

        if mode == CardMode.beginner:
            return self._format_beginner(symbol, row)
        elif mode == CardMode.intermediate:
            return self._format_intermediate(symbol, row)
        else:
            return self._format_advanced(symbol, row)

    def _format_beginner(self, symbol: str, row: asyncpg.Record) -> dict[str, Any]:
        """Beginner: Simple options interpretation."""
        iv30 = float(row["iv30"]) if row["iv30"] else None
        expected_move_1d = float(row["expected_move_1d"]) if row["expected_move_1d"] else None

        if iv30 is None:
            iv_label = "❓ No IV data"
            iv_explanation = "Options data not available."
        elif iv30 > 50:
            iv_label = "🔥 High Volatility"
            iv_explanation = f"Options traders expect big moves. IV is {iv30:.0f}%."
        elif iv30 > 30:
            iv_label = "⚡ Moderate Volatility"
            iv_explanation = f"Options showing normal activity. IV is {iv30:.0f}%."
        else:
            iv_label = "😴 Low Volatility"
            iv_explanation = f"Options are cheap. Market expects small moves. IV is {iv30:.0f}%."

        if expected_move_1d:
            move_text = f"Market expects {symbol} to move ±{expected_move_1d:.1f}% tomorrow."
        else:
            move_text = "Expected move data not available."

        return {
            "symbol": symbol,
            "volatility": iv_label,
            "explanation": iv_explanation,
            "expected_move": move_text,
            "what_it_means": "High IV = expensive options, big expected moves. Low IV = cheap options, small expected moves.",
            "tip": self._add_educational_tip("unusual_options", CardMode.beginner),
        }

    def _format_intermediate(self, symbol: str, row: asyncpg.Record) -> dict[str, Any]:
        """Intermediate: Detailed options metrics."""
        iv30 = float(row["iv30"]) if row["iv30"] else None
        skew = float(row["skew"]) if row["skew"] else None
        expected_move_1d = float(row["expected_move_1d"]) if row["expected_move_1d"] else None
        gex = float(row["gex"]) if row["gex"] else None
        features = row["features"] or {}

        return {
            "symbol": symbol,
            "implied_volatility": {
                "iv30_pct": iv30,
                "level": self._categorize_iv(iv30),
                "interpretation": self._interpret_iv(iv30),
            },
            "skew": {
                "value": skew,
                "interpretation": self._interpret_skew(skew),
            },
            "expected_moves": {
                "one_day_pct": expected_move_1d,
                "interpretation": self._interpret_expected_move(expected_move_1d),
            },
            "gamma_exposure": {
                "gex": gex,
                "interpretation": self._interpret_gex(gex),
            },
            "additional_features": features,
            "signals": self._generate_options_signals(iv30, skew, expected_move_1d, gex),
        }

    def _format_advanced(self, symbol: str, row: asyncpg.Record) -> dict[str, Any]:
        """Advanced: Full options data."""
        return {
            "symbol": symbol,
            "as_of": row["as_of"].isoformat() if row["as_of"] else None,
            "metrics": {
                "iv30": float(row["iv30"]) if row["iv30"] else None,
                "skew": float(row["skew"]) if row["skew"] else None,
                "expected_move_1d_pct": (
                    float(row["expected_move_1d"]) if row["expected_move_1d"] else None
                ),
                "gex": float(row["gex"]) if row["gex"] else None,
            },
            "features": row["features"] or {},
            "derived_metrics": {
                "iv_percentile": self._iv_percentile(
                    float(row["iv30"]) if row["iv30"] else None
                ),
                "skew_interpretation": self._interpret_skew(
                    float(row["skew"]) if row["skew"] else None
                ),
            },
            "raw_data": dict(row),
        }

    def _categorize_iv(self, iv30: Optional[float]) -> str:
        """Categorize IV level."""
        if iv30 is None:
            return "Unknown"
        if iv30 > 60:
            return "Extreme"
        elif iv30 > 40:
            return "High"
        elif iv30 > 25:
            return "Moderate"
        else:
            return "Low"

    def _interpret_iv(self, iv30: Optional[float]) -> str:
        """Interpret IV level."""
        if iv30 is None:
            return "No IV data available"
        if iv30 > 60:
            return "Extremely elevated volatility - major event expected or occurring"
        elif iv30 > 40:
            return "High volatility - options expensive, significant uncertainty"
        elif iv30 > 25:
            return "Normal volatility range - typical options pricing"
        else:
            return "Low volatility - options cheap, market complacent"

    def _interpret_skew(self, skew: Optional[float]) -> str:
        """Interpret options skew."""
        if skew is None:
            return "No skew data available"
        if skew > 5:
            return "High negative skew - puts expensive, downside hedging demand"
        elif skew > 2:
            return "Moderate skew - some downside protection demand"
        elif skew > -2:
            return "Neutral skew - balanced put/call pricing"
        else:
            return "Positive skew - calls expensive, upside speculation"

    def _interpret_expected_move(self, expected_move: Optional[float]) -> str:
        """Interpret expected move."""
        if expected_move is None:
            return "No expected move data"
        if expected_move > 5:
            return "Large expected move - significant event or high uncertainty"
        elif expected_move > 2:
            return "Moderate expected move - normal daily volatility"
        else:
            return "Small expected move - stable conditions expected"

    def _interpret_gex(self, gex: Optional[float]) -> str:
        """Interpret gamma exposure."""
        if gex is None:
            return "No GEX data available"
        if gex > 0:
            return "Positive GEX - dealers long gamma, dampens volatility"
        elif gex < 0:
            return "Negative GEX - dealers short gamma, amplifies moves"
        else:
            return "Neutral GEX"

    def _generate_options_signals(
        self,
        iv30: Optional[float],
        skew: Optional[float],
        expected_move: Optional[float],
        gex: Optional[float],
    ) -> list[str]:
        """Generate options-based signals."""
        signals = []

        if iv30:
            if iv30 > 50:
                signals.append("IV elevated - options expensive, consider selling premium")
            elif iv30 < 20:
                signals.append("IV depressed - options cheap, good time to buy protection")

        if skew and skew > 3:
            signals.append("Skew elevated - market pricing downside risk")

        if expected_move and expected_move > 5:
            signals.append("Large move expected - earnings or event likely")

        if gex:
            if gex > 0:
                signals.append("Positive GEX - expect range-bound trading")
            else:
                signals.append("Negative GEX - expect volatile moves")

        return signals if signals else ["No significant options signals"]

    def _iv_percentile(self, iv30: Optional[float]) -> Optional[int]:
        """Estimate IV percentile (simplified)."""
        if iv30 is None:
            return None
        if iv30 > 60:
            return 95
        elif iv30 > 40:
            return 80
        elif iv30 > 30:
            return 60
        elif iv30 > 20:
            return 40
        else:
            return 20
