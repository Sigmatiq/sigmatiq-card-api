"""
Analyst Ratings Handler - Wall Street analyst recommendations and price targets.

Shows analyst consensus:
- Buy/Hold/Sell ratings distribution
- Average price target
- Recent rating changes
- Analyst sentiment trend

Data source: sb.analyst_ratings (expected table)
"""

from datetime import date, timedelta
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class AnalystRatingsHandler(BaseCardHandler):
    """Handler for ticker_analyst card - analyst ratings and price targets."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        if not symbol:
            raise HTTPException(400, "Symbol required for ticker_analyst")

        # Get consensus ratings
        consensus_query = """
            SELECT
                as_of_date,
                strong_buy_count,
                buy_count,
                hold_count,
                sell_count,
                strong_sell_count,
                avg_price_target,
                high_price_target,
                low_price_target,
                analyst_count
            FROM sb.analyst_consensus
            WHERE symbol = $1 AND as_of_date <= $2
            ORDER BY as_of_date DESC
            LIMIT 1
        """

        # Get recent rating changes
        changes_query = """
            SELECT
                rating_date,
                analyst_firm,
                rating_action,
                new_rating,
                old_rating,
                price_target
            FROM sb.analyst_ratings
            WHERE symbol = $1
              AND rating_date >= $2
              AND rating_date <= $3
            ORDER BY rating_date DESC
            LIMIT 10
        """

        # Get current price for target comparison
        price_query = """
            SELECT close
            FROM sb.equity_bars_daily
            WHERE symbol = $1 AND trading_date = $2
            LIMIT 1
        """

        consensus = await self._fetch_one(consensus_query, {"symbol": symbol, "as_of_date": trading_date})
        changes = await self._fetch_all(changes_query, {
            "symbol": symbol,
            "start_date": trading_date - timedelta(days=90),
            "end_date": trading_date
        })
        price_row = await self._fetch_one(price_query, {"symbol": symbol, "trading_date": trading_date})

        if not consensus:
            raise HTTPException(404, f"No analyst data for {symbol}")

        current_price = float(price_row["close"]) if price_row and price_row.get("close") else None
        avg_target = float(consensus["avg_price_target"]) if consensus.get("avg_price_target") else None

        upside = None
        if current_price and avg_target and current_price > 0:
            upside = ((avg_target - current_price) / current_price) * 100

        # Calculate consensus rating
        total_analysts = (
            (consensus.get("strong_buy_count") or 0) +
            (consensus.get("buy_count") or 0) +
            (consensus.get("hold_count") or 0) +
            (consensus.get("sell_count") or 0) +
            (consensus.get("strong_sell_count") or 0)
        )

        if mode == CardMode.beginner:
            consensus_rating = self._get_consensus_rating(consensus)
            return {
                "symbol": symbol,
                "analyst_consensus": consensus_rating,
                "consensus_emoji": {"Strong Buy": "🚀", "Buy": "📈", "Hold": "➡️", "Sell": "📉", "Strong Sell": "⚠️"}.get(consensus_rating, "❓"),
                "price_target": f"${avg_target:.2f}" if avg_target else None,
                "current_price": f"${current_price:.2f}" if current_price else None,
                "upside_potential": f"{upside:+.1f}%" if upside else None,
                "analyst_count": total_analysts,
                "what_it_means": f"Analysts recommend: {consensus_rating}. Target: ${avg_target:.0f}. {upside:+.0f}% from current price." if avg_target and upside else f"Analysts recommend: {consensus_rating}.",
                "educational_tip": "Analyst ratings show Wall Street's view. 'Buy' = analysts think it will go up. Price target = where analysts think it should trade.",
                "beginner_advice": self._get_beginner_advice(consensus_rating, upside),
                "as_of_date": str(consensus["as_of_date"]),
            }
        elif mode == CardMode.intermediate:
            return {
                "symbol": symbol,
                "consensus": {
                    "rating": self._get_consensus_rating(consensus),
                    "score": self._calculate_consensus_score(consensus),
                    "analyst_count": total_analysts,
                },
                "rating_distribution": {
                    "strong_buy": consensus.get("strong_buy_count") or 0,
                    "buy": consensus.get("buy_count") or 0,
                    "hold": consensus.get("hold_count") or 0,
                    "sell": consensus.get("sell_count") or 0,
                    "strong_sell": consensus.get("strong_sell_count") or 0,
                },
                "price_targets": {
                    "average": round(avg_target, 2) if avg_target else None,
                    "high": round(float(consensus["high_price_target"]), 2) if consensus.get("high_price_target") else None,
                    "low": round(float(consensus["low_price_target"]), 2) if consensus.get("low_price_target") else None,
                    "current_price": round(current_price, 2) if current_price else None,
                    "upside_pct": round(upside, 2) if upside else None,
                },
                "recent_changes": [
                    {
                        "date": str(c["rating_date"]),
                        "firm": c.get("analyst_firm"),
                        "action": c.get("rating_action"),
                        "new_rating": c.get("new_rating"),
                        "price_target": round(float(c["price_target"]), 2) if c.get("price_target") else None,
                    }
                    for c in changes
                ],
                "as_of_date": str(consensus["as_of_date"]),
                "interpretation": self._get_interpretation(consensus, upside),
            }
        else:
            return {
                "symbol": symbol,
                "consensus_metrics": {
                    "consensus_rating": self._get_consensus_rating(consensus),
                    "consensus_score": self._calculate_consensus_score(consensus),
                    "total_analysts": total_analysts,
                    "rating_scale": "1 (Strong Sell) to 5 (Strong Buy)",
                },
                "rating_distribution": {
                    "strong_buy": consensus.get("strong_buy_count") or 0,
                    "buy": consensus.get("buy_count") or 0,
                    "hold": consensus.get("hold_count") or 0,
                    "sell": consensus.get("sell_count") or 0,
                    "strong_sell": consensus.get("strong_sell_count") or 0,
                    "strong_buy_pct": round((consensus.get("strong_buy_count") or 0) / total_analysts * 100, 2) if total_analysts > 0 else 0,
                    "buy_pct": round((consensus.get("buy_count") or 0) / total_analysts * 100, 2) if total_analysts > 0 else 0,
                    "hold_pct": round((consensus.get("hold_count") or 0) / total_analysts * 100, 2) if total_analysts > 0 else 0,
                    "sell_pct": round((consensus.get("sell_count") or 0) / total_analysts * 100, 2) if total_analysts > 0 else 0,
                    "strong_sell_pct": round((consensus.get("strong_sell_count") or 0) / total_analysts * 100, 2) if total_analysts > 0 else 0,
                },
                "price_target_analysis": {
                    "average_target": round(avg_target, 4) if avg_target else None,
                    "high_target": round(float(consensus["high_price_target"]), 4) if consensus.get("high_price_target") else None,
                    "low_target": round(float(consensus["low_price_target"]), 4) if consensus.get("low_price_target") else None,
                    "current_price": round(current_price, 4) if current_price else None,
                    "upside_to_avg_pct": round(upside, 4) if upside else None,
                    "upside_to_high_pct": round(((float(consensus["high_price_target"]) - current_price) / current_price * 100), 4) if consensus.get("high_price_target") and current_price else None,
                    "downside_to_low_pct": round(((float(consensus["low_price_target"]) - current_price) / current_price * 100), 4) if consensus.get("low_price_target") and current_price else None,
                },
                "recent_rating_changes": [
                    {
                        "rating_date": str(c["rating_date"]),
                        "analyst_firm": c.get("analyst_firm"),
                        "rating_action": c.get("rating_action"),
                        "new_rating": c.get("new_rating"),
                        "old_rating": c.get("old_rating"),
                        "price_target": round(float(c["price_target"]), 4) if c.get("price_target") else None,
                    }
                    for c in changes
                ],
                "data_quality": {
                    "as_of_date": str(consensus["as_of_date"]),
                    "data_age_days": (date.today() - consensus["as_of_date"]).days,
                },
            }

    @staticmethod
    def _get_consensus_rating(consensus: dict) -> str:
        """Calculate consensus rating from distribution."""
        strong_buy = consensus.get("strong_buy_count") or 0
        buy = consensus.get("buy_count") or 0
        hold = consensus.get("hold_count") or 0
        sell = consensus.get("sell_count") or 0
        strong_sell = consensus.get("strong_sell_count") or 0

        total = strong_buy + buy + hold + sell + strong_sell
        if total == 0:
            return "No Consensus"

        # Weighted score (5=Strong Buy, 1=Strong Sell)
        score = (strong_buy * 5 + buy * 4 + hold * 3 + sell * 2 + strong_sell * 1) / total

        if score >= 4.5:
            return "Strong Buy"
        elif score >= 3.5:
            return "Buy"
        elif score >= 2.5:
            return "Hold"
        elif score >= 1.5:
            return "Sell"
        else:
            return "Strong Sell"

    @staticmethod
    def _calculate_consensus_score(consensus: dict) -> float:
        """Calculate numeric consensus score (1-5)."""
        strong_buy = consensus.get("strong_buy_count") or 0
        buy = consensus.get("buy_count") or 0
        hold = consensus.get("hold_count") or 0
        sell = consensus.get("sell_count") or 0
        strong_sell = consensus.get("strong_sell_count") or 0

        total = strong_buy + buy + hold + sell + strong_sell
        if total == 0:
            return 3.0

        return (strong_buy * 5 + buy * 4 + hold * 3 + sell * 2 + strong_sell * 1) / total

    @staticmethod
    def _get_beginner_advice(rating: str, upside: Optional[float]) -> str:
        """Get beginner advice based on rating and upside."""
        if rating == "Strong Buy" and upside and upside > 20:
            return "Strong analyst support + high upside. Consider buying. Verify fundamentals first."
        elif rating in ["Strong Buy", "Buy"]:
            return "Analysts are bullish. Good signal for potential purchase."
        elif rating == "Hold":
            return "Analysts neutral. OK to hold if you own, but no urgency to buy."
        elif rating in ["Sell", "Strong Sell"]:
            return "Analysts bearish. Avoid or consider selling if you own."
        else:
            return "Analyst opinion mixed. Use other factors to decide."

    @staticmethod
    def _get_interpretation(consensus: dict, upside: Optional[float]) -> str:
        """Get intermediate interpretation."""
        rating = AnalystRatingsHandler._get_consensus_rating(consensus)
        total = (
            (consensus.get("strong_buy_count") or 0) +
            (consensus.get("buy_count") or 0) +
            (consensus.get("hold_count") or 0) +
            (consensus.get("sell_count") or 0) +
            (consensus.get("strong_sell_count") or 0)
        )

        base = f"Consensus: {rating} ({total} analysts). "

        if upside:
            if upside > 30:
                base += f"High upside potential: {upside:.1f}%."
            elif upside > 10:
                base += f"Moderate upside: {upside:.1f}%."
            elif upside > 0:
                base += f"Limited upside: {upside:.1f}%."
            else:
                base += f"Trading above price target ({upside:.1f}%)."

        return base
