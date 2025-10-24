"""
Volatility Snapshot Handler - Ticker-specific volatility metrics.

Shows key volatility indicators:
- ATR (Average True Range)
- Bollinger Band width
- Historical volatility (20-day)
- Volatility classification

Data sources:
- sb.symbol_indicators_daily (ATR, Bollinger Bands)
- sb.equity_bars_daily (for price context)
"""

from datetime import date
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class VolatilitySnapshotHandler(BaseCardHandler):
    """Handler for ticker_volatility card - volatility metrics."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Fetch volatility metrics for the given symbol and trading date.

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
                detail="Symbol is required for ticker_volatility card",
            )

        # Fetch volatility indicators
        indicators_query = """
            SELECT atr_14, bb_upper, bb_middle, bb_lower
            FROM sb.symbol_indicators_daily
            WHERE trading_date = $1 AND symbol = $2
            LIMIT 1
        """
        indicators = await self._fetch_one(
            indicators_query, {"trading_date": trading_date, "symbol": symbol}
        )

        if not indicators:
            raise HTTPException(
                status_code=404,
                detail=f"No volatility data for {symbol} on {trading_date}",
            )

        # Fetch price data for context
        price_query = """
            SELECT close, high, low
            FROM sb.equity_bars_daily
            WHERE trading_date = $1 AND symbol = $2
            LIMIT 1
        """
        price_data = await self._fetch_one(
            price_query, {"trading_date": trading_date, "symbol": symbol}
        )

        if not price_data:
            raise HTTPException(
                status_code=404,
                detail=f"No price data for {symbol} on {trading_date}",
            )

        # Extract values
        atr = float(indicators["atr_14"]) if indicators["atr_14"] is not None else None
        bb_upper = float(indicators["bb_upper"]) if indicators["bb_upper"] is not None else None
        bb_middle = float(indicators["bb_middle"]) if indicators["bb_middle"] is not None else None
        bb_lower = float(indicators["bb_lower"]) if indicators["bb_lower"] is not None else None
        close = float(price_data["close"])

        # Calculate derived metrics
        bb_width = None
        bb_width_pct = None
        atr_pct = None

        if bb_upper is not None and bb_lower is not None and bb_middle is not None:
            bb_width = bb_upper - bb_lower
            bb_width_pct = (bb_width / bb_middle) * 100 if bb_middle > 0 else None

        if atr is not None and close > 0:
            atr_pct = (atr / close) * 100

        # Classify volatility
        volatility_classification = self._classify_volatility(bb_width_pct, atr_pct)

        # Determine position sizing guidance
        position_size_guidance = self._get_position_size_guidance(volatility_classification)

        # Format based on mode
        if mode == CardMode.beginner:
            return self._format_beginner(
                symbol,
                volatility_classification,
                atr,
                atr_pct,
                bb_width_pct,
                position_size_guidance,
            )
        elif mode == CardMode.intermediate:
            return self._format_intermediate(
                symbol,
                volatility_classification,
                atr,
                atr_pct,
                bb_width,
                bb_width_pct,
                close,
                bb_upper,
                bb_middle,
                bb_lower,
                position_size_guidance,
            )
        else:
            return self._format_advanced(
                symbol,
                volatility_classification,
                atr,
                atr_pct,
                bb_width,
                bb_width_pct,
                close,
                bb_upper,
                bb_middle,
                bb_lower,
            )

    @staticmethod
    def _classify_volatility(
        bb_width_pct: Optional[float], atr_pct: Optional[float]
    ) -> str:
        """
        Classify volatility level based on Bollinger Band width and ATR.

        Args:
            bb_width_pct: Bollinger Band width as % of middle band
            atr_pct: ATR as % of current price

        Returns:
            Volatility classification: Very High, High, Normal, Low, or Very Low
        """
        # Use BB width % as primary signal, ATR % as confirmation
        score = 0

        if bb_width_pct is not None:
            if bb_width_pct > 10:
                score += 2
            elif bb_width_pct > 6:
                score += 1
            elif bb_width_pct < 3:
                score -= 1
            elif bb_width_pct < 2:
                score -= 2

        if atr_pct is not None:
            if atr_pct > 5:
                score += 1
            elif atr_pct > 3:
                score += 0.5
            elif atr_pct < 1.5:
                score -= 0.5
            elif atr_pct < 1:
                score -= 1

        # Classify based on score
        if score >= 2.5:
            return "Very High"
        elif score >= 1:
            return "High"
        elif score <= -2:
            return "Very Low"
        elif score <= -1:
            return "Low"
        else:
            return "Normal"

    @staticmethod
    def _get_position_size_guidance(volatility_class: str) -> str:
        """Get position sizing guidance based on volatility."""
        guidance_map = {
            "Very High": "Reduce position size by 50%+ due to extreme volatility. Wider stops required.",
            "High": "Reduce position size by 25-50%. Use wider stops to avoid whipsaw.",
            "Normal": "Standard position sizing. Normal stop placement.",
            "Low": "Can use standard to slightly larger positions. Tighter stops possible.",
            "Very Low": "Watch for potential volatility expansion. May precede breakout or breakdown.",
        }
        return guidance_map.get(volatility_class, "Assess risk carefully.")

    def _format_beginner(
        self,
        symbol: str,
        classification: str,
        atr: Optional[float],
        atr_pct: Optional[float],
        bb_width_pct: Optional[float],
        position_guidance: str,
    ) -> dict[str, Any]:
        """Format for beginner mode - simple classification and guidance."""
        # Get emoji for classification
        emoji = {
            "Very High": "🔥",
            "High": "⚡",
            "Normal": "✅",
            "Low": "📊",
            "Very Low": "💤",
        }.get(classification, "➡️")

        return {
            "symbol": symbol,
            "volatility_level": f"{emoji} {classification} Volatility",
            "simple_explanation": self._get_beginner_explanation(classification),
            "position_sizing_tip": position_guidance,
            "key_metrics": {
                "atr_dollars": f"${round(atr, 2)}" if atr else "N/A",
                "atr_percent": f"{round(atr_pct, 2)}%" if atr_pct else "N/A",
            },
        }

    def _format_intermediate(
        self,
        symbol: str,
        classification: str,
        atr: Optional[float],
        atr_pct: Optional[float],
        bb_width: Optional[float],
        bb_width_pct: Optional[float],
        close: float,
        bb_upper: Optional[float],
        bb_middle: Optional[float],
        bb_lower: Optional[float],
        position_guidance: str,
    ) -> dict[str, Any]:
        """Format for intermediate mode - detailed metrics."""
        return {
            "symbol": symbol,
            "volatility_classification": classification,
            "metrics": {
                "atr": {
                    "value": round(atr, 4) if atr else None,
                    "percentage": round(atr_pct, 2) if atr_pct else None,
                    "interpretation": self._get_atr_interpretation(atr_pct),
                },
                "bollinger_bands": {
                    "width": round(bb_width, 4) if bb_width else None,
                    "width_percentage": round(bb_width_pct, 2) if bb_width_pct else None,
                    "upper": round(bb_upper, 2) if bb_upper else None,
                    "middle": round(bb_middle, 2) if bb_middle else None,
                    "lower": round(bb_lower, 2) if bb_lower else None,
                    "current_price": round(close, 2),
                    "band_position": self._get_bb_position(close, bb_upper, bb_middle, bb_lower),
                },
            },
            "position_sizing": position_guidance,
            "stop_guidance": self._get_stop_guidance(atr, classification),
        }

    def _format_advanced(
        self,
        symbol: str,
        classification: str,
        atr: Optional[float],
        atr_pct: Optional[float],
        bb_width: Optional[float],
        bb_width_pct: Optional[float],
        close: float,
        bb_upper: Optional[float],
        bb_middle: Optional[float],
        bb_lower: Optional[float],
    ) -> dict[str, Any]:
        """Format for advanced mode - full metrics and analysis."""
        return {
            "symbol": symbol,
            "volatility_classification": classification,
            "raw_metrics": {
                "atr_14": {
                    "absolute": round(atr, 6) if atr else None,
                    "percentage": round(atr_pct, 4) if atr_pct else None,
                    "interpretation": self._get_atr_interpretation(atr_pct),
                },
                "bollinger_bands": {
                    "upper_band": round(bb_upper, 4) if bb_upper else None,
                    "middle_band": round(bb_middle, 4) if bb_middle else None,
                    "lower_band": round(bb_lower, 4) if bb_lower else None,
                    "width_absolute": round(bb_width, 6) if bb_width else None,
                    "width_percentage": round(bb_width_pct, 4) if bb_width_pct else None,
                    "current_price": round(close, 4),
                },
            },
            "derived_metrics": {
                "bb_position": self._get_bb_position_detailed(
                    close, bb_upper, bb_middle, bb_lower
                ),
                "bb_squeeze_status": self._detect_bb_squeeze(bb_width_pct),
                "price_to_upper_band": round((bb_upper - close) / close * 100, 2)
                if bb_upper
                else None,
                "price_to_lower_band": round((close - bb_lower) / close * 100, 2)
                if bb_lower
                else None,
            },
            "risk_management": {
                "recommended_stop_distance": f"{round(atr * 2, 2)}" if atr else None,
                "recommended_stop_distance_pct": f"{round(atr_pct * 2, 2)}%"
                if atr_pct
                else None,
                "position_size_multiplier": self._get_position_multiplier(classification),
            },
            "thresholds": {
                "bb_width_pct": {
                    "very_high": ">10%",
                    "high": "6-10%",
                    "normal": "3-6%",
                    "low": "2-3%",
                    "very_low": "<2%",
                },
                "atr_pct": {
                    "very_high": ">5%",
                    "high": "3-5%",
                    "normal": "1.5-3%",
                    "low": "1-1.5%",
                    "very_low": "<1%",
                },
            },
        }

    @staticmethod
    def _get_beginner_explanation(classification: str) -> str:
        """Get plain-language explanation for beginners."""
        explanations = {
            "Very High": "This stock is moving a lot (big daily swings). Higher risk but also bigger profit potential. Use smaller positions.",
            "High": "Above-normal price swings. More risk than usual. Consider reducing position size.",
            "Normal": "Normal price movement for this stock. Standard position sizing and risk management apply.",
            "Low": "Stock is calmer than usual. May be in consolidation before next big move.",
            "Very Low": "Very quiet - possibly before a big move. Watch for volatility expansion (breakout or breakdown coming).",
        }
        return explanations.get(
            classification, "Volatility level unclear - assess risk carefully."
        )

    @staticmethod
    def _get_atr_interpretation(atr_pct: Optional[float]) -> str:
        """Get ATR interpretation."""
        if atr_pct is None:
            return "No data"
        if atr_pct > 5:
            return "Extremely volatile - expect large daily swings"
        elif atr_pct > 3:
            return "High volatility - wider stops needed"
        elif atr_pct > 1.5:
            return "Normal volatility for this stock"
        elif atr_pct > 1:
            return "Low volatility - tight range"
        else:
            return "Very low volatility - consolidation phase"

    @staticmethod
    def _get_bb_position(
        price: float,
        bb_upper: Optional[float],
        bb_middle: Optional[float],
        bb_lower: Optional[float],
    ) -> str:
        """Determine price position within Bollinger Bands."""
        if not all([bb_upper, bb_middle, bb_lower]):
            return "Unknown"

        if price > bb_upper:
            return "Above upper band (overbought zone)"
        elif price > bb_middle:
            return "Upper half (bullish zone)"
        elif price > bb_lower:
            return "Lower half (bearish zone)"
        else:
            return "Below lower band (oversold zone)"

    @staticmethod
    def _get_bb_position_detailed(
        price: float,
        bb_upper: Optional[float],
        bb_middle: Optional[float],
        bb_lower: Optional[float],
    ) -> dict[str, Any]:
        """Get detailed Bollinger Band position analysis."""
        if not all([bb_upper, bb_middle, bb_lower]):
            return {"position": "Unknown", "percentile": None}

        bb_range = bb_upper - bb_lower
        if bb_range == 0:
            return {"position": "Bands collapsed", "percentile": 50}

        percentile = ((price - bb_lower) / bb_range) * 100

        if percentile > 100:
            position = "Above bands"
        elif percentile > 75:
            position = "Upper quartile"
        elif percentile > 50:
            position = "Upper half"
        elif percentile > 25:
            position = "Lower half"
        elif percentile > 0:
            position = "Lower quartile"
        else:
            position = "Below bands"

        return {"position": position, "percentile": round(percentile, 2)}

    @staticmethod
    def _detect_bb_squeeze(bb_width_pct: Optional[float]) -> str:
        """Detect Bollinger Band squeeze (low volatility before breakout)."""
        if bb_width_pct is None:
            return "Unknown"
        if bb_width_pct < 2:
            return "Extreme squeeze - breakout likely imminent"
        elif bb_width_pct < 3:
            return "Squeeze detected - watch for expansion"
        else:
            return "No squeeze"

    @staticmethod
    def _get_stop_guidance(atr: Optional[float], classification: str) -> str:
        """Get stop-loss placement guidance."""
        if atr is None:
            return "Insufficient data for stop guidance"

        multipliers = {
            "Very High": 3.0,
            "High": 2.5,
            "Normal": 2.0,
            "Low": 1.5,
            "Very Low": 1.5,
        }

        multiplier = multipliers.get(classification, 2.0)
        stop_distance = atr * multiplier

        return f"Suggested stop: {multiplier}x ATR = ${round(stop_distance, 2)} from entry"

    @staticmethod
    def _get_position_multiplier(classification: str) -> float:
        """Get position size multiplier based on volatility."""
        multipliers = {
            "Very High": 0.5,
            "High": 0.75,
            "Normal": 1.0,
            "Low": 1.0,
            "Very Low": 1.0,
        }
        return multipliers.get(classification, 1.0)
