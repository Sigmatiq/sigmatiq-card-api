"""
Breakout Watch Handler - 52-week breakout detection.

Detects when stocks break above 52-week highs with volume confirmation:
- Breakout status (is_breakout_52w)
- Volume confirmation (RVOL)
- Quality assessment based on RS percentile
- Distance from breakout level

Data sources:
- sb.symbol_derived_eod (breakout flags, rvol, returns)
- sb.symbol_52w_levels (52-week high/low data)
- sb.symbol_cross_sectional_eod (RS percentiles for quality check)
"""

from datetime import date
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class BreakoutWatchHandler(BaseCardHandler):
    """Handler for ticker_breakout card - 52-week breakout detection."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Fetch breakout data for the given symbol and trading date.

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
                detail="Symbol is required for ticker_breakout card",
            )

        # Fetch breakout data
        query = """
            SELECT
                d.trading_date,
                d.symbol,
                d.close,
                d.is_breakout_52w,
                d.r_20d_pct,
                d.rvol,
                l.high_52w,
                l.high_52w_date,
                x.rs_pct_60
            FROM sb.symbol_derived_eod d
            JOIN sb.symbol_52w_levels l ON l.symbol = d.symbol AND l.trading_date = d.trading_date
            LEFT JOIN sb.symbol_cross_sectional_eod x ON x.symbol = d.symbol AND x.trading_date = d.trading_date
            WHERE d.symbol = $1 AND d.trading_date = $2
            LIMIT 1
        """
        row = await self._fetch_one(query, {"symbol": symbol, "trading_date": trading_date})

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No breakout data for {symbol} on {trading_date}",
            )

        # Extract values
        is_breakout = bool(row["is_breakout_52w"])
        close = float(row["close"]) if row["close"] else 0
        high_52w = float(row["high_52w"]) if row["high_52w"] else 0
        rvol = float(row["rvol"]) if row["rvol"] is not None else 1.0
        rs_60 = float(row["rs_pct_60"]) if row["rs_pct_60"] is not None else None
        r_20d = float(row["r_20d_pct"]) if row["r_20d_pct"] is not None else None

        # Assess breakout quality
        breakout_quality = self._assess_breakout_quality(is_breakout, rvol, rs_60)

        # Calculate distance from 52w high
        dist_from_high_pct = ((close - high_52w) / high_52w * 100) if high_52w > 0 else 0

        # Format based on mode
        if mode == CardMode.beginner:
            return self._format_beginner(
                symbol,
                is_breakout,
                breakout_quality,
                close,
                high_52w,
                rvol,
            )
        elif mode == CardMode.intermediate:
            return self._format_intermediate(
                symbol,
                is_breakout,
                breakout_quality,
                close,
                high_52w,
                dist_from_high_pct,
                rvol,
                rs_60,
                r_20d,
            )
        else:
            return self._format_advanced(
                symbol,
                is_breakout,
                breakout_quality,
                close,
                high_52w,
                dist_from_high_pct,
                rvol,
                rs_60,
                r_20d,
                row["high_52w_date"],
            )

    @staticmethod
    def _assess_breakout_quality(
        is_breakout: bool,
        rvol: float,
        rs_60: Optional[float],
    ) -> str:
        """
        Assess breakout quality based on volume and RS.

        Args:
            is_breakout: Whether stock is breaking out
            rvol: Relative volume
            rs_60: 60-day RS percentile

        Returns:
            Quality: high_quality, moderate, low_volume, or not_breakout
        """
        if not is_breakout:
            return "not_breakout"

        # High quality: breakout + high volume + strong RS
        if rvol > 1.5 and rs_60 is not None and rs_60 > 70:
            return "high_quality"
        # Moderate: breakout + decent volume
        elif rvol > 1.0:
            return "moderate"
        # Low volume breakout (often fails)
        else:
            return "low_volume"

    def _format_beginner(
        self,
        symbol: str,
        is_breakout: bool,
        quality: str,
        close: float,
        high_52w: float,
        rvol: float,
    ) -> dict[str, Any]:
        """Format for beginner mode - simple breakout status."""
        if is_breakout:
            emoji = "🔥" if quality == "high_quality" else "⚠️" if quality == "moderate" else "❌"
            status_label = f"{emoji} 52-Week Breakout!"
        else:
            emoji = "📊"
            status_label = f"{emoji} Not Breaking Out"

        return {
            "symbol": symbol,
            "is_breakout": is_breakout,
            "breakout_status": status_label,
            "breakout_status_clean": ("52-Week Breakout!" if is_breakout else "Not Breaking Out"),
            "quality": quality,
            "quality_label": self._get_quality_label(quality),
            "current_price": round(close, 2),
            "week_52_high": round(high_52w, 2),
            "volume_vs_average": f"{round((rvol - 1) * 100):+}%",
            "interpretation": self._get_beginner_interpretation(is_breakout, quality),
            "trading_advice": self._get_trading_advice(is_breakout, quality),
            "educational_tip": "Breakouts with high volume (1.5x+ average) and strong RS often continue. Low-volume breakouts often fail.",
            "action_block": self._build_action_block_breakout(is_breakout, quality, high_52w),
        }

    def _format_intermediate(
        self,
        symbol: str,
        is_breakout: bool,
        quality: str,
        close: float,
        high_52w: float,
        dist_from_high_pct: float,
        rvol: float,
        rs_60: Optional[float],
        r_20d: Optional[float],
    ) -> dict[str, Any]:
        """Format for intermediate mode - breakout metrics and quality."""
        return {
            "symbol": symbol,
            "breakout_detected": is_breakout,
            "breakout_quality": quality,
            "quality_label": self._get_quality_label(quality),
            "price_metrics": {
                "current_price": round(close, 2),
                "week_52_high": round(high_52w, 2),
                "distance_from_high_pct": round(dist_from_high_pct, 2),
                "return_20d_pct": round(r_20d, 2) if r_20d is not None else None,
            },
            "confirmation_metrics": {
                "relative_volume": round(rvol, 2),
                "rs_percentile": round(rs_60) if rs_60 is not None else None,
                "volume_confirmed": rvol > 1.5,
                "rs_confirmed": rs_60 > 70 if rs_60 is not None else False,
            },
            "interpretation": self._get_intermediate_interpretation(is_breakout, quality, rs_60),
            "trading_guidance": self._get_trading_advice(is_breakout, quality),
            "action_block": self._build_action_block_breakout(is_breakout, quality, high_52w),
        }

    def _build_action_block_breakout(self, is_breakout: bool, quality: str, high_52w: float) -> dict[str, Any]:
        """Construct action guidance for breakouts/pullbacks."""
        if not is_breakout:
            return {
                "entry": "Wait for breakout or strong RS setup",
                "invalidation": "N/A",
                "risk_note": "No edge before breakout",
                "targets": [],
                "confidence": 40,
            }
        if quality == "high_quality":
            return {
                "entry": "Buy breakout or first pullback above 52w high",
                "invalidation": f"Close back below 52w high (~{high_52w:.2f})",
                "risk_note": "Use ATR-based stop below breakout level",
                "targets": ["+1R", "+2R"],
                "confidence": 80,
            }
        if quality == "moderate":
            return {
                "entry": "Prefer pullback and re-test; confirm volume",
                "invalidation": f"Sustained back below 52w high (~{high_52w:.2f})",
                "risk_note": "Smaller size; confirm RS/volume",
                "targets": ["+1R"],
                "confidence": 60,
            }
        return {
            "entry": "Avoid low-volume breakouts; wait for retest + volume",
            "invalidation": f"Below 52w high (~{high_52w:.2f})",
            "risk_note": "Higher failure rate on low volume",
            "targets": [],
            "confidence": 45,
        }

    def _format_advanced(
        self,
        symbol: str,
        is_breakout: bool,
        quality: str,
        close: float,
        high_52w: float,
        dist_from_high_pct: float,
        rvol: float,
        rs_60: Optional[float],
        r_20d: Optional[float],
        high_52w_date: Optional[date],
    ) -> dict[str, Any]:
        """Format for advanced mode - full breakout analysis."""
        return {
            "symbol": symbol,
            "breakout_status": {
                "is_breakout": is_breakout,
                "quality": quality,
                "quality_score": self._calculate_quality_score(rvol, rs_60),
            },
            "price_analysis": {
                "current_price": round(close, 4),
                "week_52_high": round(high_52w, 4),
                "distance_from_high_pct": round(dist_from_high_pct, 4),
                "previous_high_date": high_52w_date.isoformat() if high_52w_date else None,
                "recent_return_20d": round(r_20d, 4) if r_20d is not None else None,
            },
            "confirmation_signals": {
                "relative_volume": round(rvol, 4),
                "rvol_threshold_met": rvol > 1.5,
                "rs_percentile_60d": round(rs_60, 2) if rs_60 is not None else None,
                "rs_threshold_met": rs_60 > 70 if rs_60 is not None else None,
            },
            "quality_thresholds": {
                "high_quality": "RVOL > 1.5 AND RS > 70",
                "moderate": "RVOL > 1.0",
                "low_volume": "Breakout but RVOL < 1.0",
            },
            "risk_management": {
                "stop_suggestion": "Below breakout level (52w high)",
                "follow_through_required": "Watch for 1-2 days of continuation",
            },
        }

    @staticmethod
    def _get_quality_label(quality: str) -> str:
        """Get human-readable quality label."""
        labels = {
            "high_quality": "High Quality Breakout",
            "moderate": "Moderate Quality",
            "low_volume": "Low Volume (Risky)",
            "not_breakout": "Not in Breakout",
        }
        return labels.get(quality, quality)

    @staticmethod
    def _calculate_quality_score(rvol: float, rs_60: Optional[float]) -> int:
        """Calculate quality score 0-100."""
        score = 0

        # Volume component (0-50 points)
        if rvol > 2.0:
            score += 50
        elif rvol > 1.5:
            score += 40
        elif rvol > 1.0:
            score += 25
        else:
            score += 10

        # RS component (0-50 points)
        if rs_60 is not None:
            if rs_60 > 80:
                score += 50
            elif rs_60 > 70:
                score += 40
            elif rs_60 > 50:
                score += 25
            else:
                score += 10

        return score

    @staticmethod
    def _get_beginner_interpretation(is_breakout: bool, quality: str) -> str:
        """Get beginner-friendly interpretation."""
        if not is_breakout:
            return "Stock is not currently breaking out to new 52-week highs. Wait for a breakout before considering momentum entry."

        interpretations = {
            "high_quality": "High-quality breakout with strong volume and momentum. This type of breakout often continues higher. Good setup for trend-followers.",
            "moderate": "Breakout with decent volume but not exceptional. Wait for 1-2 days of follow-through before entering.",
            "low_volume": "Breakout on light volume - these often fail. Wait for volume confirmation before buying. Many false breakouts look like this.",
        }
        return interpretations.get(quality, "Breakout detected")

    @staticmethod
    def _get_trading_advice(is_breakout: bool, quality: str) -> str:
        """Get trading advice based on breakout status."""
        if not is_breakout:
            return "Not breaking out. Wait for price to clear 52-week high on strong volume. Set alert at resistance."

        advice = {
            "high_quality": "Consider entry on pullback to breakout level or on continuation. Set stop below 52w high. Target 20%+ from breakout.",
            "moderate": "Wait for 1-2 days of follow-through above breakout before entering. Watch for volume confirmation.",
            "low_volume": "High risk of failure. Wait for volume to increase above 1.5x average. Many traders would pass on low-volume breakouts.",
        }
        return advice.get(quality, "Proceed with caution")

    @staticmethod
    def _get_intermediate_interpretation(is_breakout: bool, quality: str, rs_60: Optional[float]) -> str:
        """Get intermediate-level interpretation."""
        if not is_breakout:
            return "No breakout detected. Monitor for price clearing 52-week high with volume."

        rs_context = ""
        if rs_60 is not None:
            if rs_60 > 70:
                rs_context = " Strong RS confirms quality."
            else:
                rs_context = f" RS at {round(rs_60)}th percentile - moderate strength."

        base = f"{quality.replace('_', ' ').title()} breakout detected."
        return f"{base}{rs_context}"
