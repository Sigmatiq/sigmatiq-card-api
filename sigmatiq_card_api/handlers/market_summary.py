"""
Market Summary Handler - Composite market health score.

Combines multiple market metrics into a single health score (0-100):
- Market breadth (40% weight)
- Market regime (30% weight)
- Volatility proxy (20% weight)
- SPY trend (10% weight)

Data sources:
- sb.market_breadth_daily (breadth metrics)
- sb.symbol_indicators_daily (SPY trend)
"""

from datetime import date
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class MarketSummaryHandler(BaseCardHandler):
    """Handler for market_summary card - composite health score."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Fetch market summary data for the given trading date.

        Args:
            mode: Response complexity level
            symbol: Not used (market-level card)
            trading_date: Trading date to fetch data for

        Returns:
            Formatted card data based on mode

        Raises:
            HTTPException: If required data not found
        """
        # 1. Fetch market breadth data
        breadth_query = """
            SELECT above_ma50_pct, above_ma200_pct, new_highs, new_lows
            FROM sb.market_breadth_daily
            WHERE trading_date = $1 AND preset_id = 'all_active'
            LIMIT 1
        """
        breadth = await self._fetch_one(breadth_query, {"trading_date": trading_date})

        if not breadth:
            raise HTTPException(
                status_code=404,
                detail=f"No market breadth data for {trading_date}",
            )

        # 2. Fetch SPY trend data for trend score
        spy_query = """
            SELECT sma_200
            FROM sb.symbol_indicators_daily
            WHERE trading_date = $1 AND symbol = 'SPY'
            LIMIT 1
        """
        spy = await self._fetch_one(spy_query, {"trading_date": trading_date})

        # 3. Fetch SPY price to compare with SMA
        spy_price_query = """
            SELECT close
            FROM sb.equity_bars_daily
            WHERE trading_date = $1 AND symbol = 'SPY'
            LIMIT 1
        """
        spy_price = await self._fetch_one(spy_price_query, {"trading_date": trading_date})

        # Extract values
        above_ma50 = float(breadth["above_ma50_pct"] or 50)
        above_ma200 = float(breadth["above_ma200_pct"] or 50)
        new_highs = int(breadth["new_highs"] or 0)
        new_lows = int(breadth["new_lows"] or 0)

        # Calculate component scores
        # Breadth score (0-100): Use above_ma50 as proxy
        breadth_score = above_ma50

        # Regime score (0-100): Based on breadth health
        if above_ma50 >= 60 and new_highs > new_lows:
            regime_score = 80.0  # Bull regime
            regime_label = "Bullish"
        elif above_ma50 <= 40 or new_lows > new_highs:
            regime_score = 20.0  # Bear regime
            regime_label = "Bearish"
        else:
            regime_score = 50.0  # Neutral regime
            regime_label = "Neutral"

        # Volatility score (0-100): Placeholder - neutral default
        # TODO: Replace with VIX when available in database
        vol_score = 60.0

        # Trend score (0-100): SPY above/below 200-day MA
        if spy and spy_price:
            spy_sma200 = float(spy["sma_200"] or 0)
            spy_close = float(spy_price["close"] or 0)
            trend_score = 80.0 if spy_close > spy_sma200 else 30.0
            spy_above_ma200 = spy_close > spy_sma200
        else:
            trend_score = 50.0  # Neutral if no data
            spy_above_ma200 = None

        # Weighted composite score
        composite_score = (
            breadth_score * 0.40
            + regime_score * 0.30
            + vol_score * 0.20
            + trend_score * 0.10
        )

        # Classify overall health
        if composite_score >= 65:
            health_label = "Bullish"
            health_emoji = "✅"
        elif composite_score >= 40:
            health_label = "Neutral"
            health_emoji = "⚠️"
        else:
            health_label = "Bearish"
            health_emoji = "❌"

        # Format based on mode
        if mode == CardMode.beginner:
            return self._format_beginner(
                composite_score,
                health_label,
                health_emoji,
                regime_label,
                above_ma50,
                spy_above_ma200,
            )
        elif mode == CardMode.intermediate:
            return self._format_intermediate(
                composite_score,
                health_label,
                breadth_score,
                regime_score,
                vol_score,
                trend_score,
                regime_label,
                above_ma50,
                above_ma200,
                new_highs,
                new_lows,
                spy_above_ma200,
            )
        else:
            return self._format_advanced(
                composite_score,
                health_label,
                breadth_score,
                regime_score,
                vol_score,
                trend_score,
                regime_label,
                above_ma50,
                above_ma200,
                new_highs,
                new_lows,
                spy_above_ma200,
            )

    def _format_beginner(
        self,
        composite_score: float,
        health_label: str,
        health_emoji: str,
        regime_label: str,
        above_ma50: float,
        spy_above_ma200: Optional[bool],
    ) -> dict[str, Any]:
        """Format for beginner mode - simple score and guidance."""
        return {
            "market_health_score": round(composite_score),
            "market_health_label": f"{health_emoji} {health_label} Market ({round(composite_score)}/100)",
            "simple_guidance": self._get_simple_guidance(composite_score),
            "regime": regime_label,
            "breadth_pct": round(above_ma50),
            "spy_trend": "Above 200-day average" if spy_above_ma200 else "Below 200-day average" if spy_above_ma200 is not None else "No data",
            "bias_block": self._build_bias_block(health_label, above_ma50),
        }

    def _format_intermediate(
        self,
        composite_score: float,
        health_label: str,
        breadth_score: float,
        regime_score: float,
        vol_score: float,
        trend_score: float,
        regime_label: str,
        above_ma50: float,
        above_ma200: float,
        new_highs: int,
        new_lows: int,
        spy_above_ma200: Optional[bool],
    ) -> dict[str, Any]:
        """Format for intermediate mode - component breakdown."""
        return {
            "market_health_score": round(composite_score),
            "market_health_label": f"{health_label} Market",
            "components": {
                "breadth": {
                    "score": round(breadth_score),
                    "weight": 40,
                    "above_ma50_pct": round(above_ma50),
                    "above_ma200_pct": round(above_ma200),
                },
                "regime": {
                    "score": round(regime_score),
                    "weight": 30,
                    "regime_label": regime_label,
                },
                "volatility": {
                    "score": round(vol_score),
                    "weight": 20,
                    "note": "Placeholder - VIX not yet available",
                },
                "trend": {
                    "score": round(trend_score),
                    "weight": 10,
                    "spy_above_ma200": spy_above_ma200,
                },
            },
            "hl_ratio": f"{new_highs}/{new_lows}" if new_highs or new_lows else "N/A",
            "guidance": self._get_simple_guidance(composite_score),
            "bias_block": self._build_bias_block(health_label, above_ma50),
        }

    def _build_bias_block(self, health_label: str, above_ma50: float) -> dict[str, Any]:
        """Construct bias from health label and breadth."""
        if health_label == "Bullish" and above_ma50 >= 60:
            return {"bias": "risk_on", "focus": "trend continuation", "guardrails": "If internals weaken intraday, cut risk"}
        if health_label == "Bearish" and above_ma50 <= 40:
            return {"bias": "risk_off", "focus": "defensive", "guardrails": "Only A+ setups, smaller size"}
        return {"bias": "neutral", "focus": "stock-picking", "guardrails": "Be selective"}

    def _format_advanced(
        self,
        composite_score: float,
        health_label: str,
        breadth_score: float,
        regime_score: float,
        vol_score: float,
        trend_score: float,
        regime_label: str,
        above_ma50: float,
        above_ma200: float,
        new_highs: int,
        new_lows: int,
        spy_above_ma200: Optional[bool],
    ) -> dict[str, Any]:
        """Format for advanced mode - full breakdown with raw values."""
        return {
            "composite_score": round(composite_score, 2),
            "health_classification": health_label,
            "component_scores": {
                "breadth": {
                    "score": round(breadth_score, 2),
                    "weight": 0.40,
                    "contribution": round(breadth_score * 0.40, 2),
                    "raw_values": {
                        "above_ma50_pct": round(above_ma50, 2),
                        "above_ma200_pct": round(above_ma200, 2),
                        "new_highs": new_highs,
                        "new_lows": new_lows,
                    },
                },
                "regime": {
                    "score": round(regime_score, 2),
                    "weight": 0.30,
                    "contribution": round(regime_score * 0.30, 2),
                    "regime_classification": regime_label,
                },
                "volatility": {
                    "score": round(vol_score, 2),
                    "weight": 0.20,
                    "contribution": round(vol_score * 0.20, 2),
                    "note": "Placeholder pending VIX data",
                },
                "trend": {
                    "score": round(trend_score, 2),
                    "weight": 0.10,
                    "contribution": round(trend_score * 0.10, 2),
                    "spy_above_ma200": spy_above_ma200,
                },
            },
            "thresholds": {
                "bullish": 65,
                "neutral": 40,
                "bearish": 0,
            },
        }

    @staticmethod
    def _get_simple_guidance(score: float) -> str:
        """Get simple trading guidance based on score."""
        if score >= 65:
            return "Favorable conditions for long positions. Look for quality setups in leading stocks."
        elif score >= 40:
            return "Mixed conditions. Be selective. Wait for high-probability setups."
        else:
            return "Weak market. Consider defensive positioning or staying in cash."
