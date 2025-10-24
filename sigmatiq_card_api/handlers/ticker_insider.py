"""
Insider Transactions Handler - Insider buying and selling activity.

Shows insider trading patterns:
- Recent insider transactions
- Net insider buying/selling
- Transaction clusters
- Insider sentiment

Data source: sb.insider_transactions (expected table)
"""

from datetime import date, timedelta
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class InsiderTransactionsHandler(BaseCardHandler):
    """Handler for ticker_insider card - insider trading activity."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Fetch insider transaction data for the given symbol.

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
                detail="Symbol is required for ticker_insider card",
            )

        # Fetch recent insider transactions (last 6 months)
        transactions_query = """
            SELECT
                filing_date,
                transaction_date,
                owner_name,
                owner_title,
                transaction_type,  -- 'P' (purchase), 'S' (sale), 'A' (award), 'M' (option exercise)
                shares,
                price_per_share,
                value,
                shares_owned_after,
                is_direct_ownership
            FROM sb.insider_transactions
            WHERE symbol = $1
              AND transaction_date >= $2
              AND transaction_date <= $3
            ORDER BY transaction_date DESC
            LIMIT 50
        """

        start_date = trading_date - timedelta(days=180)  # Last 6 months

        transactions = await self._fetch_all(
            transactions_query,
            {"symbol": symbol, "start_date": start_date, "end_date": trading_date}
        )

        if not transactions:
            raise HTTPException(
                status_code=404,
                detail=f"No insider transaction data for {symbol} in the past 6 months",
            )

        # Calculate aggregate metrics
        buys = [t for t in transactions if t.get("transaction_type") == "P"]
        sales = [t for t in transactions if t.get("transaction_type") == "S"]

        total_buy_value = sum(float(t["value"]) for t in buys if t.get("value"))
        total_sell_value = sum(float(t["value"]) for t in sales if t.get("value"))

        net_value = total_buy_value - total_sell_value
        sentiment = self._assess_sentiment(total_buy_value, total_sell_value, len(buys), len(sales))

        # Format based on mode
        if mode == CardMode.beginner:
            return self._format_beginner(symbol, transactions, buys, sales, sentiment, net_value)
        elif mode == CardMode.intermediate:
            return self._format_intermediate(symbol, transactions, buys, sales, sentiment, net_value, total_buy_value, total_sell_value)
        else:
            return self._format_advanced(symbol, transactions, buys, sales, sentiment, total_buy_value, total_sell_value)

    def _format_beginner(
        self,
        symbol: str,
        transactions: list[dict],
        buys: list[dict],
        sales: list[dict],
        sentiment: str,
        net_value: float,
    ) -> dict[str, Any]:
        """Format for beginner mode - simplified insider activity."""
        sentiment_emoji = {
            "very_bullish": "🚀",
            "bullish": "📈",
            "neutral": "➡️",
            "bearish": "📉",
            "very_bearish": "⚠️",
        }.get(sentiment, "❓")

        return {
            "symbol": symbol,
            "insider_sentiment": sentiment,
            "sentiment_emoji": sentiment_emoji,
            "simple_summary": self._get_beginner_summary(sentiment, len(buys), len(sales)),
            "buy_transactions": len(buys),
            "sell_transactions": len(sales),
            "net_activity": "Net Buying" if net_value > 0 else "Net Selling" if net_value < 0 else "Balanced",
            "net_value": f"${abs(net_value)/1e6:.1f}M" if abs(net_value) >= 1e6 else f"${abs(net_value)/1e3:.0f}K",
            "recent_activity": [
                {
                    "date": str(t["transaction_date"]) if t.get("transaction_date") else None,
                    "insider": t.get("owner_name"),
                    "title": t.get("owner_title"),
                    "action": "Bought" if t.get("transaction_type") == "P" else "Sold",
                    "shares": f"{int(t['shares']):,}" if t.get("shares") else None,
                    "value": f"${float(t['value'])/1e3:.0f}K" if t.get("value") and float(t["value"]) < 1e6 else f"${float(t['value'])/1e6:.1f}M" if t.get("value") else None,
                }
                for t in transactions[:5] if t.get("transaction_type") in ["P", "S"]
            ],
            "what_it_means": self._explain_sentiment(sentiment),
            "educational_tip": "Insiders are company executives and board members. They have inside information. Consistent insider buying = bullish signal. Heavy selling may be normal (compensation) or bearish.",
            "beginner_advice": self._get_beginner_advice(sentiment),
        }

    def _format_intermediate(
        self,
        symbol: str,
        transactions: list[dict],
        buys: list[dict],
        sales: list[dict],
        sentiment: str,
        net_value: float,
        total_buy_value: float,
        total_sell_value: float,
    ) -> dict[str, Any]:
        """Format for intermediate mode - detailed insider metrics."""
        # Calculate clusters (multiple insiders buying within short period)
        buy_clusters = self._find_clusters(buys)

        # Separate by insider type
        exec_buys = [t for t in buys if self._is_executive(t.get("owner_title"))]
        exec_sales = [t for t in sales if self._is_executive(t.get("owner_title"))]

        return {
            "symbol": symbol,
            "summary": {
                "insider_sentiment": sentiment,
                "timeframe": "6 months",
                "total_transactions": len(transactions),
                "buy_transactions": len(buys),
                "sell_transactions": len(sales),
            },
            "financial_metrics": {
                "total_buy_value": round(total_buy_value, 2),
                "total_sell_value": round(total_sell_value, 2),
                "net_insider_value": round(net_value, 2),
                "buy_sell_ratio": round(total_buy_value / total_sell_value, 2) if total_sell_value > 0 else None,
            },
            "activity_breakdown": {
                "executive_buys": len(exec_buys),
                "executive_sells": len(exec_sales),
                "buy_clusters_detected": len(buy_clusters),
                "largest_buy": {
                    "value": round(float(buys[0]["value"]), 2),
                    "insider": buys[0].get("owner_name"),
                    "date": str(buys[0]["transaction_date"]),
                } if buys and buys[0].get("value") else None,
            },
            "recent_transactions": [
                {
                    "transaction_date": str(t["transaction_date"]) if t.get("transaction_date") else None,
                    "filing_date": str(t["filing_date"]) if t.get("filing_date") else None,
                    "owner_name": t.get("owner_name"),
                    "owner_title": t.get("owner_title"),
                    "transaction_type": "Purchase" if t.get("transaction_type") == "P" else "Sale" if t.get("transaction_type") == "S" else t.get("transaction_type"),
                    "shares": int(t["shares"]) if t.get("shares") else None,
                    "price_per_share": round(float(t["price_per_share"]), 2) if t.get("price_per_share") else None,
                    "total_value": round(float(t["value"]), 2) if t.get("value") else None,
                }
                for t in transactions[:15]
            ],
            "interpretation": self._get_intermediate_interpretation(sentiment, len(buy_clusters), len(exec_buys)),
            "trading_signal": self._get_trading_signal(sentiment, len(buy_clusters)),
        }

    def _format_advanced(
        self,
        symbol: str,
        transactions: list[dict],
        buys: list[dict],
        sales: list[dict],
        sentiment: str,
        total_buy_value: float,
        total_sell_value: float,
    ) -> dict[str, Any]:
        """Format for advanced mode - comprehensive insider analysis."""
        # Advanced analytics
        buy_clusters = self._find_clusters(buys)
        timing_analysis = self._analyze_timing(buys, sales)
        insider_patterns = self._analyze_patterns(transactions)

        # Breakdown by transaction type
        purchases = [t for t in transactions if t.get("transaction_type") == "P"]
        sales_trans = [t for t in transactions if t.get("transaction_type") == "S"]
        awards = [t for t in transactions if t.get("transaction_type") == "A"]
        exercises = [t for t in transactions if t.get("transaction_type") == "M"]

        # Breakdown by insider role
        exec_trans = [t for t in transactions if self._is_executive(t.get("owner_title"))]
        board_trans = [t for t in transactions if "director" in (t.get("owner_title") or "").lower()]

        return {
            "symbol": symbol,
            "sentiment_analysis": {
                "overall_sentiment": sentiment,
                "sentiment_score": self._calculate_sentiment_score(total_buy_value, total_sell_value),
                "confidence": self._assess_confidence(len(buys), len(sales), buy_clusters),
            },
            "transaction_breakdown": {
                "purchases": len(purchases),
                "sales": len(sales_trans),
                "awards": len(awards),
                "option_exercises": len(exercises),
                "direct_ownership": len([t for t in transactions if t.get("is_direct_ownership")]),
                "indirect_ownership": len([t for t in transactions if not t.get("is_direct_ownership")]),
            },
            "financial_analysis": {
                "total_buy_value": round(total_buy_value, 2),
                "total_sell_value": round(total_sell_value, 2),
                "net_value": round(total_buy_value - total_sell_value, 2),
                "buy_sell_ratio": round(total_buy_value / total_sell_value, 2) if total_sell_value > 0 else None,
                "avg_buy_size": round(total_buy_value / len(buys), 2) if buys else None,
                "avg_sell_size": round(total_sell_value / len(sales), 2) if sales else None,
            },
            "insider_role_breakdown": {
                "executive_transactions": len(exec_trans),
                "board_transactions": len(board_trans),
                "executive_net_value": round(self._calculate_net_value(exec_trans), 2),
            },
            "cluster_analysis": {
                "buy_clusters": len(buy_clusters),
                "cluster_details": [
                    {
                        "date_range": f"{c['start_date']} to {c['end_date']}",
                        "insiders": c["count"],
                        "total_value": round(c["value"], 2),
                    }
                    for c in buy_clusters[:3]
                ],
            },
            "timing_analysis": timing_analysis,
            "patterns": insider_patterns,
            "all_transactions": [
                {
                    "transaction_date": str(t["transaction_date"]) if t.get("transaction_date") else None,
                    "filing_date": str(t["filing_date"]) if t.get("filing_date") else None,
                    "owner_name": t.get("owner_name"),
                    "owner_title": t.get("owner_title"),
                    "transaction_type": t.get("transaction_type"),
                    "shares": int(t["shares"]) if t.get("shares") else None,
                    "price_per_share": round(float(t["price_per_share"]), 4) if t.get("price_per_share") else None,
                    "value": round(float(t["value"]), 2) if t.get("value") else None,
                    "shares_owned_after": int(t["shares_owned_after"]) if t.get("shares_owned_after") else None,
                    "is_direct": t.get("is_direct_ownership"),
                }
                for t in transactions
            ],
            "trading_implications": {
                "signal_strength": self._assess_signal_strength(sentiment, len(buy_clusters), len(buys)),
                "recommended_action": self._get_recommended_action(sentiment, len(buy_clusters)),
                "risk_factors": self._get_risk_factors(total_sell_value, total_buy_value),
            },
        }

    @staticmethod
    def _assess_sentiment(buy_value: float, sell_value: float, buy_count: int, sell_count: int) -> str:
        """Assess overall insider sentiment."""
        if buy_value == 0 and sell_value == 0:
            return "neutral"

        # Net value ratio
        net_ratio = (buy_value - sell_value) / (buy_value + sell_value) if (buy_value + sell_value) > 0 else 0

        # Transaction count ratio
        count_ratio = (buy_count - sell_count) / (buy_count + sell_count) if (buy_count + sell_count) > 0 else 0

        # Combined score
        combined_score = (net_ratio * 0.7) + (count_ratio * 0.3)

        if combined_score > 0.5:
            return "very_bullish"
        elif combined_score > 0.15:
            return "bullish"
        elif combined_score < -0.5:
            return "very_bearish"
        elif combined_score < -0.15:
            return "bearish"
        else:
            return "neutral"

    @staticmethod
    def _is_executive(title: Optional[str]) -> bool:
        """Check if insider is an executive."""
        if not title:
            return False
        title_lower = title.lower()
        exec_keywords = ["ceo", "cfo", "coo", "president", "chief", "officer", "vp", "vice president"]
        return any(keyword in title_lower for keyword in exec_keywords)

    @staticmethod
    def _find_clusters(transactions: list[dict]) -> list[dict]:
        """Find clusters of buying activity (multiple insiders buying within 30 days)."""
        if len(transactions) < 2:
            return []

        clusters = []
        sorted_trans = sorted(transactions, key=lambda t: t.get("transaction_date") or date.min)

        i = 0
        while i < len(sorted_trans):
            cluster_start = sorted_trans[i]["transaction_date"]
            cluster_end = cluster_start + timedelta(days=30)

            cluster_trans = []
            j = i
            while j < len(sorted_trans) and sorted_trans[j]["transaction_date"] <= cluster_end:
                cluster_trans.append(sorted_trans[j])
                j += 1

            if len(cluster_trans) >= 2:  # At least 2 insiders
                cluster_value = sum(float(t["value"]) for t in cluster_trans if t.get("value"))
                clusters.append({
                    "start_date": str(cluster_start),
                    "end_date": str(sorted_trans[j-1]["transaction_date"]) if j > i else str(cluster_start),
                    "count": len(cluster_trans),
                    "value": cluster_value,
                })

            i = j if j > i else i + 1

        return clusters

    @staticmethod
    def _analyze_timing(buys: list[dict], sales: list[dict]) -> dict:
        """Analyze timing patterns of insider transactions."""
        if not buys and not sales:
            return {"pattern": "no_activity"}

        recent_30d = date.today() - timedelta(days=30)
        recent_90d = date.today() - timedelta(days=90)

        recent_buys_30d = len([b for b in buys if b.get("transaction_date") and b["transaction_date"] >= recent_30d])
        recent_sales_30d = len([s for s in sales if s.get("transaction_date") and s["transaction_date"] >= recent_30d])

        recent_buys_90d = len([b for b in buys if b.get("transaction_date") and b["transaction_date"] >= recent_90d])
        recent_sales_90d = len([s for s in sales if s.get("transaction_date") and s["transaction_date"] >= recent_90d])

        pattern = "unknown"
        if recent_buys_30d > 3:
            pattern = "accelerating_buys"
        elif recent_sales_30d > 5:
            pattern = "accelerating_sales"
        elif recent_buys_90d > recent_buys_30d * 2:
            pattern = "slowing_buys"
        else:
            pattern = "steady"

        return {
            "pattern": pattern,
            "recent_30d_buys": recent_buys_30d,
            "recent_30d_sales": recent_sales_30d,
            "recent_90d_buys": recent_buys_90d,
            "recent_90d_sales": recent_sales_90d,
        }

    @staticmethod
    def _analyze_patterns(transactions: list[dict]) -> dict:
        """Analyze insider trading patterns."""
        if not transactions:
            return {"pattern_type": "no_data"}

        # Count unique insiders
        unique_insiders = len(set(t.get("owner_name") for t in transactions if t.get("owner_name")))

        # Check for repeated buyers
        buyer_counts = {}
        for t in transactions:
            if t.get("transaction_type") == "P" and t.get("owner_name"):
                buyer_counts[t["owner_name"]] = buyer_counts.get(t["owner_name"], 0) + 1

        repeat_buyers = sum(1 for count in buyer_counts.values() if count > 1)

        pattern_type = "unknown"
        if repeat_buyers > 2:
            pattern_type = "consistent_accumulation"
        elif unique_insiders > 5 and len([t for t in transactions if t.get("transaction_type") == "P"]) > 7:
            pattern_type = "broad_buying"
        elif len([t for t in transactions if t.get("transaction_type") == "S"]) > len([t for t in transactions if t.get("transaction_type") == "P"]) * 2:
            pattern_type = "heavy_selling"
        else:
            pattern_type = "mixed"

        return {
            "pattern_type": pattern_type,
            "unique_insiders": unique_insiders,
            "repeat_buyers": repeat_buyers,
        }

    @staticmethod
    def _calculate_net_value(transactions: list[dict]) -> float:
        """Calculate net transaction value."""
        buys = sum(float(t["value"]) for t in transactions if t.get("transaction_type") == "P" and t.get("value"))
        sales = sum(float(t["value"]) for t in transactions if t.get("transaction_type") == "S" and t.get("value"))
        return buys - sales

    @staticmethod
    def _calculate_sentiment_score(buy_value: float, sell_value: float) -> int:
        """Calculate sentiment score (0-100)."""
        if buy_value + sell_value == 0:
            return 50

        ratio = buy_value / (buy_value + sell_value)
        return int(ratio * 100)

    @staticmethod
    def _assess_confidence(buy_count: int, sell_count: int, clusters: list) -> str:
        """Assess confidence in sentiment signal."""
        if buy_count >= 5 and len(clusters) >= 2:
            return "high"
        elif buy_count >= 3:
            return "moderate"
        else:
            return "low"

    @staticmethod
    def _get_beginner_summary(sentiment: str, buy_count: int, sell_count: int) -> str:
        """Get beginner summary."""
        summaries = {
            "very_bullish": f"Insiders are buying heavily! {buy_count} buy transactions vs {sell_count} sales. Very bullish signal.",
            "bullish": f"Insiders are buying. {buy_count} buys vs {sell_count} sales. Bullish signal.",
            "neutral": f"Mixed insider activity. {buy_count} buys, {sell_count} sales. No clear signal.",
            "bearish": f"More insider selling than buying. {buy_count} buys vs {sell_count} sales. Caution.",
            "very_bearish": f"Heavy insider selling. {buy_count} buys vs {sell_count} sales. Warning sign.",
        }
        return summaries.get(sentiment, "Insider activity unclear")

    @staticmethod
    def _explain_sentiment(sentiment: str) -> str:
        """Explain what sentiment means."""
        explanations = {
            "very_bullish": "Multiple insiders buying = they think stock is undervalued. Strong bullish signal.",
            "bullish": "Net insider buying = positive signal. Insiders think stock will go up.",
            "neutral": "Balanced activity. Some routine selling (compensation), some buying. No clear signal.",
            "bearish": "More selling than buying. May be normal compensation sales OR bearish signal.",
            "very_bearish": "Heavy insider selling = insiders may see problems or overvaluation. Proceed with caution.",
        }
        return explanations.get(sentiment, "Unclear")

    @staticmethod
    def _get_beginner_advice(sentiment: str) -> str:
        """Get beginner advice."""
        advice = {
            "very_bullish": "Strong buy signal. Consider buying, but verify other factors (fundamentals, technicals).",
            "bullish": "Positive signal. Can add to conviction if considering purchase.",
            "neutral": "No clear signal from insiders. Make decision based on other factors.",
            "bearish": "Caution. Wait for more data or avoid unless you have strong contrarian thesis.",
            "very_bearish": "Warning sign. Insiders know something. Avoid or consider selling if you own.",
        }
        return advice.get(sentiment, "Evaluate carefully")

    @staticmethod
    def _get_intermediate_interpretation(sentiment: str, clusters: int, exec_buys: int) -> str:
        """Get intermediate interpretation."""
        base = f"Insider sentiment: {sentiment}. "

        if clusters >= 2:
            base += f"{clusters} buy clusters detected (multiple insiders buying within 30 days). "

        if exec_buys >= 3:
            base += f"{exec_buys} executive purchases. "

        if sentiment in ["very_bullish", "bullish"]:
            base += "Bullish signal with good confidence."
        elif sentiment == "neutral":
            base += "Mixed signals. Monitor for changes."
        else:
            base += "Bearish undertone. Exercise caution."

        return base

    @staticmethod
    def _get_trading_signal(sentiment: str, clusters: int) -> str:
        """Get trading signal."""
        if sentiment == "very_bullish" and clusters >= 2:
            return "STRONG BUY - Multiple insiders buying in clusters"
        elif sentiment == "bullish":
            return "BUY - Net insider buying"
        elif sentiment == "neutral":
            return "HOLD - Mixed activity"
        elif sentiment == "bearish":
            return "CAUTION - More selling than buying"
        else:
            return "AVOID - Heavy insider selling"

    @staticmethod
    def _assess_signal_strength(sentiment: str, clusters: int, buy_count: int) -> str:
        """Assess signal strength."""
        if sentiment in ["very_bullish", "very_bearish"]:
            if clusters >= 2 or buy_count >= 5:
                return "very_strong"
            else:
                return "strong"
        elif sentiment in ["bullish", "bearish"]:
            return "moderate"
        else:
            return "weak"

    @staticmethod
    def _get_recommended_action(sentiment: str, clusters: int) -> str:
        """Get recommended action."""
        if sentiment == "very_bullish" and clusters >= 2:
            return "Consider buying - strong insider confidence"
        elif sentiment == "bullish":
            return "Positive signal - can support buy thesis"
        elif sentiment == "neutral":
            return "No action based on insiders - use other factors"
        elif sentiment == "bearish":
            return "Wait for clarity - insider activity concerning"
        else:
            return "Avoid or consider selling - heavy insider selling"

    @staticmethod
    def _get_risk_factors(sell_value: float, buy_value: float) -> list[str]:
        """Get risk factors."""
        risks = []

        if sell_value > buy_value * 3:
            risks.append("Heavy insider selling - may indicate problems")

        if buy_value == 0:
            risks.append("No insider buying - insiders not confident")

        risks.append("Insider data is delayed (filed within 2 days of transaction)")
        risks.append("Some selling is routine (compensation, diversification)")

        return risks
