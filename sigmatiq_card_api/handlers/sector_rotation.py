"""
Sector Rotation Handler.

Provides sector performance analysis using major sector ETFs (SPDR Select Sector).
"""

from datetime import date
from typing import Any, Optional

import asyncpg
from fastapi import HTTPException

from .base import BaseCardHandler
from ..models.cards import CardMode


class SectorRotationHandler(BaseCardHandler):
    """Handler for sector_rotation card."""

    # SPDR Select Sector ETFs
    SECTORS = {
        "XLF": "Financials",
        "XLE": "Energy",
        "XLK": "Technology",
        "XLV": "Health Care",
        "XLI": "Industrials",
        "XLP": "Consumer Staples",
        "XLY": "Consumer Discretionary",
        "XLU": "Utilities",
        "XLRE": "Real Estate",
        "XLB": "Materials",
        "XLC": "Communications",
    }

    async def fetch(
        self, mode: CardMode, symbol: Optional[str], trading_date: date
    ) -> dict[str, Any]:
        """
        Fetch sector rotation data.

        Data source: sb.symbol_derived_eod for sector ETFs
        """
        query = """
            SELECT symbol, close, r_1d_pct, r_5d_pct, r_1m_pct, r_ytd_pct,
                   volume, rvol, rsi_14, dist_ma50
            FROM sb.symbol_derived_eod
            WHERE symbol = ANY($1) AND trading_date = $2
            ORDER BY r_1d_pct DESC NULLS LAST
        """

        rows = await self._fetch_all(
            query, {"symbols": list(self.SECTORS.keys()), "trading_date": trading_date}
        )

        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No sector data available for {trading_date}",
            )

        # Build sector data
        sectors = [
            {
                "symbol": row["symbol"],
                "name": self.SECTORS.get(row["symbol"], row["symbol"]),
                "close": float(row["close"]) if row["close"] else None,
                "r_1d_pct": float(row["r_1d_pct"]) if row["r_1d_pct"] else None,
                "r_5d_pct": float(row["r_5d_pct"]) if row["r_5d_pct"] else None,
                "r_1m_pct": float(row["r_1m_pct"]) if row["r_1m_pct"] else None,
                "r_ytd_pct": float(row["r_ytd_pct"]) if row["r_ytd_pct"] else None,
                "volume": int(row["volume"]) if row["volume"] else None,
                "rvol": float(row["rvol"]) if row["rvol"] else None,
                "rsi_14": float(row["rsi_14"]) if row["rsi_14"] else None,
                "dist_ma50": float(row["dist_ma50"]) if row["dist_ma50"] else None,
            }
            for row in rows
        ]

        if mode == CardMode.beginner:
            return self._format_beginner(sectors)
        elif mode == CardMode.intermediate:
            return self._format_intermediate(sectors)
        else:
            return self._format_advanced(sectors)

    def _format_beginner(self, sectors: list[dict]) -> dict[str, Any]:
        """Beginner: Top 3 leaders and laggards with simple explanations."""
        # Sort by 1-day performance
        by_1d = sorted(
            [s for s in sectors if s["r_1d_pct"] is not None],
            key=lambda x: x["r_1d_pct"],
            reverse=True,
        )

        leaders = by_1d[:3] if len(by_1d) >= 3 else by_1d
        laggards = by_1d[-3:] if len(by_1d) >= 3 else []

        return {
            "summary": f"{'🟢' if leaders and leaders[0]['r_1d_pct'] > 0 else '🔴'} {leaders[0]['name'] if leaders else 'N/A'} is leading today",
            "leaders": [
                {
                    "sector": s["name"],
                    "today": f"{s['r_1d_pct']:+.1f}%",
                    "emoji": self._sector_emoji(s["symbol"]),
                }
                for s in leaders
            ],
            "laggards": [
                {
                    "sector": s["name"],
                    "today": f"{s['r_1d_pct']:+.1f}%",
                    "emoji": self._sector_emoji(s["symbol"]),
                }
                for s in laggards
            ],
            "what_it_means": "Strong sectors show where investors are putting money. Weak sectors show where they're taking it out.",
            "tip": self._add_educational_tip("sector_rotation", CardMode.beginner),
        }

    def _format_intermediate(self, sectors: list[dict]) -> dict[str, Any]:
        """Intermediate: All sectors with multiple timeframes."""
        rotation_type = self._detect_rotation_type(sectors)

        return {
            "rotation_type": rotation_type,
            "sectors": [
                {
                    "symbol": s["symbol"],
                    "name": s["name"],
                    "performance": {
                        "today": s["r_1d_pct"],
                        "week": s["r_5d_pct"],
                        "month": s["r_1m_pct"],
                        "ytd": s["r_ytd_pct"],
                    },
                    "technical": {
                        "rsi": s["rsi_14"],
                        "dist_ma50_pct": s["dist_ma50"],
                        "rvol": s["rvol"],
                    },
                }
                for s in sectors
            ],
            "insights": self._generate_insights(sectors),
        }

    def _format_advanced(self, sectors: list[dict]) -> dict[str, Any]:
        """Advanced: Full sector data with correlations and dispersion."""
        return {
            "sectors": sectors,
            "statistics": {
                "avg_1d_pct": self._calc_avg([s["r_1d_pct"] for s in sectors]),
                "dispersion_1d": self._calc_std([s["r_1d_pct"] for s in sectors]),
                "median_rsi": self._calc_median([s["rsi_14"] for s in sectors]),
                "breadth_pct": self._calc_breadth(sectors),
            },
            "rotation_type": self._detect_rotation_type(sectors),
        }

    def _sector_emoji(self, symbol: str) -> str:
        """Get emoji for sector."""
        emojis = {
            "XLF": "🏦",
            "XLE": "⛽",
            "XLK": "💻",
            "XLV": "🏥",
            "XLI": "🏭",
            "XLP": "🛒",
            "XLY": "🛍️",
            "XLU": "⚡",
            "XLRE": "🏘️",
            "XLB": "⛏️",
            "XLC": "📡",
        }
        return emojis.get(symbol, "📊")

    def _detect_rotation_type(self, sectors: list[dict]) -> str:
        """Detect rotation pattern."""
        # Count how many sectors are positive
        positive = sum(1 for s in sectors if s["r_1d_pct"] and s["r_1d_pct"] > 0)
        total = len([s for s in sectors if s["r_1d_pct"] is not None])

        if total == 0:
            return "Unknown"

        pct_positive = positive / total

        if pct_positive >= 0.8:
            return "Risk-On (broad buying)"
        elif pct_positive <= 0.2:
            return "Risk-Off (broad selling)"
        elif pct_positive >= 0.6:
            return "Selective Rotation (mixed)"
        else:
            return "Defensive Shift (risk aversion)"

    def _generate_insights(self, sectors: list[dict]) -> list[str]:
        """Generate trading insights."""
        insights = []

        # Check for strong leadership
        top = sorted(
            [s for s in sectors if s["r_1d_pct"] is not None],
            key=lambda x: x["r_1d_pct"],
            reverse=True,
        )
        if top and top[0]["r_1d_pct"] > 2:
            insights.append(
                f"{top[0]['name']} showing strong momentum (+{top[0]['r_1d_pct']:.1f}%)"
            )

        # Check for divergence
        if len(top) >= 2:
            spread = top[0]["r_1d_pct"] - top[-1]["r_1d_pct"]
            if spread > 5:
                insights.append(
                    f"High sector dispersion ({spread:.1f}% range) suggests selective market"
                )

        # Check for tech leadership (often risk-on signal)
        tech = next((s for s in sectors if s["symbol"] == "XLK"), None)
        if tech and tech["r_1d_pct"] and tech["r_1d_pct"] > 1:
            insights.append("Technology leading (risk-on signal)")

        # Check for defensive strength (often risk-off signal)
        utils = next((s for s in sectors if s["symbol"] == "XLU"), None)
        staples = next((s for s in sectors if s["symbol"] == "XLP"), None)
        if (
            utils
            and staples
            and utils["r_1d_pct"]
            and staples["r_1d_pct"]
            and utils["r_1d_pct"] > 0.5
            and staples["r_1d_pct"] > 0.5
        ):
            insights.append("Defensive sectors outperforming (caution signal)")

        return insights if insights else ["No notable patterns detected"]

    def _calc_avg(self, values: list[Optional[float]]) -> Optional[float]:
        """Calculate average, ignoring None."""
        valid = [v for v in values if v is not None]
        return sum(valid) / len(valid) if valid else None

    def _calc_std(self, values: list[Optional[float]]) -> Optional[float]:
        """Calculate standard deviation."""
        valid = [v for v in values if v is not None]
        if not valid:
            return None
        avg = sum(valid) / len(valid)
        variance = sum((v - avg) ** 2 for v in valid) / len(valid)
        return variance**0.5

    def _calc_median(self, values: list[Optional[float]]) -> Optional[float]:
        """Calculate median."""
        valid = sorted([v for v in values if v is not None])
        if not valid:
            return None
        mid = len(valid) // 2
        if len(valid) % 2 == 0:
            return (valid[mid - 1] + valid[mid]) / 2
        return valid[mid]

    def _calc_breadth(self, sectors: list[dict]) -> Optional[float]:
        """Calculate sector breadth (% positive)."""
        with_data = [s for s in sectors if s["r_1d_pct"] is not None]
        if not with_data:
            return None
        positive = sum(1 for s in with_data if s["r_1d_pct"] > 0)
        return (positive / len(with_data)) * 100
