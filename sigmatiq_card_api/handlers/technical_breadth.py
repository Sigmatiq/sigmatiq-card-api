"""
Technical Breadth Handler.

Provides technical breadth indicators (% above MAs, RSI distribution, new highs/lows).
"""

from datetime import date
from typing import Any, Optional

import asyncpg
from fastapi import HTTPException

from .base import BaseCardHandler
from ..models.cards import CardMode


class TechnicalBreadthHandler(BaseCardHandler):
    """Handler for technical_breadth card."""

    async def fetch(
        self, mode: CardMode, symbol: Optional[str], trading_date: date
    ) -> dict[str, Any]:
        """
        Fetch technical breadth data.

        Data source: sb.market_breadth_daily
        """
        query = """
            SELECT pct_above_ma20, pct_above_ma50, pct_above_ma200,
                   advancing, declining, new_highs, new_lows,
                   net_advances, advance_decline_ratio
            FROM sb.market_breadth_daily
            WHERE trading_date = $1
        """

        row = await self._fetch_one(query, {"trading_date": trading_date})

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No technical breadth data available for {trading_date}",
            )

        if mode == CardMode.beginner:
            return self._format_beginner(row)
        elif mode == CardMode.intermediate:
            return self._format_intermediate(row)
        else:
            return self._format_advanced(row)

    def _format_beginner(self, row: asyncpg.Record) -> dict[str, Any]:
        """Beginner: Simple health scores with emojis."""
        pct_above_ma50 = float(row["pct_above_ma50"]) if row["pct_above_ma50"] else 0
        net_advances = int(row["net_advances"]) if row["net_advances"] else 0
        advancing = int(row["advancing"]) if row["advancing"] else 0
        declining = int(row["declining"]) if row["declining"] else 0

        # Overall market health score (0-100)
        health_score = self._calculate_health_score(pct_above_ma50, net_advances)

        health_emoji = "🟢" if health_score >= 70 else "🟡" if health_score >= 40 else "🔴"
        health_label = (" Healthy\ if health_score >= 70 else \Mixed\ if health_score >= 40 else \Weak\)
            "Healthy" if health_score >= 70 else "Mixed" if health_score >= 40 else "Weak"
        )

        return {
            "health_score": health_score,
            "health_label": f"{health_emoji} {health_label}",
 \health_label\: health_label,
            "what_it_means": self._explain_health(health_score),
            "tip": self._add_educational_tip("technical_breadth", CardMode.beginner),
            "bias_block": self._build_bias_block(pct_above_ma50=None if False else float(row["pct_above_ma50"]) if row["pct_above_ma50"] else 0, ad_ratio=None, new_highs=int(row["new_highs"]) if row["new_highs"] else 0, new_lows=int(row["new_lows"]) if row["new_lows"] else 0),
        }

    def _format_intermediate(self, row: asyncpg.Record) -> dict[str, Any]:
        """Intermediate: Detailed breadth metrics."""
        pct_above_ma50 = float(row["pct_above_ma50"]) if row["pct_above_ma50"] else None
        pct_above_ma200 = (
            float(row["pct_above_ma200"]) if row["pct_above_ma200"] else None
        )
        ad_ratio = float(row["advance_decline_ratio"]) if row["advance_decline_ratio"] else None

        return {
            "moving_averages": {
                "above_20d_pct": float(row["pct_above_ma20"]) if row["pct_above_ma20"] else None,
                "above_50d_pct": pct_above_ma50,
                "above_200d_pct": pct_above_ma200,
            },
            "advance_decline": {
                "advancing": int(row["advancing"]) if row["advancing"] else None,
                "declining": int(row["declining"]) if row["declining"] else None,
                "net": int(row["net_advances"]) if row["net_advances"] else None,
                "ratio": ad_ratio,
            },
            "extremes": {
                "new_highs": int(row["new_highs"]) if row["new_highs"] else None,
                "new_lows": int(row["new_lows"]) if row["new_lows"] else None,
            },
            "interpretation": self._interpret_breadth(pct_above_ma50, ad_ratio),
            "bias_block": self._build_bias_block(pct_above_ma50 or 0, ad_ratio or 0, int(row["new_highs"]) if row["new_highs"] else 0, int(row["new_lows"]) if row["new_lows"] else 0),
        }

    def _build_bias_block(self, pct_above_ma50: float, ad_ratio: Optional[float], new_highs: int, new_lows: int) -> dict[str, Any]:
        """Construct bias from breadth metrics."""
        if pct_above_ma50 > 60 and (ad_ratio is None or ad_ratio > 1.0) and new_highs >= new_lows:
            return {"bias": "risk_on", "focus": "trend continuation", "guardrails": "If AD < 1 intraday, reduce risk"}
        if pct_above_ma50 < 40 and (ad_ratio is None or ad_ratio < 1.0) and new_lows > new_highs:
            return {"bias": "risk_off", "focus": "defensive", "guardrails": "Only A+ setups"}
        return {"bias": "neutral", "focus": "stock-picking", "guardrails": "Be selective"}

    def _format_advanced(self, row: asyncpg.Record) -> dict[str, Any]:
        """Advanced: All raw data."""
        return {
            "raw_data": dict(row),
            "derived_metrics": {
                "health_score": self._calculate_health_score(
                    float(row["pct_above_ma50"]) if row["pct_above_ma50"] else 0,
                    int(row["net_advances"]) if row["net_advances"] else 0,
                ),
                "thrust_signal": self._detect_thrust(
                    float(row["pct_above_ma50"]) if row["pct_above_ma50"] else 0
                ),
                "divergence_flag": self._check_divergence(
                    float(row["pct_above_ma50"]) if row["pct_above_ma50"] else 0,
                    float(row["pct_above_ma200"]) if row["pct_above_ma200"] else 0,
                ),
            },
        }

    def _calculate_health_score(self, pct_above_ma50: float, net_advances: int) -> int:
        """Calculate overall market health (0-100)."""
        # Weight 70% on % above MA50, 30% on net advances
        ma_score = min(100, pct_above_ma50)
        ad_score = min(100, max(0, 50 + (net_advances / 10)))  # Normalize around 50
        return int(ma_score * 0.7 + ad_score * 0.3)

    def _explain_health(self, score: int) -> str:
        """Explain what health score means."""
        if score >= 70:
            return "Most stocks are in uptrends. Good time to be invested."
        elif score >= 40:
            return "Market is mixed. Some stocks rising, some falling. Be selective."
        else:
            return "Most stocks are struggling. Consider being defensive."

    def _interpret_breadth(
        self, pct_above_ma50: Optional[float], ad_ratio: Optional[float]
    ) -> str:
        """Interpret breadth for intermediate users."""
        if pct_above_ma50 is None:
            return "Insufficient data for interpretation."

        if pct_above_ma50 > 70:
            return "Strong breadth - broad market participation in uptrend."
        elif pct_above_ma50 > 50:
            return "Positive breadth - majority of stocks in uptrends."
        elif pct_above_ma50 > 30:
            return "Weak breadth - narrow market leadership, divergence risk."
        else:
            return "Poor breadth - most stocks in downtrends, high risk environment."

    def _detect_thrust(self, pct_above_ma50: float) -> bool:
        """Detect breadth thrust (rapid improvement from oversold)."""
        # Thrust detected when >70% above MA50 (simplified)
        return pct_above_ma50 > 70

    def _check_divergence(
        self, pct_above_ma50: float, pct_above_ma200: float
    ) -> bool:
        """Check for divergence between short-term and long-term breadth."""
        # Divergence if short-term strong but long-term weak
        return pct_above_ma50 > 60 and pct_above_ma200 < 40
