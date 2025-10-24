"""
Short Interest Handler - Short selling activity and squeeze potential.

Shows short interest metrics:
- Short interest as % of float
- Days to cover ratio
- Short interest trend
- Squeeze potential scoring

Data source: sb.short_interest (expected table)
"""

from datetime import date, timedelta
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class ShortInterestHandler(BaseCardHandler):
    """Handler for ticker_short_interest card - short selling analysis."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Fetch short interest data for the given symbol.

        Args:
            mode: Response complexity level
            symbol: Stock symbol (required)
            trading_date: Current trading date

        Returns:
            Formatted card data based on mode

        Raises:
            HTTPException: If symbol not provided or data not found
        """
        if not symbol:
            raise HTTPException(
                status_code=400,
                detail="Symbol is required for ticker_short_interest card",
            )

        # Fetch latest short interest data
        latest_query = """
            SELECT
                report_date,
                settlement_date,
                short_interest,
                avg_daily_volume,
                days_to_cover,
                short_pct_float,
                short_pct_outstanding
            FROM sb.short_interest
            WHERE symbol = $1
              AND report_date <= $2
            ORDER BY report_date DESC
            LIMIT 1
        """

        # Fetch historical data for trend analysis
        history_query = """
            SELECT
                report_date,
                short_interest,
                short_pct_float,
                days_to_cover
            FROM sb.short_interest
            WHERE symbol = $1
              AND report_date <= $2
            ORDER BY report_date DESC
            LIMIT 6
        """

        latest = await self._fetch_one(latest_query, {"symbol": symbol, "report_date": trading_date})
        history = await self._fetch_all(history_query, {"symbol": symbol, "report_date": trading_date})

        if not latest:
            raise HTTPException(
                status_code=404,
                detail=f"No short interest data for {symbol}",
            )

        # Calculate trend
        trend = self._calculate_trend(history) if len(history) >= 2 else "unknown"

        # Assess squeeze potential
        squeeze_score = self._assess_squeeze_potential(
            latest.get("short_pct_float"),
            latest.get("days_to_cover"),
            trend
        )

        # Format based on mode
        if mode == CardMode.beginner:
            return self._format_beginner(symbol, latest, trend, squeeze_score)
        elif mode == CardMode.intermediate:
            return self._format_intermediate(symbol, latest, history, trend, squeeze_score)
        else:
            return self._format_advanced(symbol, latest, history, trend, squeeze_score)

    def _format_beginner(
        self,
        symbol: str,
        latest: dict,
        trend: str,
        squeeze_score: int,
    ) -> dict[str, Any]:
        """Format for beginner mode - simplified short interest overview."""
        short_pct = float(latest["short_pct_float"]) if latest.get("short_pct_float") else None
        days_to_cover = float(latest["days_to_cover"]) if latest.get("days_to_cover") else None

        level = self._classify_short_interest(short_pct)

        return {
            "symbol": symbol,
            "short_interest_level": level,
            "short_pct_of_float": round(short_pct, 1) if short_pct else None,
            "days_to_cover": round(days_to_cover, 1) if days_to_cover else None,
            "simple_explanation": self._get_beginner_explanation(level, short_pct),
            "what_it_means": self._get_what_it_means(level),
            "squeeze_potential": "High" if squeeze_score >= 70 else "Moderate" if squeeze_score >= 40 else "Low",
            "trend": self._get_trend_label(trend),
            "report_date": str(latest["report_date"]) if latest.get("report_date") else None,
            "data_age_days": (date.today() - latest["report_date"]).days if latest.get("report_date") else None,
            "educational_tip": "Short interest shows how many shares are sold short (betting on decline). High short interest can lead to 'short squeezes' where shorts are forced to buy, pushing price up.",
            "beginner_warning": "High short interest = high risk. Stock can squeeze up OR continue down. Don't buy just because of short interest.",
        }

    def _format_intermediate(
        self,
        symbol: str,
        latest: dict,
        history: list[dict],
        trend: str,
        squeeze_score: int,
    ) -> dict[str, Any]:
        """Format for intermediate mode - detailed short interest metrics."""
        short_pct = float(latest["short_pct_float"]) if latest.get("short_pct_float") else None
        days_to_cover = float(latest["days_to_cover"]) if latest.get("days_to_cover") else None
        short_interest = int(latest["short_interest"]) if latest.get("short_interest") else None

        return {
            "symbol": symbol,
            "current_metrics": {
                "short_interest_shares": short_interest,
                "short_pct_float": round(short_pct, 2) if short_pct else None,
                "short_pct_outstanding": round(float(latest["short_pct_outstanding"]), 2) if latest.get("short_pct_outstanding") else None,
                "days_to_cover": round(days_to_cover, 2) if days_to_cover else None,
                "avg_daily_volume": int(latest["avg_daily_volume"]) if latest.get("avg_daily_volume") else None,
            },
            "classification": {
                "level": self._classify_short_interest(short_pct),
                "squeeze_potential": "high" if squeeze_score >= 70 else "moderate" if squeeze_score >= 40 else "low",
                "squeeze_score": squeeze_score,
            },
            "trend_analysis": {
                "trend": trend,
                "trend_label": self._get_trend_label(trend),
                "interpretation": self._get_trend_interpretation(trend),
            },
            "historical_data": [
                {
                    "report_date": str(h["report_date"]) if h.get("report_date") else None,
                    "short_pct_float": round(float(h["short_pct_float"]), 2) if h.get("short_pct_float") else None,
                    "days_to_cover": round(float(h["days_to_cover"]), 2) if h.get("days_to_cover") else None,
                }
                for h in history
            ],
            "report_date": str(latest["report_date"]) if latest.get("report_date") else None,
            "data_freshness": f"{(date.today() - latest['report_date']).days} days old" if latest.get("report_date") else "unknown",
            "trading_implications": self._get_trading_implications(short_pct, days_to_cover, trend, squeeze_score),
        }

    def _format_advanced(
        self,
        symbol: str,
        latest: dict,
        history: list[dict],
        trend: str,
        squeeze_score: int,
    ) -> dict[str, Any]:
        """Format for advanced mode - comprehensive short interest analysis."""
        short_pct = float(latest["short_pct_float"]) if latest.get("short_pct_float") else None
        days_to_cover = float(latest["days_to_cover"]) if latest.get("days_to_cover") else None

        # Calculate detailed metrics
        change_analysis = self._analyze_changes(history)

        return {
            "symbol": symbol,
            "raw_metrics": {
                "short_interest_shares": int(latest["short_interest"]) if latest.get("short_interest") else None,
                "short_pct_float": round(short_pct, 4) if short_pct else None,
                "short_pct_outstanding": round(float(latest["short_pct_outstanding"]), 4) if latest.get("short_pct_outstanding") else None,
                "days_to_cover": round(days_to_cover, 4) if days_to_cover else None,
                "avg_daily_volume": int(latest["avg_daily_volume"]) if latest.get("avg_daily_volume") else None,
                "report_date": str(latest["report_date"]) if latest.get("report_date") else None,
                "settlement_date": str(latest["settlement_date"]) if latest.get("settlement_date") else None,
            },
            "classification": {
                "short_interest_level": self._classify_short_interest(short_pct),
                "squeeze_risk_score": squeeze_score,
                "squeeze_potential": self._assess_squeeze_level(squeeze_score),
                "short_interest_percentile": self._estimate_percentile(short_pct),
            },
            "trend_analysis": {
                "overall_trend": trend,
                "recent_change_pct": change_analysis.get("recent_change_pct"),
                "momentum": change_analysis.get("momentum"),
                "consistency": change_analysis.get("consistency"),
            },
            "historical_series": [
                {
                    "report_date": str(h["report_date"]) if h.get("report_date") else None,
                    "short_interest": int(h["short_interest"]) if h.get("short_interest") else None,
                    "short_pct_float": round(float(h["short_pct_float"]), 6) if h.get("short_pct_float") else None,
                    "days_to_cover": round(float(h["days_to_cover"]), 6) if h.get("days_to_cover") else None,
                }
                for h in history
            ],
            "squeeze_analysis": {
                "squeeze_score": squeeze_score,
                "key_factors": self._get_squeeze_factors(short_pct, days_to_cover, trend),
                "catalyst_requirements": self._get_catalyst_requirements(squeeze_score),
                "risk_assessment": self._assess_squeeze_risk(short_pct, days_to_cover),
            },
            "data_quality": {
                "report_date": str(latest["report_date"]) if latest.get("report_date") else None,
                "data_age_days": (date.today() - latest["report_date"]).days if latest.get("report_date") else None,
                "reporting_frequency": "bi-monthly (approximate)",
            },
            "trading_strategy": {
                "recommended_approach": self._get_trading_approach(short_pct, days_to_cover, trend, squeeze_score),
                "risk_factors": self._get_risk_factors(short_pct, trend),
                "position_sizing": self._get_position_sizing_advice(squeeze_score),
            },
        }

    @staticmethod
    def _classify_short_interest(short_pct: Optional[float]) -> str:
        """Classify short interest level."""
        if short_pct is None:
            return "unknown"
        if short_pct > 30:
            return "extremely_high"
        elif short_pct > 20:
            return "very_high"
        elif short_pct > 10:
            return "high"
        elif short_pct > 5:
            return "moderate"
        else:
            return "low"

    @staticmethod
    def _calculate_trend(history: list[dict]) -> str:
        """Calculate short interest trend."""
        if len(history) < 2:
            return "unknown"

        recent = float(history[0]["short_pct_float"]) if history[0].get("short_pct_float") else None
        previous = float(history[1]["short_pct_float"]) if history[1].get("short_pct_float") else None

        if recent is None or previous is None:
            return "unknown"

        change_pct = ((recent - previous) / previous) * 100 if previous > 0 else 0

        if change_pct > 10:
            return "sharply_increasing"
        elif change_pct > 3:
            return "increasing"
        elif change_pct < -10:
            return "sharply_decreasing"
        elif change_pct < -3:
            return "decreasing"
        else:
            return "stable"

    @staticmethod
    def _assess_squeeze_potential(
        short_pct: Optional[float],
        days_to_cover: Optional[float],
        trend: str,
    ) -> int:
        """
        Assess short squeeze potential (0-100 score).

        Factors:
        - High short % of float (0-40 points)
        - High days to cover (0-30 points)
        - Increasing trend (0-30 points)
        """
        score = 0

        # Short % of float contribution (0-40 points)
        if short_pct:
            if short_pct > 30:
                score += 40
            elif short_pct > 20:
                score += 35
            elif short_pct > 15:
                score += 25
            elif short_pct > 10:
                score += 15
            elif short_pct > 5:
                score += 5

        # Days to cover contribution (0-30 points)
        if days_to_cover:
            if days_to_cover > 10:
                score += 30
            elif days_to_cover > 7:
                score += 25
            elif days_to_cover > 5:
                score += 20
            elif days_to_cover > 3:
                score += 10
            elif days_to_cover > 1:
                score += 5

        # Trend contribution (0-30 points)
        trend_scores = {
            "sharply_increasing": 30,
            "increasing": 20,
            "stable": 10,
            "decreasing": 5,
            "sharply_decreasing": 0,
        }
        score += trend_scores.get(trend, 0)

        return min(score, 100)

    @staticmethod
    def _get_beginner_explanation(level: str, short_pct: Optional[float]) -> str:
        """Get beginner explanation of short interest level."""
        if short_pct is None:
            return "Short interest data not available."

        explanations = {
            "extremely_high": f"{short_pct:.1f}% of shares are sold short - EXTREMELY HIGH. This stock is heavily bet against. Risk of short squeeze is high, but so is downside risk.",
            "very_high": f"{short_pct:.1f}% of shares are sold short - VERY HIGH. Many traders are betting this stock will fall. Watch for short squeeze potential.",
            "high": f"{short_pct:.1f}% of shares are sold short - HIGH. Significant bearish sentiment. Could squeeze on positive news.",
            "moderate": f"{short_pct:.1f}% of shares are sold short - MODERATE. Normal level for most stocks.",
            "low": f"{short_pct:.1f}% of shares are sold short - LOW. Not heavily shorted. Low squeeze potential.",
        }
        return explanations.get(level, f"Short interest: {short_pct:.1f}% of float.")

    @staticmethod
    def _get_what_it_means(level: str) -> str:
        """Explain what the level means."""
        meanings = {
            "extremely_high": "Stock is heavily bet against. Either fundamental problems OR setup for massive squeeze.",
            "very_high": "Strong bearish sentiment. Watch for catalyst that could trigger squeeze.",
            "high": "Above-average short interest. Monitor for changes.",
            "moderate": "Normal short interest. Not a significant factor.",
            "low": "Low short interest. Squeeze unlikely.",
        }
        return meanings.get(level, "Short interest level unknown.")

    @staticmethod
    def _get_trend_label(trend: str) -> str:
        """Get human-readable trend label."""
        labels = {
            "sharply_increasing": "Sharply Increasing (⬆️⬆️)",
            "increasing": "Increasing (⬆️)",
            "stable": "Stable (→)",
            "decreasing": "Decreasing (⬇️)",
            "sharply_decreasing": "Sharply Decreasing (⬇️⬇️)",
            "unknown": "Unknown",
        }
        return labels.get(trend, trend)

    @staticmethod
    def _get_trend_interpretation(trend: str) -> str:
        """Get interpretation of trend."""
        interpretations = {
            "sharply_increasing": "Shorts piling in - bearish sentiment growing OR squeeze setup building",
            "increasing": "Short interest growing - more bearish bets being placed",
            "stable": "Short interest stable - no major change in sentiment",
            "decreasing": "Shorts covering - bearish sentiment easing OR squeeze happening",
            "sharply_decreasing": "Heavy short covering - possible squeeze in progress OR fundamental improvement",
        }
        return interpretations.get(trend, "Trend unclear")

    @staticmethod
    def _get_trading_implications(
        short_pct: Optional[float],
        days_to_cover: Optional[float],
        trend: str,
        squeeze_score: int,
    ) -> str:
        """Get trading implications."""
        if squeeze_score >= 70:
            return "High squeeze potential. Watch for catalyst (earnings beat, news). Use tight stops - can move violently in either direction."
        elif squeeze_score >= 40:
            return "Moderate squeeze potential. Monitor closely. Consider small position with defined risk."
        elif short_pct and short_pct > 20:
            return "High short interest but low squeeze score. Likely valid concerns. Avoid unless contrarian with strong thesis."
        else:
            return "Low squeeze potential. Short interest not a major trading factor."

    @staticmethod
    def _analyze_changes(history: list[dict]) -> dict:
        """Analyze historical changes."""
        if len(history) < 2:
            return {"recent_change_pct": None, "momentum": "unknown", "consistency": "unknown"}

        recent = float(history[0]["short_pct_float"]) if history[0].get("short_pct_float") else None
        previous = float(history[1]["short_pct_float"]) if history[1].get("short_pct_float") else None

        if recent is None or previous is None:
            return {"recent_change_pct": None, "momentum": "unknown", "consistency": "unknown"}

        change_pct = ((recent - previous) / previous) * 100 if previous > 0 else 0

        # Assess momentum across all periods
        changes = []
        for i in range(len(history) - 1):
            curr = float(history[i]["short_pct_float"]) if history[i].get("short_pct_float") else None
            prev = float(history[i+1]["short_pct_float"]) if history[i+1].get("short_pct_float") else None

            if curr and prev and prev > 0:
                changes.append((curr - prev) / prev * 100)

        momentum = "unknown"
        if changes:
            avg_change = sum(changes) / len(changes)
            if avg_change > 5:
                momentum = "strongly_increasing"
            elif avg_change > 1:
                momentum = "increasing"
            elif avg_change < -5:
                momentum = "strongly_decreasing"
            elif avg_change < -1:
                momentum = "decreasing"
            else:
                momentum = "stable"

        # Consistency
        consistency = "unknown"
        if len(changes) >= 3:
            if all(c > 0 for c in changes):
                consistency = "consistently_increasing"
            elif all(c < 0 for c in changes):
                consistency = "consistently_decreasing"
            else:
                consistency = "volatile"

        return {
            "recent_change_pct": round(change_pct, 2),
            "momentum": momentum,
            "consistency": consistency,
        }

    @staticmethod
    def _estimate_percentile(short_pct: Optional[float]) -> str:
        """Estimate percentile vs all stocks."""
        if short_pct is None:
            return "unknown"
        if short_pct > 25:
            return "top_1%"
        elif short_pct > 15:
            return "top_5%"
        elif short_pct > 10:
            return "top_10%"
        elif short_pct > 5:
            return "top_25%"
        else:
            return "bottom_75%"

    @staticmethod
    def _assess_squeeze_level(score: int) -> str:
        """Assess squeeze potential level."""
        if score >= 80:
            return "very_high"
        elif score >= 60:
            return "high"
        elif score >= 40:
            return "moderate"
        elif score >= 20:
            return "low"
        else:
            return "very_low"

    @staticmethod
    def _get_squeeze_factors(
        short_pct: Optional[float],
        days_to_cover: Optional[float],
        trend: str,
    ) -> list[str]:
        """Get key factors contributing to squeeze potential."""
        factors = []

        if short_pct and short_pct > 20:
            factors.append(f"High short interest ({short_pct:.1f}% of float)")

        if days_to_cover and days_to_cover > 5:
            factors.append(f"High days to cover ({days_to_cover:.1f} days)")

        if trend in ["sharply_increasing", "increasing"]:
            factors.append("Short interest trending up")

        if not factors:
            factors.append("Low squeeze setup - would need catalyst and short position buildup")

        return factors

    @staticmethod
    def _get_catalyst_requirements(squeeze_score: int) -> str:
        """Get what catalyst would be needed for squeeze."""
        if squeeze_score >= 70:
            return "Any positive catalyst (earnings beat, upgrade, good news) could trigger squeeze"
        elif squeeze_score >= 40:
            return "Significant positive catalyst needed (major earnings beat, strategic announcement)"
        else:
            return "Would need extraordinary catalyst plus short interest buildup"

    @staticmethod
    def _assess_squeeze_risk(short_pct: Optional[float], days_to_cover: Optional[float]) -> str:
        """Assess risk of squeeze."""
        if short_pct and short_pct > 30 and days_to_cover and days_to_cover > 7:
            return "very_high_risk"
        elif short_pct and short_pct > 20:
            return "high_risk"
        elif short_pct and short_pct > 10:
            return "moderate_risk"
        else:
            return "low_risk"

    @staticmethod
    def _get_trading_approach(
        short_pct: Optional[float],
        days_to_cover: Optional[float],
        trend: str,
        squeeze_score: int,
    ) -> str:
        """Get recommended trading approach."""
        if squeeze_score >= 70:
            return "High-risk momentum play. Use small position (1-2% portfolio). Tight stops. Watch for catalyst. Consider options instead of stock."
        elif squeeze_score >= 40:
            return "Speculative play. Use 2-3% max position. Watch for positive catalyst. Trail stops aggressively."
        elif short_pct and short_pct > 20:
            return "High short interest with valid concerns. Avoid long unless strong contrarian thesis. Consider shorting on rallies."
        else:
            return "Short interest not a major factor. Trade based on fundamentals and technicals."

    @staticmethod
    def _get_risk_factors(short_pct: Optional[float], trend: str) -> list[str]:
        """Get risk factors."""
        risks = []

        if short_pct and short_pct > 20:
            risks.append("High short interest may indicate fundamental problems")

        if trend in ["sharply_increasing", "increasing"]:
            risks.append("Growing short interest suggests deteriorating sentiment")

        if short_pct and short_pct > 30:
            risks.append("Extreme volatility possible - can squeeze up OR crash down")

        risks.append("Short interest data is delayed (bi-monthly reports)")

        return risks

    @staticmethod
    def _get_position_sizing_advice(squeeze_score: int) -> str:
        """Get position sizing advice."""
        if squeeze_score >= 70:
            return "1-2% max (high volatility risk)"
        elif squeeze_score >= 40:
            return "2-3% max (moderate volatility risk)"
        else:
            return "Normal position sizing (3-5%)"
