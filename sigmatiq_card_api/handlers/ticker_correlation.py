"""
Correlation Analysis Handler - Price correlation with indices and related stocks.

Shows correlation metrics:
- Correlation to SPY, QQQ, sector ETF
- Beta calculation
- Related stocks correlation
- Correlation stability

Data source: sb.correlation_matrix or calculated from price history
"""

from datetime import date, timedelta
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class CorrelationAnalysisHandler(BaseCardHandler):
    """Handler for ticker_correlation card - correlation and beta analysis."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        if not symbol:
            raise HTTPException(400, "Symbol required for ticker_correlation")

        # Fetch correlation data (if pre-calculated)
        corr_query = """
            SELECT
                correlation_spy,
                correlation_qqq,
                correlation_sector_etf,
                beta_spy,
                sector
            FROM sb.symbol_correlations
            WHERE symbol = $1 AND as_of_date = $2
            LIMIT 1
        """

        corr_data = await self._fetch_one(corr_query, {"symbol": symbol, "as_of_date": trading_date})

        if not corr_data:
            raise HTTPException(404, f"No correlation data for {symbol}")

        spy_corr = float(corr_data["correlation_spy"]) if corr_data.get("correlation_spy") else None
        qqq_corr = float(corr_data["correlation_qqq"]) if corr_data.get("correlation_qqq") else None
        beta = float(corr_data["beta_spy"]) if corr_data.get("beta_spy") else None

        if mode == CardMode.beginner:
            return {
                "symbol": symbol,
                "correlation_to_market": round(spy_corr, 2) if spy_corr else None,
                "correlation_strength": self._classify_correlation(spy_corr) if spy_corr else "Unknown",
                "beta": round(beta, 2) if beta else None,
                "beta_meaning": self._explain_beta(beta) if beta else "Beta not available",
                "simple_explanation": f"Stock moves {abs(spy_corr)*100:.0f}% in sync with S&P 500." if spy_corr else "Correlation data not available",
                "educational_tip": "Correlation shows if stock moves with the market. High correlation = stock follows market trends. Low correlation = independent moves.",
                "practical_use": self._get_practical_use(spy_corr, beta),
            }
        elif mode == CardMode.intermediate:
            return {
                "symbol": symbol,
                "market_correlations": {
                    "spy_correlation": round(spy_corr, 3) if spy_corr else None,
                    "qqq_correlation": round(qqq_corr, 3) if qqq_corr else None,
                    "sector_etf_correlation": round(float(corr_data["correlation_sector_etf"]), 3) if corr_data.get("correlation_sector_etf") else None,
                },
                "beta_analysis": {
                    "beta_spy": round(beta, 3) if beta else None,
                    "volatility_vs_market": self._classify_beta(beta) if beta else "Unknown",
                    "interpretation": self._interpret_beta(beta) if beta else "No beta data",
                },
                "correlation_classification": {
                    "spy": self._classify_correlation(spy_corr) if spy_corr else "Unknown",
                    "qqq": self._classify_correlation(qqq_corr) if qqq_corr else "Unknown",
                },
                "trading_implications": {
                    "hedging": self._get_hedging_advice(spy_corr, beta),
                    "diversification": self._get_diversification_value(spy_corr),
                },
                "sector": corr_data.get("sector"),
            }
        else:
            return {
                "symbol": symbol,
                "correlation_metrics": {
                    "spy_correlation": round(spy_corr, 6) if spy_corr else None,
                    "qqq_correlation": round(qqq_corr, 6) if qqq_corr else None,
                    "sector_etf_correlation": round(float(corr_data["correlation_sector_etf"]), 6) if corr_data.get("correlation_sector_etf") else None,
                    "correlation_r_squared": round(spy_corr ** 2, 4) if spy_corr else None,
                },
                "beta_metrics": {
                    "beta_spy": round(beta, 6) if beta else None,
                    "systematic_risk_pct": round((spy_corr ** 2) * 100, 2) if spy_corr else None,
                    "idiosyncratic_risk_pct": round((1 - spy_corr ** 2) * 100, 2) if spy_corr else None,
                },
                "risk_decomposition": {
                    "market_driven": f"{(spy_corr**2)*100:.1f}%" if spy_corr else None,
                    "stock_specific": f"{(1-spy_corr**2)*100:.1f}%" if spy_corr else None,
                    "interpretation": "Market explains variance" if spy_corr and spy_corr**2 > 0.5 else "Mostly stock-specific risk",
                },
                "portfolio_implications": {
                    "hedge_ratio": round(beta, 4) if beta else None,
                    "hedge_ratio_explanation": f"Short {abs(beta):.2f} SPY per $1 long {symbol}" if beta else None,
                    "diversification_benefit": "Low" if spy_corr and abs(spy_corr) > 0.7 else "Moderate" if spy_corr and abs(spy_corr) > 0.4 else "High",
                },
            }

    @staticmethod
    def _classify_correlation(corr: Optional[float]) -> str:
        """Classify correlation strength."""
        if corr is None:
            return "Unknown"
        abs_corr = abs(corr)
        if abs_corr > 0.8:
            return "Very Strong"
        elif abs_corr > 0.6:
            return "Strong"
        elif abs_corr > 0.4:
            return "Moderate"
        elif abs_corr > 0.2:
            return "Weak"
        else:
            return "Very Weak/Uncorrelated"

    @staticmethod
    def _explain_beta(beta: Optional[float]) -> str:
        """Explain beta in beginner terms."""
        if beta is None:
            return "Beta not available"
        if beta > 1.5:
            return f"Beta {beta:.1f} - Stock is MUCH more volatile than market. Big swings up and down."
        elif beta > 1.0:
            return f"Beta {beta:.1f} - Stock moves MORE than market. When market up 1%, stock up {beta:.1f}%."
        elif beta > 0.5:
            return f"Beta {beta:.1f} - Stock moves LESS than market. More stable, less volatile."
        elif beta > 0:
            return f"Beta {beta:.1f} - Stock barely moves with market. Very low volatility."
        else:
            return f"Beta {beta:.1f} - Stock moves OPPOSITE of market. Rare."

    @staticmethod
    def _classify_beta(beta: Optional[float]) -> str:
        """Classify beta level."""
        if beta is None:
            return "Unknown"
        if beta > 1.5:
            return "High Volatility"
        elif beta > 1.0:
            return "Above Market"
        elif beta > 0.8:
            return "Market-like"
        elif beta > 0.5:
            return "Below Market"
        elif beta > 0:
            return "Low Volatility"
        else:
            return "Negative (Inverse)"

    @staticmethod
    def _interpret_beta(beta: Optional[float]) -> str:
        """Interpret beta value."""
        if beta is None:
            return "No beta data available"
        if beta > 1:
            return f"Beta {beta:.2f} means stock is {(beta-1)*100:.0f}% more volatile than S&P 500"
        elif beta < 1:
            return f"Beta {beta:.2f} means stock is {(1-beta)*100:.0f}% less volatile than S&P 500"
        else:
            return "Beta 1.0 means stock moves exactly with market"

    @staticmethod
    def _get_practical_use(corr: Optional[float], beta: Optional[float]) -> str:
        """Get practical use of correlation data."""
        if corr and abs(corr) > 0.7:
            return "High correlation - stock follows market. Good for sector plays, watch S&P direction."
        elif corr and abs(corr) < 0.3:
            return "Low correlation - stock independent. Good for diversification, less affected by market moves."
        else:
            return "Moderate correlation - some market influence but also independent factors."

    @staticmethod
    def _get_hedging_advice(corr: Optional[float], beta: Optional[float]) -> str:
        """Get hedging advice."""
        if not beta:
            return "Beta required for hedge calculation"
        if abs(beta) < 0.3:
            return "Low beta - hedging with SPY not effective"
        elif beta > 0:
            return f"Long stock hedges with {beta:.2f}x short SPY position"
        else:
            return "Negative beta - acts as natural hedge"

    @staticmethod
    def _get_diversification_value(corr: Optional[float]) -> str:
        """Get diversification value."""
        if not corr:
            return "Unknown"
        if abs(corr) > 0.8:
            return "Low diversification value - highly correlated with market"
        elif abs(corr) > 0.5:
            return "Moderate diversification value"
        else:
            return "High diversification value - low market correlation"
