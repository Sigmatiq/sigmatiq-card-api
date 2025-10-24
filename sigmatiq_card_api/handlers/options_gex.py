"""
GEX Handler - Dealer gamma exposure and positioning.

Shows dealer positioning metrics (advanced only):
- Dealer net delta
- Zero-gamma level
- Total GEX (gamma exposure)
- Distance to zero-gamma level

Data sources:
- sb.options_agg_eod (GEX metrics)
- sb.symbol_derived_eod (current price)
"""

from datetime import date
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class GEXHandler(BaseCardHandler):
    """Handler for options_gex card - dealer gamma exposure."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Fetch GEX data for the given symbol and trading_date.

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
                detail="Symbol is required for options_gex card",
            )

        # Fetch GEX data
        query = """
            SELECT
                a.as_of,
                a.symbol,
                a.dealer_net_delta,
                a.zero_gamma_level,
                a.gex,
                d.close as current_price
            FROM sb.options_agg_eod a
            JOIN sb.symbol_derived_eod d ON d.symbol = a.symbol AND d.trading_date = a.as_of
            WHERE a.symbol = $1 AND a.as_of = $2
            LIMIT 1
        """
        row = await self._fetch_one(query, {"symbol": symbol, "as_of": trading_date})

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No GEX data for {symbol} on {trading_date}",
            )

        # Extract values
        dealer_net_delta = float(row["dealer_net_delta"]) if row["dealer_net_delta"] is not None else None
        zero_gamma_level = float(row["zero_gamma_level"]) if row["zero_gamma_level"] is not None else None
        gex = float(row["gex"]) if row["gex"] is not None else None
        current_price = float(row["current_price"]) if row["current_price"] else 0

        # Calculate distance to zero gamma
        dist_to_zero_gamma_pct = None
        if zero_gamma_level and zero_gamma_level > 0 and current_price > 0:
            dist_to_zero_gamma_pct = ((current_price - zero_gamma_level) / zero_gamma_level) * 100

        # Determine positioning
        gex_positioning = "dealers_long_gamma" if gex and gex > 0 else "dealers_short_gamma" if gex else "unknown"

        # Format based on mode (GEX is advanced-only, but provide all modes)
        if mode == CardMode.beginner:
            return self._format_beginner(
                symbol,
                gex_positioning,
                zero_gamma_level,
                current_price,
            )
        elif mode == CardMode.intermediate:
            return self._format_intermediate(
                symbol,
                dealer_net_delta,
                zero_gamma_level,
                gex_positioning,
                current_price,
                dist_to_zero_gamma_pct,
            )
        else:
            return self._format_advanced(
                symbol,
                dealer_net_delta,
                zero_gamma_level,
                gex,
                gex_positioning,
                current_price,
                dist_to_zero_gamma_pct,
            )

    def _format_beginner(
        self,
        symbol: str,
        positioning: str,
        zero_gamma: Optional[float],
        current_price: float,
    ) -> dict[str, Any]:
        """Format for beginner mode - simplified GEX concept."""
        return {
            "symbol": symbol,
            "market_makers_position": "Providing liquidity" if positioning == "dealers_long_gamma" else "Pulling liquidity" if positioning == "dealers_short_gamma" else "Unknown",
            "volatility_expectation": "Lower volatility expected" if positioning == "dealers_long_gamma" else "Higher volatility expected" if positioning == "dealers_short_gamma" else "Unknown",
            "key_level": round(zero_gamma, 2) if zero_gamma else None,
            "current_price": round(current_price, 2),
            "simple_explanation": self._get_beginner_explanation(positioning),
            "educational_tip": "Dealers (market makers) hedge options by buying/selling stock. Positive gamma = they stabilize price. Negative gamma = they amplify moves.",
        }

    def _format_intermediate(
        self,
        symbol: str,
        net_delta: Optional[float],
        zero_gamma: Optional[float],
        positioning: str,
        current_price: float,
        dist_pct: Optional[float],
    ) -> dict[str, Any]:
        """Format for intermediate mode - GEX metrics."""
        return {
            "symbol": symbol,
            "dealer_positioning": positioning,
            "positioning_label": self._get_positioning_label(positioning),
            "metrics": {
                "dealer_net_delta": round(net_delta) if net_delta is not None else None,
                "zero_gamma_level": round(zero_gamma, 2) if zero_gamma else None,
                "current_price": round(current_price, 2),
                "distance_to_zero_gamma_pct": round(dist_pct, 2) if dist_pct is not None else None,
            },
            "volatility_regime": "Lower vol expected" if positioning == "dealers_long_gamma" else "Higher vol expected",
            "interpretation": self._get_intermediate_interpretation(positioning, dist_pct),
            "trading_implications": self._get_trading_implications(positioning),
        }

    def _format_advanced(
        self,
        symbol: str,
        net_delta: Optional[float],
        zero_gamma: Optional[float],
        gex: Optional[float],
        positioning: str,
        current_price: float,
        dist_pct: Optional[float],
    ) -> dict[str, Any]:
        """Format for advanced mode - full GEX analysis."""
        return {
            "symbol": symbol,
            "raw_metrics": {
                "dealer_net_delta": round(net_delta, 2) if net_delta is not None else None,
                "zero_gamma_level": round(zero_gamma, 4) if zero_gamma else None,
                "total_gex": round(gex, 2) if gex is not None else None,
                "current_price": round(current_price, 4),
            },
            "positioning_analysis": {
                "gex_sign": "positive" if gex and gex > 0 else "negative" if gex else "unknown",
                "positioning": positioning,
                "positioning_description": self._get_positioning_description(positioning),
            },
            "price_levels": {
                "zero_gamma_level": round(zero_gamma, 4) if zero_gamma else None,
                "distance_to_zero_pct": round(dist_pct, 4) if dist_pct is not None else None,
                "price_vs_zero_gamma": "above" if dist_pct and dist_pct > 0 else "below" if dist_pct and dist_pct < 0 else "at",
            },
            "hedging_behavior": {
                "above_zero_gamma": self._get_hedging_behavior(positioning, True),
                "below_zero_gamma": self._get_hedging_behavior(positioning, False),
            },
            "volatility_implications": {
                "expected_volatility": "suppressed" if positioning == "dealers_long_gamma" else "amplified" if positioning == "dealers_short_gamma" else "unknown",
                "range_bound_likely": positioning == "dealers_long_gamma",
                "breakout_potential": positioning == "dealers_short_gamma",
            },
        }

    @staticmethod
    def _get_positioning_label(positioning: str) -> str:
        """Get human-readable positioning label."""
        labels = {
            "dealers_long_gamma": "Dealers Long Gamma",
            "dealers_short_gamma": "Dealers Short Gamma",
            "unknown": "Unknown",
        }
        return labels.get(positioning, positioning)

    @staticmethod
    def _get_positioning_description(positioning: str) -> str:
        """Get detailed positioning description."""
        descriptions = {
            "dealers_long_gamma": "Dealers are long gamma - they will dampen volatility by buying dips and selling rips (providing liquidity)",
            "dealers_short_gamma": "Dealers are short gamma - they will amplify moves by selling dips and buying rips (pulling liquidity)",
            "unknown": "Positioning unknown",
        }
        return descriptions.get(positioning, "")

    @staticmethod
    def _get_hedging_behavior(positioning: str, above_zero_gamma: bool) -> str:
        """Get hedging behavior description."""
        if positioning == "dealers_long_gamma":
            if above_zero_gamma:
                return "Dealers sell into strength (dampens rallies)"
            else:
                return "Dealers buy into weakness (supports dips)"
        elif positioning == "dealers_short_gamma":
            if above_zero_gamma:
                return "Dealers buy into strength (amplifies rallies)"
            else:
                return "Dealers sell into weakness (amplifies selloffs)"
        else:
            return "Unknown"

    @staticmethod
    def _get_beginner_explanation(positioning: str) -> str:
        """Get beginner-friendly explanation."""
        explanations = {
            "dealers_long_gamma": "Market makers are positioned to stabilize the price. They will buy when price drops and sell when price rises. This tends to keep the stock in a range.",
            "dealers_short_gamma": "Market makers are positioned to amplify price moves. They will sell when price drops and buy when price rises. This can lead to bigger swings and breakouts.",
            "unknown": "Market maker positioning unclear.",
        }
        return explanations.get(positioning, "")

    @staticmethod
    def _get_intermediate_interpretation(positioning: str, dist_pct: Optional[float]) -> str:
        """Get intermediate interpretation."""
        base = f"Dealers are {positioning.replace('dealers_', '').replace('_', ' ')}."

        if dist_pct is not None:
            location = f" Price is {abs(round(dist_pct))}% {'above' if dist_pct > 0 else 'below'} zero-gamma level."
            if abs(dist_pct) < 2:
                location += " Price near zero-gamma acts as magnet."
        else:
            location = ""

        return base + location

    @staticmethod
    def _get_trading_implications(positioning: str) -> str:
        """Get trading implications."""
        implications = {
            "dealers_long_gamma": "Expect range-bound price action. Fade moves - buy dips, sell rips. Iron condors and theta strategies favorable.",
            "dealers_short_gamma": "Expect increased volatility. Breakout strategies favored. Avoid selling premium. Watch for explosive moves.",
            "unknown": "Unclear positioning - use caution with volatility strategies.",
        }
        return implications.get(positioning, "")
