"""
0DTE Flow Handler - Same-day expiration options flow.

Tracks 0DTE (zero days to expiration) options activity (advanced only):
- Total 0DTE open interest
- Flow imbalance (call vs put flow)
- Flow sentiment classification

Data source: sb.options_agg_eod
"""

from datetime import date
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class ZeroDTEFlowHandler(BaseCardHandler):
    """Handler for options_0dte card - 0DTE flow monitoring."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Fetch 0DTE flow data for the given symbol and trading date.

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
                detail="Symbol is required for options_0dte card",
            )

        # Fetch 0DTE flow data
        query = """
            SELECT
                as_of,
                symbol,
                odte_total_oi,
                odte_flow_imbalance
            FROM sb.options_agg_eod
            WHERE symbol = $1 AND as_of = $2
            LIMIT 1
        """
        row = await self._fetch_one(query, {"symbol": symbol, "as_of": trading_date})

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No 0DTE flow data for {symbol} on {trading_date}",
            )

        # Extract values
        odte_oi = int(row["odte_total_oi"]) if row["odte_total_oi"] is not None else 0
        flow_imbalance = float(row["odte_flow_imbalance"]) if row["odte_flow_imbalance"] is not None else 0.0

        # Classify flow sentiment
        flow_sentiment = self._classify_flow_sentiment(flow_imbalance)

        # Format based on mode (0DTE is advanced-only, but provide all modes)
        if mode == CardMode.beginner:
            return self._format_beginner(
                symbol,
                odte_oi,
                flow_imbalance,
                flow_sentiment,
            )
        elif mode == CardMode.intermediate:
            return self._format_intermediate(
                symbol,
                odte_oi,
                flow_imbalance,
                flow_sentiment,
            )
        else:
            return self._format_advanced(
                symbol,
                odte_oi,
                flow_imbalance,
                flow_sentiment,
            )

    @staticmethod
    def _classify_flow_sentiment(flow_imbalance: float) -> str:
        """
        Classify 0DTE flow sentiment based on imbalance.

        Args:
            flow_imbalance: Flow imbalance ratio

        Returns:
            Sentiment: bullish_flow, bearish_flow, or neutral_flow
        """
        if flow_imbalance > 0.2:
            return "bullish_flow"
        elif flow_imbalance < -0.2:
            return "bearish_flow"
        else:
            return "neutral_flow"

    def _format_beginner(
        self,
        symbol: str,
        odte_oi: int,
        flow_imbalance: float,
        sentiment: str,
    ) -> dict[str, Any]:
        """Format for beginner mode - simplified 0DTE concept."""
        emoji = {
            "bullish_flow": "🚀",
            "bearish_flow": "🔻",
            "neutral_flow": "⚖️",
        }.get(sentiment, "➡️")

        return {
            "symbol": symbol,
            "flow_sentiment": sentiment,
            "flow_label": f"{emoji} {self._get_sentiment_label(sentiment)}",
            "total_0dte_oi": odte_oi,
            "flow_imbalance": round(flow_imbalance, 2),
            "simple_explanation": self._get_beginner_explanation(sentiment),
            "intraday_bias": self._get_intraday_bias(sentiment),
            "warning": "0DTE options are extremely risky and can go to zero in minutes. For experienced traders only.",
            "educational_tip": "0DTE = zero days to expiration. These options expire today. Used for intraday speculation with extreme leverage and extreme risk.",
        }

    def _format_intermediate(
        self,
        symbol: str,
        odte_oi: int,
        flow_imbalance: float,
        sentiment: str,
    ) -> dict[str, Any]:
        """Format for intermediate mode - 0DTE flow metrics."""
        return {
            "symbol": symbol,
            "flow_metrics": {
                "total_0dte_oi": odte_oi,
                "flow_imbalance": round(flow_imbalance, 3),
                "flow_sentiment": sentiment,
                "sentiment_label": self._get_sentiment_label(sentiment),
            },
            "interpretation": self._get_intermediate_interpretation(sentiment, flow_imbalance),
            "intraday_implications": self._get_intraday_implications(sentiment),
            "risk_warning": "0DTE options have extreme theta decay and gamma risk. Most expire worthless. Trade with caution.",
        }

    def _format_advanced(
        self,
        symbol: str,
        odte_oi: int,
        flow_imbalance: float,
        sentiment: str,
    ) -> dict[str, Any]:
        """Format for advanced mode - full 0DTE flow analysis."""
        return {
            "symbol": symbol,
            "raw_metrics": {
                "odte_total_oi": odte_oi,
                "odte_flow_imbalance": round(flow_imbalance, 6),
            },
            "flow_analysis": {
                "sentiment": sentiment,
                "sentiment_strength": self._assess_sentiment_strength(flow_imbalance),
                "call_vs_put_ratio": self._calculate_call_put_ratio(flow_imbalance),
            },
            "dealer_hedging": {
                "expected_behavior": self._get_dealer_behavior(sentiment),
                "intraday_pressure": "Upward" if sentiment == "bullish_flow" else "Downward" if sentiment == "bearish_flow" else "Neutral",
            },
            "trading_considerations": {
                "gamma_risk": "extreme",
                "theta_decay": "extreme",
                "directional_bias": self._get_directional_bias(sentiment),
                "dealer_hedging_impact": "High - dealers must hedge 0DTE positions aggressively",
            },
            "thresholds": {
                "bullish_flow": ">0.2",
                "neutral_flow": "-0.2 to 0.2",
                "bearish_flow": "<-0.2",
            },
        }

    @staticmethod
    def _get_sentiment_label(sentiment: str) -> str:
        """Get human-readable sentiment label."""
        labels = {
            "bullish_flow": "Bullish Flow (Heavy Call Buying)",
            "bearish_flow": "Bearish Flow (Heavy Put Buying)",
            "neutral_flow": "Neutral Flow (Balanced)",
        }
        return labels.get(sentiment, sentiment)

    @staticmethod
    def _get_beginner_explanation(sentiment: str) -> str:
        """Get beginner-friendly explanation."""
        explanations = {
            "bullish_flow": "Traders are heavily buying call options expiring today, betting on upward movement before market close.",
            "bearish_flow": "Traders are heavily buying put options expiring today, betting on downward movement before market close.",
            "neutral_flow": "Call and put buying is balanced. No clear directional bias from 0DTE traders.",
        }
        return explanations.get(sentiment, "")

    @staticmethod
    def _get_intraday_bias(sentiment: str) -> str:
        """Get intraday directional bias."""
        biases = {
            "bullish_flow": "Expect intraday strength - dealers hedging call sales will buy stock",
            "bearish_flow": "Expect intraday weakness - dealers hedging put sales will sell stock",
            "neutral_flow": "No clear intraday bias from 0DTE flow",
        }
        return biases.get(sentiment, "")

    @staticmethod
    def _get_intermediate_interpretation(sentiment: str, flow_imbalance: float) -> str:
        """Get intermediate interpretation."""
        base = f"Flow imbalance: {round(flow_imbalance, 2)} ({sentiment.replace('_', ' ')})"

        strength = ""
        if abs(flow_imbalance) > 0.4:
            strength = ". Extremely strong signal."
        elif abs(flow_imbalance) > 0.3:
            strength = ". Strong signal."

        return base + strength

    @staticmethod
    def _get_intraday_implications(sentiment: str) -> str:
        """Get intraday trading implications."""
        implications = {
            "bullish_flow": "Watch for intraday rallies, especially in first and last hour. Dealers hedging sold calls will buy stock, creating upward pressure.",
            "bearish_flow": "Watch for intraday selloffs, especially in first and last hour. Dealers hedging sold puts will sell stock, creating downward pressure.",
            "neutral_flow": "No strong hedging pressure from 0DTE flow. Price action driven by other factors.",
        }
        return implications.get(sentiment, "")

    @staticmethod
    def _assess_sentiment_strength(flow_imbalance: float) -> str:
        """Assess sentiment strength."""
        abs_imbalance = abs(flow_imbalance)
        if abs_imbalance > 0.4:
            return "very strong"
        elif abs_imbalance > 0.3:
            return "strong"
        elif abs_imbalance > 0.2:
            return "moderate"
        else:
            return "weak"

    @staticmethod
    def _calculate_call_put_ratio(flow_imbalance: float) -> str:
        """Calculate implied call/put ratio from imbalance."""
        # Simplified calculation for display
        if flow_imbalance > 0:
            return f"~{round(1 + flow_imbalance, 2)}:1 (calls:puts)"
        elif flow_imbalance < 0:
            return f"~1:{round(1 - flow_imbalance, 2)} (calls:puts)"
        else:
            return "~1:1 (balanced)"

    @staticmethod
    def _get_dealer_behavior(sentiment: str) -> str:
        """Get expected dealer hedging behavior."""
        behaviors = {
            "bullish_flow": "Dealers sell calls to retail, must hedge by buying stock (creates upward pressure)",
            "bearish_flow": "Dealers sell puts to retail, must hedge by selling stock (creates downward pressure)",
            "neutral_flow": "Balanced hedging - no clear directional pressure",
        }
        return behaviors.get(sentiment, "")

    @staticmethod
    def _get_directional_bias(sentiment: str) -> str:
        """Get directional bias for trading."""
        biases = {
            "bullish_flow": "Bullish (expect intraday strength)",
            "bearish_flow": "Bearish (expect intraday weakness)",
            "neutral_flow": "Neutral (no clear bias)",
        }
        return biases.get(sentiment, "")
