"""
Economic Calendar Handler - Macroeconomic events and data releases.

Shows upcoming economic events:
- Fed meetings
- CPI/PPI releases
- Employment data
- GDP reports
- Impact levels

Data source: sb.economic_calendar (expected table)
"""

from datetime import date, timedelta
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class EconomicCalendarHandler(BaseCardHandler):
    """Handler for economic_calendar card - macro economic events."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Fetch economic calendar data for upcoming events.

        Args:
            mode: Response complexity level
            symbol: Stock symbol (not required for economic calendar)
            trading_date: Current trading date

        Returns:
            Formatted card data based on mode

        Raises:
            HTTPException: If no economic data found
        """
        # Fetch upcoming economic events
        upcoming_query = """
            SELECT
                event_date,
                event_time,
                event_name,
                event_category,  -- 'employment', 'inflation', 'monetary_policy', 'gdp', etc.
                impact_level,  -- 'low', 'medium', 'high'
                country,
                previous_value,
                consensus_estimate,
                actual_value
            FROM sb.economic_calendar
            WHERE event_date >= $1
              AND event_date <= $2
            ORDER BY event_date ASC, impact_level DESC
            LIMIT 30
        """

        # Fetch recent past events (for comparison)
        past_query = """
            SELECT
                event_date,
                event_name,
                event_category,
                impact_level,
                previous_value,
                consensus_estimate,
                actual_value
            FROM sb.economic_calendar
            WHERE event_date < $1
              AND event_date >= $2
              AND actual_value IS NOT NULL
            ORDER BY event_date DESC
            LIMIT 10
        """

        # Date ranges
        end_date = trading_date + timedelta(days=14)  # Next 2 weeks
        start_past = trading_date - timedelta(days=7)  # Past week

        upcoming = await self._fetch_all(
            upcoming_query,
            {"start_date": trading_date, "end_date": end_date}
        )

        past = await self._fetch_all(
            past_query,
            {"trading_date": trading_date, "start_past": start_past}
        )

        if not upcoming and not past:
            raise HTTPException(
                status_code=404,
                detail="No economic calendar data available",
            )

        # Categorize by impact
        high_impact = [e for e in upcoming if e.get("impact_level") == "high"]
        medium_impact = [e for e in upcoming if e.get("impact_level") == "medium"]

        # Format based on mode
        if mode == CardMode.beginner:
            return self._format_beginner(upcoming, past, high_impact)
        elif mode == CardMode.intermediate:
            return self._format_intermediate(upcoming, past, high_impact, medium_impact)
        else:
            return self._format_advanced(upcoming, past)

    def _format_beginner(
        self,
        upcoming: list[dict],
        past: list[dict],
        high_impact: list[dict],
    ) -> dict[str, Any]:
        """Format for beginner mode - simplified economic calendar."""
        return {
            "upcoming_events_count": len(upcoming),
            "high_impact_events": [
                {
                    "event_name": self._simplify_event_name(e["event_name"]),
                    "date": str(e["event_date"]),
                    "days_until": (e["event_date"] - date.today()).days,
                    "impact": "High Market Impact",
                    "simple_explanation": self._explain_event(e["event_category"]),
                }
                for e in high_impact[:5]
            ],
            "next_key_event": {
                "name": self._simplify_event_name(high_impact[0]["event_name"]),
                "date": str(high_impact[0]["event_date"]),
                "days_until": (high_impact[0]["event_date"] - date.today()).days,
                "what_to_watch": self._get_what_to_watch(high_impact[0]["event_category"]),
            } if high_impact else None,
            "recent_surprises": [
                {
                    "event": self._simplify_event_name(e["event_name"]),
                    "date": str(e["event_date"]),
                    "surprise": self._calculate_surprise(e),
                }
                for e in past[:3]
                if self._calculate_surprise(e) != "as expected"
            ],
            "educational_tip": "Economic data releases can cause big market moves. Fed meetings and jobs reports are especially important. Avoid trading right before major announcements.",
            "beginner_advice": self._get_beginner_advice(high_impact),
        }

    def _format_intermediate(
        self,
        upcoming: list[dict],
        past: list[dict],
        high_impact: list[dict],
        medium_impact: list[dict],
    ) -> dict[str, Any]:
        """Format for intermediate mode - detailed economic calendar."""
        # Group by category
        by_category = {}
        for event in upcoming:
            category = event.get("event_category", "other")
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(event)

        return {
            "summary": {
                "total_events": len(upcoming),
                "high_impact": len(high_impact),
                "medium_impact": len(medium_impact),
                "next_high_impact": str(high_impact[0]["event_date"]) if high_impact else None,
            },
            "high_impact_events": [
                {
                    "event_name": e["event_name"],
                    "event_date": str(e["event_date"]),
                    "event_time": e.get("event_time"),
                    "category": e.get("event_category"),
                    "country": e.get("country", "US"),
                    "previous": e.get("previous_value"),
                    "estimate": e.get("consensus_estimate"),
                    "days_until": (e["event_date"] - date.today()).days,
                }
                for e in high_impact
            ],
            "medium_impact_events": [
                {
                    "event_name": e["event_name"],
                    "event_date": str(e["event_date"]),
                    "category": e.get("event_category"),
                    "country": e.get("country", "US"),
                }
                for e in medium_impact[:10]
            ],
            "by_category": {
                category: {
                    "count": len(events),
                    "next_event": str(events[0]["event_date"]) if events else None,
                }
                for category, events in by_category.items()
            },
            "recent_releases": [
                {
                    "event_name": e["event_name"],
                    "date": str(e["event_date"]),
                    "category": e.get("event_category"),
                    "previous": e.get("previous_value"),
                    "estimate": e.get("consensus_estimate"),
                    "actual": e.get("actual_value"),
                    "beat_miss": self._calculate_beat_miss(e),
                }
                for e in past[:5]
            ],
            "trading_implications": self._get_trading_implications(high_impact),
        }

    def _format_advanced(
        self,
        upcoming: list[dict],
        past: list[dict],
    ) -> dict[str, Any]:
        """Format for advanced mode - comprehensive economic analysis."""
        # Group by date and impact
        by_date = {}
        for event in upcoming:
            event_date = str(event["event_date"])
            if event_date not in by_date:
                by_date[event_date] = {"high": [], "medium": [], "low": []}

            impact = event.get("impact_level", "low")
            by_date[event_date][impact].append(event)

        # Analyze recent surprise patterns
        surprise_analysis = self._analyze_surprises(past)

        return {
            "upcoming_events": [
                {
                    "event_date": str(e["event_date"]),
                    "event_time": e.get("event_time"),
                    "event_name": e["event_name"],
                    "category": e.get("event_category"),
                    "impact_level": e.get("impact_level"),
                    "country": e.get("country", "US"),
                    "previous_value": e.get("previous_value"),
                    "consensus_estimate": e.get("consensus_estimate"),
                    "actual_value": e.get("actual_value"),
                    "days_until": (e["event_date"] - date.today()).days,
                }
                for e in upcoming
            ],
            "by_date": {
                event_date: {
                    "high_impact_count": len(events["high"]),
                    "high_impact_events": [
                        {
                            "name": ev["event_name"],
                            "time": ev.get("event_time"),
                            "category": ev.get("event_category"),
                            "estimate": ev.get("consensus_estimate"),
                        }
                        for ev in events["high"]
                    ],
                    "medium_impact_count": len(events["medium"]),
                    "total_events": sum(len(events[level]) for level in ["high", "medium", "low"]),
                }
                for event_date, events in by_date.items()
            },
            "recent_releases": [
                {
                    "event_date": str(e["event_date"]),
                    "event_name": e["event_name"],
                    "category": e.get("event_category"),
                    "impact_level": e.get("impact_level"),
                    "previous_value": e.get("previous_value"),
                    "consensus_estimate": e.get("consensus_estimate"),
                    "actual_value": e.get("actual_value"),
                    "surprise_direction": self._calculate_beat_miss(e),
                    "surprise_magnitude": self._calculate_surprise_magnitude(e),
                }
                for e in past
            ],
            "surprise_analysis": surprise_analysis,
            "risk_calendar": self._assess_calendar_risk(by_date),
            "key_dates": self._identify_key_dates(by_date),
        }

    @staticmethod
    def _simplify_event_name(event_name: str) -> str:
        """Simplify event name for beginners."""
        simplifications = {
            "Non-Farm Payrolls": "Jobs Report",
            "Federal Funds Rate Decision": "Fed Interest Rate Decision",
            "Consumer Price Index": "Inflation Report (CPI)",
            "Producer Price Index": "Wholesale Inflation (PPI)",
            "Gross Domestic Product": "GDP Growth",
            "FOMC Meeting": "Fed Meeting",
            "Initial Jobless Claims": "Unemployment Claims",
            "Retail Sales": "Consumer Spending",
        }

        for full_name, simple_name in simplifications.items():
            if full_name.lower() in event_name.lower():
                return simple_name

        return event_name

    @staticmethod
    def _explain_event(category: Optional[str]) -> str:
        """Explain what an event category means."""
        explanations = {
            "employment": "Jobs data shows economic health. Strong jobs = strong economy = bullish.",
            "inflation": "Inflation data affects Fed policy. High inflation = Fed may raise rates = bearish for stocks.",
            "monetary_policy": "Fed decisions on interest rates. Rate hikes = borrowing costs up = bearish.",
            "gdp": "Economic growth rate. Higher GDP = stronger economy = bullish.",
            "consumer_confidence": "Consumer spending drives economy. High confidence = bullish.",
            "manufacturing": "Factory activity indicates economic strength.",
        }
        return explanations.get(category, "Economic indicator that can move markets.")

    @staticmethod
    def _get_what_to_watch(category: Optional[str]) -> str:
        """Get what to watch for in an event."""
        watch_items = {
            "employment": "Watch if jobs beat/miss expectations. Big surprise = big market move.",
            "inflation": "Higher than expected = Fed may hike rates faster. Lower = relief rally.",
            "monetary_policy": "Watch Fed's tone. 'Hawkish' = bearish. 'Dovish' = bullish.",
            "gdp": "Above estimate = bullish. Below = concerns about slowdown.",
        }
        return watch_items.get(category, "Watch if actual beats or misses estimates significantly.")

    @staticmethod
    def _calculate_surprise(event: dict) -> str:
        """Calculate if event surprised markets."""
        actual = event.get("actual_value")
        estimate = event.get("consensus_estimate")

        if actual is None or estimate is None:
            return "no data"

        try:
            actual_val = float(actual)
            estimate_val = float(estimate)

            diff_pct = ((actual_val - estimate_val) / abs(estimate_val)) * 100 if estimate_val != 0 else 0

            if abs(diff_pct) < 2:
                return "as expected"
            elif diff_pct > 5:
                return f"beat by {abs(diff_pct):.1f}%"
            elif diff_pct < -5:
                return f"missed by {abs(diff_pct):.1f}%"
            elif diff_pct > 0:
                return "slightly beat"
            else:
                return "slightly missed"
        except (ValueError, TypeError):
            return "no data"

    @staticmethod
    def _calculate_beat_miss(event: dict) -> Optional[str]:
        """Calculate beat/miss direction."""
        actual = event.get("actual_value")
        estimate = event.get("consensus_estimate")

        if actual is None or estimate is None:
            return None

        try:
            actual_val = float(actual)
            estimate_val = float(estimate)

            if actual_val > estimate_val:
                return "beat"
            elif actual_val < estimate_val:
                return "miss"
            else:
                return "inline"
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _calculate_surprise_magnitude(event: dict) -> Optional[float]:
        """Calculate surprise magnitude as percentage."""
        actual = event.get("actual_value")
        estimate = event.get("consensus_estimate")

        if actual is None or estimate is None:
            return None

        try:
            actual_val = float(actual)
            estimate_val = float(estimate)

            if estimate_val != 0:
                return round(((actual_val - estimate_val) / abs(estimate_val)) * 100, 2)
            return None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _get_beginner_advice(high_impact: list[dict]) -> str:
        """Get beginner advice based on upcoming events."""
        if not high_impact:
            return "No major economic events coming up. Normal trading conditions."

        days_until = (high_impact[0]["event_date"] - date.today()).days

        if days_until == 0:
            return "Major economic data today! Avoid trading around release time. Wait for dust to settle."
        elif days_until == 1:
            return "Major economic data tomorrow. Consider reducing positions or waiting until after the release."
        elif days_until <= 3:
            return "Major economic data in a few days. Volatility may increase. Use smaller position sizes."
        else:
            return "Keep an eye on upcoming economic events. Plan your trades around major releases."

    @staticmethod
    def _get_trading_implications(high_impact: list[dict]) -> str:
        """Get trading implications of upcoming events."""
        if not high_impact:
            return "Light economic calendar. Focus on company-specific catalysts."

        # Count by category
        categories = {}
        for event in high_impact:
            cat = event.get("event_category", "other")
            categories[cat] = categories.get(cat, 0) + 1

        # Assess risk
        if len(high_impact) > 5:
            return "Heavy economic calendar ahead. Expect increased volatility. Reduce position sizes and widen stops."
        elif "monetary_policy" in categories:
            return "Fed meeting coming. Market-moving event. Expect volatility in rates, financials, and growth stocks."
        elif "employment" in categories:
            return "Jobs data coming. Watch for surprises. Strong jobs = bullish economy, but may push Fed hawkish."
        elif "inflation" in categories:
            return "Inflation data coming. Higher than expected = Fed pressure. Lower = relief rally potential."
        else:
            return "Standard economic releases. Moderate volatility expected."

    @staticmethod
    def _analyze_surprises(past: list[dict]) -> dict:
        """Analyze recent surprise patterns."""
        if not past:
            return {"pattern": "insufficient_data"}

        surprises = []
        for event in past:
            beat_miss = EconomicCalendarHandler._calculate_beat_miss(event)
            if beat_miss:
                surprises.append(beat_miss)

        if not surprises:
            return {"pattern": "no_surprises"}

        beat_count = surprises.count("beat")
        miss_count = surprises.count("miss")
        inline_count = surprises.count("inline")

        total = len(surprises)

        return {
            "pattern": "mostly_beats" if beat_count > total * 0.6 else "mostly_misses" if miss_count > total * 0.6 else "mixed",
            "beat_count": beat_count,
            "miss_count": miss_count,
            "inline_count": inline_count,
            "beat_rate": round(beat_count / total * 100, 1) if total > 0 else 0,
        }

    @staticmethod
    def _assess_calendar_risk(by_date: dict) -> str:
        """Assess overall calendar risk level."""
        high_impact_days = sum(1 for events in by_date.values() if events["high_impact_count"] > 0)
        total_high_impact = sum(events["high_impact_count"] for events in by_date.values())

        if total_high_impact > 8:
            return "very_high"
        elif total_high_impact > 5:
            return "high"
        elif total_high_impact > 2:
            return "moderate"
        else:
            return "low"

    @staticmethod
    def _identify_key_dates(by_date: dict) -> list[str]:
        """Identify key dates with multiple high-impact events."""
        key_dates = []

        for event_date, events in by_date.items():
            if events["high_impact_count"] >= 2:
                key_dates.append(event_date)

        return sorted(key_dates)[:5]  # Return top 5 dates
