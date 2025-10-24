"""
Dividends Calendar Handler - Dividend payments and history.

Shows dividend information:
- Next dividend date
- Dividend yield
- Dividend growth history
- Payment consistency

Data source: sb.dividends_calendar (expected table)
"""

from datetime import date, timedelta
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class DividendsCalendarHandler(BaseCardHandler):
    """Handler for ticker_dividends card - dividend calendar and history."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Fetch dividend calendar data for the given symbol.

        Args:
            mode: Response complexity level
            symbol: Stock symbol (required)
            trading_date: Current trading date (for context)

        Returns:
            Formatted card data based on mode

        Raises:
            HTTPException: If symbol not provided or data not found
        """
        if not symbol:
            raise HTTPException(
                status_code=400,
                detail="Symbol is required for ticker_dividends card",
            )

        # Fetch upcoming dividend
        upcoming_query = """
            SELECT
                symbol,
                ex_dividend_date,
                payment_date,
                dividend_amount,
                dividend_type,  -- 'regular', 'special', 'qualified'
                frequency  -- 'quarterly', 'monthly', 'annual'
            FROM sb.dividends_calendar
            WHERE symbol = $1
              AND ex_dividend_date >= $2
            ORDER BY ex_dividend_date ASC
            LIMIT 1
        """

        # Fetch dividend history
        history_query = """
            SELECT
                ex_dividend_date,
                payment_date,
                dividend_amount,
                dividend_type,
                annualized_dividend
            FROM sb.dividends_calendar
            WHERE symbol = $1
              AND ex_dividend_date < $2
            ORDER BY ex_dividend_date DESC
            LIMIT 8
        """

        # Get current price for yield calculation
        price_query = """
            SELECT close
            FROM sb.equity_bars_daily
            WHERE symbol = $1
              AND trading_date = $2
            LIMIT 1
        """

        upcoming = await self._fetch_one(upcoming_query, {"symbol": symbol, "ex_dividend_date": trading_date})
        history = await self._fetch_all(history_query, {"symbol": symbol, "ex_dividend_date": trading_date})
        price_row = await self._fetch_one(price_query, {"symbol": symbol, "trading_date": trading_date})

        if not upcoming and not history:
            raise HTTPException(
                status_code=404,
                detail=f"No dividend data for {symbol} (may not pay dividends)",
            )

        current_price = float(price_row["close"]) if price_row and price_row["close"] else None

        # Calculate metrics
        dividend_yield = None
        annual_dividend = None
        if history and current_price:
            # Calculate annual dividend from recent history
            recent_dividends = [float(h["dividend_amount"]) for h in history[:4] if h.get("dividend_amount")]
            if recent_dividends:
                annual_dividend = sum(recent_dividends)
                dividend_yield = (annual_dividend / current_price) * 100

        # Format based on mode
        if mode == CardMode.beginner:
            return self._format_beginner(symbol, upcoming, history, dividend_yield, annual_dividend)
        elif mode == CardMode.intermediate:
            return self._format_intermediate(symbol, upcoming, history, dividend_yield, annual_dividend, current_price)
        else:
            return self._format_advanced(symbol, upcoming, history, dividend_yield, annual_dividend, current_price)

    def _format_beginner(
        self,
        symbol: str,
        upcoming: Optional[dict],
        history: list[dict],
        yield_pct: Optional[float],
        annual_dividend: Optional[float],
    ) -> dict[str, Any]:
        """Format for beginner mode - simple dividend overview."""
        result = {
            "symbol": symbol,
            "pays_dividends": bool(upcoming or history),
            "educational_tip": "Dividends are cash payments companies make to shareholders. You must own the stock before the ex-dividend date to receive payment.",
        }

        if yield_pct:
            result.update({
                "dividend_yield": f"{yield_pct:.2f}%",
                "annual_dividend": f"${annual_dividend:.2f}" if annual_dividend else None,
                "yield_rating": self._rate_yield(yield_pct),
                "simple_explanation": self._get_yield_explanation(yield_pct),
            })

        if upcoming:
            ex_date = upcoming["ex_dividend_date"]
            payment_date = upcoming["payment_date"]
            days_until_ex = (ex_date - date.today()).days
            days_until_payment = (payment_date - date.today()).days if payment_date else None

            result.update({
                "next_dividend": {
                    "amount": f"${upcoming['dividend_amount']:.2f}" if upcoming.get("dividend_amount") else None,
                    "ex_date": str(ex_date),
                    "days_until_ex_date": days_until_ex,
                    "payment_date": str(payment_date) if payment_date else None,
                    "days_until_payment": days_until_payment,
                    "frequency": upcoming.get("frequency", "quarterly"),
                },
                "advice": self._get_beginner_advice(days_until_ex),
            })
        else:
            result["next_dividend"] = None
            result["advice"] = "Check historical dividends to see if company still pays regularly"

        if history:
            result["consistency"] = self._assess_consistency(history)
            result["recent_payments"] = [
                {
                    "date": str(h["ex_dividend_date"]),
                    "amount": f"${h['dividend_amount']:.2f}" if h.get("dividend_amount") else None,
                }
                for h in history[:4]
            ]

        return result

    def _format_intermediate(
        self,
        symbol: str,
        upcoming: Optional[dict],
        history: list[dict],
        yield_pct: Optional[float],
        annual_dividend: Optional[float],
        current_price: Optional[float],
    ) -> dict[str, Any]:
        """Format for intermediate mode - dividend metrics and analysis."""
        result = {"symbol": symbol}

        if yield_pct:
            result["dividend_metrics"] = {
                "current_yield_pct": round(yield_pct, 2),
                "annual_dividend": round(annual_dividend, 2) if annual_dividend else None,
                "current_price": round(current_price, 2) if current_price else None,
                "yield_classification": self._classify_yield(yield_pct),
            }

        if upcoming:
            result["upcoming_dividend"] = {
                "ex_dividend_date": str(upcoming["ex_dividend_date"]),
                "payment_date": str(upcoming["payment_date"]) if upcoming.get("payment_date") else None,
                "dividend_amount": round(upcoming["dividend_amount"], 2) if upcoming.get("dividend_amount") else None,
                "dividend_type": upcoming.get("dividend_type", "regular"),
                "frequency": upcoming.get("frequency", "quarterly"),
                "days_until_ex_date": (upcoming["ex_dividend_date"] - date.today()).days,
            }

        if history:
            result["dividend_history"] = [
                {
                    "ex_date": str(h["ex_dividend_date"]),
                    "payment_date": str(h["payment_date"]) if h.get("payment_date") else None,
                    "amount": round(h["dividend_amount"], 2) if h.get("dividend_amount") else None,
                    "type": h.get("dividend_type", "regular"),
                }
                for h in history
            ]

            # Calculate dividend growth
            growth_rate = self._calculate_growth_rate(history)
            result["growth_analysis"] = {
                "growth_rate_yoy": round(growth_rate, 1) if growth_rate is not None else None,
                "consistency_rating": self._assess_consistency(history),
                "payment_reliability": self._assess_reliability(history),
            }

        return result

    def _format_advanced(
        self,
        symbol: str,
        upcoming: Optional[dict],
        history: list[dict],
        yield_pct: Optional[float],
        annual_dividend: Optional[float],
        current_price: Optional[float],
    ) -> dict[str, Any]:
        """Format for advanced mode - comprehensive dividend analysis."""
        result = {"symbol": symbol}

        if yield_pct:
            result["yield_analysis"] = {
                "current_yield_pct": round(yield_pct, 4),
                "annual_dividend": round(annual_dividend, 4) if annual_dividend else None,
                "current_price": round(current_price, 4) if current_price else None,
                "yield_classification": self._classify_yield(yield_pct),
                "yield_percentile": self._estimate_yield_percentile(yield_pct),
            }

        if upcoming:
            result["upcoming_dividend"] = {
                "ex_dividend_date": str(upcoming["ex_dividend_date"]),
                "payment_date": str(upcoming["payment_date"]) if upcoming.get("payment_date") else None,
                "dividend_amount": round(upcoming["dividend_amount"], 4) if upcoming.get("dividend_amount") else None,
                "dividend_type": upcoming.get("dividend_type"),
                "frequency": upcoming.get("frequency"),
                "days_until_ex_date": (upcoming["ex_dividend_date"] - date.today()).days,
                "annualized": round(upcoming.get("annualized_dividend"), 4) if upcoming.get("annualized_dividend") else None,
            }

        if history:
            result["dividend_history"] = [
                {
                    "ex_date": str(h["ex_dividend_date"]),
                    "payment_date": str(h["payment_date"]) if h.get("payment_date") else None,
                    "amount": round(h["dividend_amount"], 4) if h.get("dividend_amount") else None,
                    "type": h.get("dividend_type"),
                    "annualized": round(h.get("annualized_dividend"), 4) if h.get("annualized_dividend") else None,
                }
                for h in history
            ]

            # Advanced metrics
            growth_rate = self._calculate_growth_rate(history)
            cagr = self._calculate_cagr(history)

            result["advanced_metrics"] = {
                "growth_rate_yoy_pct": round(growth_rate, 4) if growth_rate is not None else None,
                "cagr_5y_pct": round(cagr, 4) if cagr is not None else None,
                "consistency_score": self._calculate_consistency_score(history),
                "payment_reliability": self._assess_reliability(history),
                "dividend_aristocrat": len(history) >= 8 and all(h.get("dividend_amount", 0) > 0 for h in history),
            }

            result["investment_profile"] = {
                "income_quality": self._assess_income_quality(yield_pct, growth_rate),
                "sustainability": self._assess_sustainability(history),
                "recommendation": self._get_investment_recommendation(yield_pct, growth_rate, history),
            }

        return result

    @staticmethod
    def _rate_yield(yield_pct: float) -> str:
        """Rate the dividend yield."""
        if yield_pct > 6:
            return "Very High (⚠️ verify sustainability)"
        elif yield_pct > 4:
            return "High"
        elif yield_pct > 2:
            return "Moderate"
        elif yield_pct > 0:
            return "Low"
        else:
            return "No Yield"

    @staticmethod
    def _classify_yield(yield_pct: float) -> str:
        """Classify the dividend yield."""
        if yield_pct > 7:
            return "very_high"
        elif yield_pct > 4:
            return "high"
        elif yield_pct > 2:
            return "moderate"
        elif yield_pct > 1:
            return "low"
        else:
            return "minimal"

    @staticmethod
    def _get_yield_explanation(yield_pct: float) -> str:
        """Get explanation of dividend yield."""
        if yield_pct > 6:
            return f"Very high {yield_pct:.1f}% yield. Verify company is healthy - high yields can signal problems."
        elif yield_pct > 4:
            return f"Attractive {yield_pct:.1f}% dividend yield for income investors."
        elif yield_pct > 2:
            return f"Moderate {yield_pct:.1f}% yield. Decent income plus growth potential."
        else:
            return f"Low {yield_pct:.1f}% yield. Stock focused more on growth than income."

    @staticmethod
    def _get_beginner_advice(days_until_ex: int) -> str:
        """Get beginner advice based on ex-dividend date."""
        if days_until_ex < 0:
            return "Ex-dividend date has passed. You won't get the next dividend if you buy now."
        elif days_until_ex == 0:
            return "Today is ex-dividend date. Buy today or later and you'll miss this dividend."
        elif days_until_ex == 1:
            return "Tomorrow is ex-dividend date. Must buy TODAY to receive next dividend."
        elif days_until_ex <= 5:
            return f"Must own stock before {days_until_ex} days from now to receive dividend."
        else:
            return "Plenty of time before next dividend. No need to rush."

    @staticmethod
    def _assess_consistency(history: list[dict]) -> str:
        """Assess dividend payment consistency."""
        if not history or len(history) < 4:
            return "insufficient_history"

        # Check if dividends are paid regularly
        amounts = [h.get("dividend_amount", 0) for h in history[:4]]
        if all(a > 0 for a in amounts):
            # Check if amounts are stable or growing
            if all(amounts[i] <= amounts[i-1] * 1.1 for i in range(1, len(amounts))):
                return "highly_consistent"
            else:
                return "growing"
        else:
            return "irregular"

    @staticmethod
    def _assess_reliability(history: list[dict]) -> str:
        """Assess dividend payment reliability."""
        if not history:
            return "unknown"

        # Check for missed payments or cuts
        amounts = [h.get("dividend_amount", 0) for h in history]
        if any(a <= 0 for a in amounts):
            return "unreliable"

        # Check for cuts (significant decreases)
        for i in range(1, min(len(amounts), 4)):
            if amounts[i] < amounts[i-1] * 0.9:  # More than 10% cut
                return "recently_cut"

        return "reliable"

    @staticmethod
    def _calculate_growth_rate(history: list[dict]) -> Optional[float]:
        """Calculate year-over-year dividend growth rate."""
        if len(history) < 8:  # Need 2 years of quarterly data
            return None

        # Compare recent 4 dividends to previous 4
        recent_total = sum(h.get("dividend_amount", 0) for h in history[:4])
        previous_total = sum(h.get("dividend_amount", 0) for h in history[4:8])

        if previous_total > 0:
            return ((recent_total - previous_total) / previous_total) * 100
        return None

    @staticmethod
    def _calculate_cagr(history: list[dict]) -> Optional[float]:
        """Calculate compound annual growth rate (5-year if available)."""
        if len(history) < 8:
            return None

        recent = history[0].get("dividend_amount", 0)
        oldest = history[-1].get("dividend_amount", 0)

        if oldest > 0:
            years = len(history) / 4  # Assuming quarterly
            cagr = (pow(recent / oldest, 1 / years) - 1) * 100
            return cagr
        return None

    @staticmethod
    def _calculate_consistency_score(history: list[dict]) -> float:
        """Calculate consistency score (0-100)."""
        if not history or len(history) < 2:
            return 0.0

        amounts = [h.get("dividend_amount", 0) for h in history]

        # Score based on: no cuts, regular payments, stable growth
        score = 100.0

        # Penalty for missed payments
        if any(a <= 0 for a in amounts):
            score -= 30

        # Penalty for cuts
        for i in range(1, len(amounts)):
            if amounts[i] < amounts[i-1]:
                score -= 15

        # Bonus for consistent growth
        growth_count = sum(1 for i in range(1, len(amounts)) if amounts[i] >= amounts[i-1])
        consistency = growth_count / (len(amounts) - 1)
        score += consistency * 30

        return max(0.0, min(100.0, score))

    @staticmethod
    def _estimate_yield_percentile(yield_pct: float) -> str:
        """Estimate yield percentile vs market."""
        if yield_pct > 6:
            return "top_5%"
        elif yield_pct > 4:
            return "top_15%"
        elif yield_pct > 3:
            return "top_25%"
        elif yield_pct > 2:
            return "top_50%"
        else:
            return "bottom_50%"

    @staticmethod
    def _assess_income_quality(yield_pct: Optional[float], growth_rate: Optional[float]) -> str:
        """Assess income quality."""
        if yield_pct is None:
            return "unknown"

        if yield_pct > 7:
            return "high_risk"  # Yield may be unsustainable
        elif yield_pct > 4 and growth_rate and growth_rate > 5:
            return "excellent"  # High yield with growth
        elif yield_pct > 3 and growth_rate and growth_rate > 0:
            return "good"  # Decent yield with growth
        elif yield_pct > 2:
            return "moderate"
        else:
            return "low"

    @staticmethod
    def _assess_sustainability(history: list[dict]) -> str:
        """Assess dividend sustainability."""
        if not history or len(history) < 4:
            return "unknown"

        # Check for cuts or irregular payments
        amounts = [h.get("dividend_amount", 0) for h in history[:4]]

        if any(a <= 0 for a in amounts):
            return "at_risk"

        # Check for declining trend
        if all(amounts[i] >= amounts[i+1] for i in range(len(amounts)-1)):
            return "declining"

        # Check for stable or growing
        if all(amounts[i] <= amounts[i+1] * 1.2 for i in range(len(amounts)-1)):
            return "sustainable"

        return "uncertain"

    @staticmethod
    def _get_investment_recommendation(
        yield_pct: Optional[float],
        growth_rate: Optional[float],
        history: list[dict],
    ) -> str:
        """Get investment recommendation."""
        if yield_pct is None:
            return "insufficient_data"

        if yield_pct > 7:
            return "High yield - verify financial health before investing. May be a value trap."

        if yield_pct > 4 and growth_rate and growth_rate > 5:
            return "Attractive for income investors - high yield with growth. Verify payout ratio."

        if yield_pct > 3 and growth_rate and growth_rate > 0:
            return "Good income stock - reasonable yield with growth potential."

        if yield_pct > 2:
            return "Moderate income play - suitable for balanced portfolios."

        return "Low yield - better for growth-focused investors than income."
