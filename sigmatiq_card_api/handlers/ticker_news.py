"""
News Sentiment Handler - News and sentiment analysis.

Shows news sentiment metrics:
- Overall sentiment score
- Recent news headlines
- Sentiment trend
- Source distribution

Data source: sb.news_sentiment (expected table)
"""

from datetime import date, timedelta
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class NewsSentimentHandler(BaseCardHandler):
    """Handler for ticker_news card - news sentiment analysis."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Fetch news sentiment data for the given symbol.

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
                detail="Symbol is required for ticker_news card",
            )

        # Fetch recent news articles
        news_query = """
            SELECT
                published_at,
                title,
                source,
                sentiment_score,  -- -1 to +1
                sentiment_label,  -- 'negative', 'neutral', 'positive'
                relevance_score,  -- 0 to 1
                url
            FROM sb.news_sentiment
            WHERE symbol = $1
              AND published_at >= $2
              AND published_at <= $3
            ORDER BY published_at DESC
            LIMIT 20
        """

        # Date range: last 7 days
        end_date = trading_date
        start_date = trading_date - timedelta(days=7)

        articles = await self._fetch_all(
            news_query,
            {"symbol": symbol, "start_date": start_date, "end_date": end_date}
        )

        if not articles:
            raise HTTPException(
                status_code=404,
                detail=f"No recent news for {symbol}",
            )

        # Calculate aggregate metrics
        sentiment_scores = [float(a["sentiment_score"]) for a in articles if a.get("sentiment_score") is not None]
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0

        # Count sentiment labels
        sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
        for article in articles:
            label = article.get("sentiment_label", "neutral")
            if label in sentiment_counts:
                sentiment_counts[label] += 1

        # Format based on mode
        if mode == CardMode.beginner:
            return self._format_beginner(symbol, articles, avg_sentiment, sentiment_counts)
        elif mode == CardMode.intermediate:
            return self._format_intermediate(symbol, articles, avg_sentiment, sentiment_counts)
        else:
            return self._format_advanced(symbol, articles, avg_sentiment, sentiment_counts)

    def _format_beginner(
        self,
        symbol: str,
        articles: list[dict],
        avg_sentiment: float,
        sentiment_counts: dict,
    ) -> dict[str, Any]:
        """Format for beginner mode - simple news sentiment overview."""
        sentiment_label = self._classify_sentiment(avg_sentiment)

        emoji_map = {
            "very_positive": "🚀",
            "positive": "📈",
            "neutral": "➡️",
            "negative": "📉",
            "very_negative": "⚠️",
        }

        return {
            "symbol": symbol,
            "overall_sentiment": sentiment_label,
            "sentiment_emoji": emoji_map.get(sentiment_label, "❓"),
            "sentiment_score": round(avg_sentiment * 100),  # Convert -1/+1 to -100/+100
            "simple_explanation": self._get_sentiment_explanation(sentiment_label),
            "article_count": len(articles),
            "sentiment_breakdown": {
                "positive": sentiment_counts["positive"],
                "neutral": sentiment_counts["neutral"],
                "negative": sentiment_counts["negative"],
            },
            "recent_headlines": [
                {
                    "title": a["title"],
                    "sentiment": a.get("sentiment_label", "neutral"),
                    "date": str(a["published_at"].date()) if a.get("published_at") else None,
                }
                for a in articles[:5]
            ],
            "advice": self._get_beginner_advice(sentiment_label, sentiment_counts),
            "educational_tip": "News sentiment shows market mood. Positive news doesn't guarantee price increase, but extreme negative news often predicts volatility.",
        }

    def _format_intermediate(
        self,
        symbol: str,
        articles: list[dict],
        avg_sentiment: float,
        sentiment_counts: dict,
    ) -> dict[str, Any]:
        """Format for intermediate mode - detailed news analysis."""
        sentiment_label = self._classify_sentiment(avg_sentiment)

        # Calculate sentiment trend (comparing recent vs older articles)
        mid_point = len(articles) // 2
        recent_articles = articles[:mid_point] if mid_point > 0 else articles
        older_articles = articles[mid_point:] if mid_point > 0 else []

        recent_sentiment = self._calculate_avg_sentiment(recent_articles)
        older_sentiment = self._calculate_avg_sentiment(older_articles) if older_articles else recent_sentiment

        sentiment_trend = "improving" if recent_sentiment > older_sentiment + 0.1 else "declining" if recent_sentiment < older_sentiment - 0.1 else "stable"

        # Source analysis
        sources = {}
        for article in articles:
            source = article.get("source", "Unknown")
            if source not in sources:
                sources[source] = 0
            sources[source] += 1

        return {
            "symbol": symbol,
            "sentiment_metrics": {
                "overall_sentiment": sentiment_label,
                "sentiment_score": round(avg_sentiment, 3),
                "sentiment_score_pct": round(avg_sentiment * 100, 1),
                "article_count_7d": len(articles),
                "sentiment_trend": sentiment_trend,
            },
            "sentiment_distribution": {
                "positive": sentiment_counts["positive"],
                "positive_pct": round(sentiment_counts["positive"] / len(articles) * 100, 1),
                "neutral": sentiment_counts["neutral"],
                "neutral_pct": round(sentiment_counts["neutral"] / len(articles) * 100, 1),
                "negative": sentiment_counts["negative"],
                "negative_pct": round(sentiment_counts["negative"] / len(articles) * 100, 1),
            },
            "sources": [{"name": source, "count": count} for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True)[:5]],
            "recent_articles": [
                {
                    "title": a["title"],
                    "source": a.get("source"),
                    "sentiment_label": a.get("sentiment_label"),
                    "sentiment_score": round(a["sentiment_score"], 2) if a.get("sentiment_score") is not None else None,
                    "relevance": round(a["relevance_score"], 2) if a.get("relevance_score") is not None else None,
                    "published_at": str(a["published_at"]) if a.get("published_at") else None,
                }
                for a in articles[:10]
            ],
            "interpretation": self._get_intermediate_interpretation(sentiment_label, sentiment_trend, sentiment_counts),
        }

    def _format_advanced(
        self,
        symbol: str,
        articles: list[dict],
        avg_sentiment: float,
        sentiment_counts: dict,
    ) -> dict[str, Any]:
        """Format for advanced mode - comprehensive sentiment analysis."""
        sentiment_label = self._classify_sentiment(avg_sentiment)

        # Detailed trend analysis
        trend_analysis = self._analyze_sentiment_trend(articles)

        # Source credibility weighting
        weighted_sentiment = self._calculate_weighted_sentiment(articles)

        # High-relevance articles
        high_relevance = [a for a in articles if a.get("relevance_score", 0) > 0.7]

        # Source distribution
        sources = {}
        for article in articles:
            source = article.get("source", "Unknown")
            if source not in sources:
                sources[source] = {"count": 0, "avg_sentiment": []}
            sources[source]["count"] += 1
            if article.get("sentiment_score") is not None:
                sources[source]["avg_sentiment"].append(article["sentiment_score"])

        source_analysis = [
            {
                "source": source,
                "article_count": data["count"],
                "avg_sentiment": round(sum(data["avg_sentiment"]) / len(data["avg_sentiment"]), 4) if data["avg_sentiment"] else None,
            }
            for source, data in sources.items()
        ]

        return {
            "symbol": symbol,
            "sentiment_analysis": {
                "overall_sentiment": sentiment_label,
                "raw_sentiment_score": round(avg_sentiment, 6),
                "sentiment_score_pct": round(avg_sentiment * 100, 2),
                "weighted_sentiment_score": round(weighted_sentiment, 6),
                "sentiment_strength": self._assess_sentiment_strength(avg_sentiment, sentiment_counts, len(articles)),
            },
            "distribution": {
                "positive": sentiment_counts["positive"],
                "positive_pct": round(sentiment_counts["positive"] / len(articles) * 100, 2),
                "neutral": sentiment_counts["neutral"],
                "neutral_pct": round(sentiment_counts["neutral"] / len(articles) * 100, 2),
                "negative": sentiment_counts["negative"],
                "negative_pct": round(sentiment_counts["negative"] / len(articles) * 100, 2),
            },
            "trend_analysis": trend_analysis,
            "source_analysis": sorted(source_analysis, key=lambda x: x["article_count"], reverse=True)[:10],
            "high_relevance_articles": [
                {
                    "title": a["title"],
                    "source": a.get("source"),
                    "sentiment_score": round(a["sentiment_score"], 4) if a.get("sentiment_score") is not None else None,
                    "relevance_score": round(a["relevance_score"], 4) if a.get("relevance_score") is not None else None,
                    "published_at": str(a["published_at"]) if a.get("published_at") else None,
                    "url": a.get("url"),
                }
                for a in high_relevance[:5]
            ],
            "all_articles": [
                {
                    "title": a["title"],
                    "source": a.get("source"),
                    "sentiment_score": round(a["sentiment_score"], 6) if a.get("sentiment_score") is not None else None,
                    "relevance_score": round(a["relevance_score"], 6) if a.get("relevance_score") is not None else None,
                    "published_at": str(a["published_at"]) if a.get("published_at") else None,
                }
                for a in articles
            ],
            "trading_implications": {
                "sentiment_divergence": self._assess_divergence(avg_sentiment, sentiment_counts),
                "news_intensity": "high" if len(articles) > 15 else "moderate" if len(articles) > 5 else "low",
                "actionability": self._assess_actionability(avg_sentiment, weighted_sentiment, high_relevance),
            },
        }

    @staticmethod
    def _classify_sentiment(avg_sentiment: float) -> str:
        """Classify average sentiment."""
        if avg_sentiment > 0.5:
            return "very_positive"
        elif avg_sentiment > 0.15:
            return "positive"
        elif avg_sentiment > -0.15:
            return "neutral"
        elif avg_sentiment > -0.5:
            return "negative"
        else:
            return "very_negative"

    @staticmethod
    def _get_sentiment_explanation(sentiment_label: str) -> str:
        """Get beginner explanation of sentiment."""
        explanations = {
            "very_positive": "News is very positive. Market is excited about this stock. Watch for overenthusiasm.",
            "positive": "News is mostly positive. Good momentum, but verify fundamentals.",
            "neutral": "News is balanced. No strong catalyst either way.",
            "negative": "News is mostly negative. Exercise caution. May present buying opportunity if oversold.",
            "very_negative": "News is very negative. High risk. Wait for situation to stabilize.",
        }
        return explanations.get(sentiment_label, "Sentiment unclear.")

    @staticmethod
    def _get_beginner_advice(sentiment_label: str, sentiment_counts: dict) -> str:
        """Get beginner trading advice."""
        total = sum(sentiment_counts.values())
        positive_ratio = sentiment_counts["positive"] / total if total > 0 else 0

        if sentiment_label == "very_positive" and positive_ratio > 0.7:
            return "Strong positive news, but don't chase highs. Wait for pullback or confirmation."
        elif sentiment_label == "positive":
            return "Favorable news environment. Good for swing trades with momentum."
        elif sentiment_label == "neutral":
            return "Mixed news. Focus on technical analysis and price action instead."
        elif sentiment_label == "negative":
            return "Negative sentiment. Avoid unless you're an experienced contrarian investor."
        else:
            return "Very negative sentiment. High risk - stay away unless you have strong conviction."

    @staticmethod
    def _get_intermediate_interpretation(sentiment_label: str, trend: str, counts: dict) -> str:
        """Get intermediate interpretation."""
        base = f"Overall sentiment: {sentiment_label}. "

        if trend == "improving":
            base += "Sentiment improving - momentum building."
        elif trend == "declining":
            base += "Sentiment declining - watch for breakdown."
        else:
            base += "Sentiment stable."

        total = sum(counts.values())
        if total > 0:
            consensus = max(counts.values()) / total
            if consensus > 0.7:
                base += " Strong consensus in news."
            else:
                base += " News opinions divided."

        return base

    @staticmethod
    def _calculate_avg_sentiment(articles: list[dict]) -> float:
        """Calculate average sentiment for a list of articles."""
        scores = [float(a["sentiment_score"]) for a in articles if a.get("sentiment_score") is not None]
        return sum(scores) / len(scores) if scores else 0.0

    @staticmethod
    def _analyze_sentiment_trend(articles: list[dict]) -> dict:
        """Analyze sentiment trend over time."""
        if len(articles) < 4:
            return {"trend": "insufficient_data"}

        # Split into quarters
        quarter_size = len(articles) // 4
        quarters = [
            articles[i*quarter_size:(i+1)*quarter_size]
            for i in range(4)
        ]

        quarter_sentiments = [
            sum(float(a["sentiment_score"]) for a in q if a.get("sentiment_score") is not None) / len(q) if q else 0
            for q in quarters
        ]

        # Determine trend
        if all(quarter_sentiments[i] < quarter_sentiments[i+1] for i in range(len(quarter_sentiments)-1)):
            trend = "strongly_improving"
        elif all(quarter_sentiments[i] > quarter_sentiments[i+1] for i in range(len(quarter_sentiments)-1)):
            trend = "strongly_declining"
        elif quarter_sentiments[-1] > quarter_sentiments[0]:
            trend = "improving"
        elif quarter_sentiments[-1] < quarter_sentiments[0]:
            trend = "declining"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "most_recent": round(quarter_sentiments[-1], 4),
            "oldest": round(quarter_sentiments[0], 4),
            "momentum": round(quarter_sentiments[-1] - quarter_sentiments[0], 4),
        }

    @staticmethod
    def _calculate_weighted_sentiment(articles: list[dict]) -> float:
        """Calculate sentiment weighted by relevance score."""
        weighted_sum = 0.0
        weight_total = 0.0

        for article in articles:
            sentiment = article.get("sentiment_score")
            relevance = article.get("relevance_score", 0.5)

            if sentiment is not None:
                weighted_sum += float(sentiment) * float(relevance)
                weight_total += float(relevance)

        return weighted_sum / weight_total if weight_total > 0 else 0.0

    @staticmethod
    def _assess_sentiment_strength(avg_sentiment: float, counts: dict, total: int) -> str:
        """Assess strength of sentiment signal."""
        if abs(avg_sentiment) > 0.6:
            strength = "very_strong"
        elif abs(avg_sentiment) > 0.3:
            strength = "strong"
        elif abs(avg_sentiment) > 0.1:
            strength = "moderate"
        else:
            strength = "weak"

        # Adjust for consensus
        if total > 0:
            max_count = max(counts.values())
            consensus = max_count / total
            if consensus < 0.5:
                strength = "weak"  # Downgrade if no consensus

        return strength

    @staticmethod
    def _assess_divergence(avg_sentiment: float, counts: dict) -> str:
        """Assess if there's divergence in sentiment."""
        total = sum(counts.values())
        if total == 0:
            return "unknown"

        # Check if sentiment distribution is polarized
        positive_ratio = counts["positive"] / total
        negative_ratio = counts["negative"] / total
        neutral_ratio = counts["neutral"] / total

        if neutral_ratio > 0.6:
            return "no_strong_opinion"
        elif positive_ratio > 0.7 or negative_ratio > 0.7:
            return "strong_consensus"
        elif positive_ratio > 0.4 and negative_ratio > 0.4:
            return "high_divergence"  # Mixed opinions
        else:
            return "moderate_consensus"

    @staticmethod
    def _assess_actionability(avg_sentiment: float, weighted_sentiment: float, high_relevance: list) -> str:
        """Assess how actionable the sentiment signal is."""
        if len(high_relevance) < 3:
            return "low - insufficient high-relevance articles"

        if abs(avg_sentiment) > 0.5 and abs(weighted_sentiment) > 0.5:
            return "high - strong sentiment with high relevance"
        elif abs(avg_sentiment) > 0.3:
            return "moderate - decent signal strength"
        else:
            return "low - weak or neutral sentiment"
