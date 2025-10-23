"""
Market Regime Handler.

Provides market regime detection (trend/mean-revert/neutral) based on ADX, vol, correlations.
"""

from datetime import date
from typing import Any, Optional

import asyncpg
from fastapi import HTTPException

from .base import BaseCardHandler
from ..models.cards import CardMode


class MarketRegimeHandler(BaseCardHandler):
    """Handler for market_regime card."""

    async def fetch(
        self, mode: CardMode, symbol: Optional[str], trading_date: date
    ) -> dict[str, Any]:
        """
        Fetch market regime data.

        Data source: sb.market_regime_daily
        """
        query = """
            SELECT trading_date, regime_code, features
            FROM sb.market_regime_daily
            WHERE trading_date = $1
        """

        row = await self._fetch_one(query, {"trading_date": trading_date})

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No market regime data available for {trading_date}",
            )

        regime_code = row["regime_code"]
        features = row["features"] or {}

        if mode == CardMode.beginner:
            return self._format_beginner(regime_code, features)
        elif mode == CardMode.intermediate:
            return self._format_intermediate(regime_code, features)
        else:
            return self._format_advanced(regime_code, features, row)

    def _format_beginner(self, regime_code: str, features: dict) -> dict[str, Any]:
        """Beginner: Simple regime description with plain language."""
        regime_labels = {
            "TREND": "📈 Trending Market",
            "MEAN_REVERT": "↔️ Choppy Market",
            "NEUTRAL": "😐 Mixed Signals",
            "VOLATILE": "⚡ High Volatility",
            "LOW_VOL": "😴 Quiet Market",
        }

        regime_descriptions = {
            "TREND": "Stocks are moving in clear directions. Good for riding trends.",
            "MEAN_REVERT": "Stocks are bouncing around. Good for buying dips and selling pops.",
            "NEUTRAL": "Market has no clear direction. Be cautious.",
            "VOLATILE": "Big price swings happening. Higher risk, higher reward.",
            "LOW_VOL": "Calm market with small moves. Lower risk, lower rewards.",
        }

        regime_tips = {
            "TREND": "Look for stocks breaking out to new highs. Let winners run.",
            "MEAN_REVERT": "Buy low, sell high. Don't chase breakouts.",
            "NEUTRAL": "Wait for clearer signals. Focus on quality stocks.",
            "VOLATILE": "Use smaller position sizes. Set wider stop losses.",
            "LOW_VOL": "Good time to accumulate positions. Be patient.",
        }

        return {
            "regime": regime_labels.get(regime_code, regime_code),
            "description": regime_descriptions.get(regime_code, "Unknown regime type."),
            "what_to_do": regime_tips.get(regime_code, "Proceed with caution."),
            "tip": self._add_educational_tip("market_regime", CardMode.beginner),
        }

    def _format_intermediate(self, regime_code: str, features: dict) -> dict[str, Any]:
        """Intermediate: Regime with key metrics."""
        return {
            "regime": regime_code,
            "metrics": {
                "adx": features.get("adx"),
                "volatility_pct": features.get("volatility_pct"),
                "correlation": features.get("correlation"),
                "volume_trend": features.get("volume_trend"),
            },
            "interpretation": self._interpret_regime(regime_code),
            "trading_style": self._suggest_trading_style(regime_code),
        }

    def _format_advanced(
        self, regime_code: str, features: dict, row: asyncpg.Record
    ) -> dict[str, Any]:
        """Advanced: All raw data."""
        return {
            "regime": regime_code,
            "features": features,
            "raw_data": dict(row),
        }

    def _interpret_regime(self, regime_code: str) -> str:
        """Get regime interpretation for intermediate users."""
        interpretations = {
            "TREND": "Strong directional movement with ADX > 25. Momentum strategies favored.",
            "MEAN_REVERT": "Low ADX < 20 indicates choppy, range-bound action. Mean reversion strategies favored.",
            "NEUTRAL": "Mixed signals. ADX 20-25 range. No clear edge for trend or mean reversion.",
            "VOLATILE": "High volatility environment (ATR expanding). Risk management critical.",
            "LOW_VOL": "Low volatility (ATR contracting). Breakouts may lack follow-through.",
        }
        return interpretations.get(regime_code, "Regime classification uncertain.")

    def _suggest_trading_style(self, regime_code: str) -> str:
        """Suggest trading style based on regime."""
        styles = {
            "TREND": "Breakout, momentum, trend following",
            "MEAN_REVERT": "Support/resistance bounces, fade extremes, scalping",
            "NEUTRAL": "Selective swing trades, focus on fundamentals",
            "VOLATILE": "Options strategies, smaller size, wider stops",
            "LOW_VOL": "Accumulation, low-risk entries, patience",
        }
        return styles.get(regime_code, "Flexible approach")
