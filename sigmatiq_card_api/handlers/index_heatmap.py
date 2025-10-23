"""
Index Heatmap card handler.

Provides performance comparison of major market indices (S&P 500, Nasdaq, Dow, Russell 2000).
"""

from datetime import date
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class IndexHeatmapHandler(BaseCardHandler):
    """Handler for index heatmap card."""

    # Major index ETF symbols
    INDICES = {
        "SPY": "S&P 500",
        "QQQ": "Nasdaq 100",
        "DIA": "Dow Jones",
        "IWM": "Russell 2000",
    }

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Fetch index heatmap data.

        Args:
            mode: Complexity level
            symbol: Not used (market-wide card)
            trading_date: Trading date

        Returns:
            Formatted index heatmap data
        """
        # Query all major indices
        query = """
            SELECT
                symbol,
                close,
                r_1d_pct,
                r_5d_pct,
                r_1m_pct,
                r_ytd_pct,
                volume,
                rvol
            FROM sb.symbol_derived_eod
            WHERE symbol = ANY($1) AND trading_date = $2
        """

        rows = await self._fetch_all(
            query, {"symbols": list(self.INDICES.keys()), "trading_date": trading_date}
        )

        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No index data available for {trading_date}",
            )

        # Convert to dict by symbol
        indices_data = {row["symbol"]: row for row in rows}

        # Ensure we have all indices
        missing = set(self.INDICES.keys()) - set(indices_data.keys())
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"Missing data for indices: {', '.join(missing)}",
            )

        # Format based on mode
        if mode == CardMode.beginner:
            return self._format_beginner(indices_data)

        elif mode == CardMode.intermediate:
            return self._format_intermediate(indices_data)

        else:  # advanced
            return self._format_advanced(indices_data)

    def _format_beginner(self, indices_data: dict) -> dict[str, Any]:
        """Format for beginner mode (simplified, plain language)."""
        indices = []

        for symbol, name in self.INDICES.items():
            row = indices_data[symbol]
            r_1d_pct = row["r_1d_pct"] or 0

            # Determine performance category
            if r_1d_pct > 1:
                performance = "strong gain"
                color = "green"
            elif r_1d_pct > 0:
                performance = "slight gain"
                color = "light_green"
            elif r_1d_pct < -1:
                performance = "strong loss"
                color = "red"
            elif r_1d_pct < 0:
                performance = "slight loss"
                color = "light_red"
            else:
                performance = "flat"
                color = "gray"

            indices.append({
                "symbol": symbol,
                "name": name,
                "change_pct": r_1d_pct,
                "change_label": f"{r_1d_pct:+.2f}%",
                "performance": performance,
                "color": color,
            })

        # Determine market leader
        leader = max(indices, key=lambda x: x["change_pct"])
        laggard = min(indices, key=lambda x: x["change_pct"])

        return {
            "indices": indices,
            "leader": {
                "name": leader["name"],
                "change_pct": leader["change_pct"],
                "label": f"{leader['name']} leading at {leader['change_pct']:+.2f}%",
            },
            "laggard": {
                "name": laggard["name"],
                "change_pct": laggard["change_pct"],
                "label": f"{laggard['name']} lagging at {laggard['change_pct']:+.2f}%",
            },
            "market_mood": self._get_market_mood([idx["change_pct"] for idx in indices]),
            "educational_tip": self._add_educational_tip("index_heatmap", CardMode.beginner),
        }

    def _format_intermediate(self, indices_data: dict) -> dict[str, Any]:
        """Format for intermediate mode (multiple timeframes)."""
        indices = []

        for symbol, name in self.INDICES.items():
            row = indices_data[symbol]

            indices.append({
                "symbol": symbol,
                "name": name,
                "r_1d_pct": row["r_1d_pct"] or 0,
                "r_5d_pct": row["r_5d_pct"] or 0,
                "r_1m_pct": row["r_1m_pct"] or 0,
                "r_ytd_pct": row["r_ytd_pct"] or 0,
                "rvol": row["rvol"] or 1.0,
            })

        # Calculate rotation analysis
        tech_heavy = indices_data["QQQ"]["r_1d_pct"] or 0
        broader_market = indices_data["SPY"]["r_1d_pct"] or 0
        small_caps = indices_data["IWM"]["r_1d_pct"] or 0

        rotation = self._analyze_rotation(tech_heavy, broader_market, small_caps)

        return {
            "indices": indices,
            "rotation_analysis": rotation,
            "strongest_timeframe": self._get_strongest_timeframe(indices),
            "correlation": self._assess_correlation(indices),
        }

    def _format_advanced(self, indices_data: dict) -> dict[str, Any]:
        """Format for advanced mode (all fields, raw data)."""
        indices = []

        for symbol, name in self.INDICES.items():
            row = indices_data[symbol]

            indices.append({
                "symbol": symbol,
                "name": name,
                "close": row["close"],
                "r_1d_pct": row["r_1d_pct"],
                "r_5d_pct": row["r_5d_pct"],
                "r_1m_pct": row["r_1m_pct"],
                "r_ytd_pct": row["r_ytd_pct"],
                "volume": row["volume"],
                "rvol": row["rvol"],
            })

        return {
            "indices": indices,
            "timestamp": str(indices_data["SPY"]["trading_date"]) if "SPY" in indices_data else None,
        }

    def _get_market_mood(self, changes: list[float]) -> str:
        """Determine overall market mood from index changes."""
        avg_change = sum(changes) / len(changes)
        positive_count = sum(1 for c in changes if c > 0)

        if positive_count == len(changes) and avg_change > 1:
            return "Very Positive - All indices up strongly"
        elif positive_count == len(changes):
            return "Positive - All indices gaining"
        elif positive_count == 0 and avg_change < -1:
            return "Very Negative - All indices down strongly"
        elif positive_count == 0:
            return "Negative - All indices losing"
        else:
            return "Mixed - Diverging index performance"

    def _analyze_rotation(
        self, tech_heavy: float, broader_market: float, small_caps: float
    ) -> str:
        """Analyze sector/size rotation based on relative performance."""
        if tech_heavy > broader_market > small_caps:
            return "Growth/Tech leadership - Large cap tech outperforming"
        elif small_caps > broader_market > tech_heavy:
            return "Small cap leadership - Risk-on rotation"
        elif abs(tech_heavy - broader_market) < 0.2:
            return "Broad market move - Little sector rotation"
        elif tech_heavy < broader_market:
            return "Value rotation - Broader market outperforming tech"
        else:
            return "Mixed rotation - No clear sector leadership"

    def _get_strongest_timeframe(self, indices: list) -> str:
        """Determine which timeframe shows strongest performance."""
        avg_1d = sum(idx["r_1d_pct"] for idx in indices) / len(indices)
        avg_5d = sum(idx["r_5d_pct"] for idx in indices) / len(indices)
        avg_1m = sum(idx["r_1m_pct"] for idx in indices) / len(indices)

        timeframes = {"1d": abs(avg_1d), "5d": abs(avg_5d), "1m": abs(avg_1m)}
        strongest = max(timeframes, key=timeframes.get)

        return {
            "1d": "Today",
            "5d": "Past week",
            "1m": "Past month",
        }[strongest]

    def _assess_correlation(self, indices: list) -> str:
        """Assess if indices are moving together or diverging."""
        changes_1d = [idx["r_1d_pct"] for idx in indices]

        # Simple correlation check: all same sign?
        all_positive = all(c > 0 for c in changes_1d)
        all_negative = all(c < 0 for c in changes_1d)

        if all_positive or all_negative:
            return "High - All indices moving together"
        else:
            return "Low - Indices diverging (sector rotation)"
