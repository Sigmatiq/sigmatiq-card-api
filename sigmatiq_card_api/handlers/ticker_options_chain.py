"""
Options Chain Summary Handler - Key options chain metrics at-a-glance.

Shows critical options data:
- ATM options (at-the-money)
- Near-term expiration summary
- Put/Call ratio
- Open interest distribution

Data source: sb.options_chain_summary (aggregated view)
"""

from datetime import date, timedelta
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class OptionsChainHandler(BaseCardHandler):
    """Handler for ticker_options_chain card - options chain summary."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        if not symbol:
            raise HTTPException(400, "Symbol required for ticker_options_chain")

        # Get ATM options for next expiration
        atm_query = """
            SELECT
                expiration_date,
                strike_price,
                call_bid, call_ask, call_volume, call_open_interest, call_iv,
                put_bid, put_ask, put_volume, put_open_interest, put_iv
            FROM sb.options_chain
            WHERE symbol = $1
              AND quote_date = $2
              AND expiration_date >= $3
              AND ABS(strike_price - $4) < $5
            ORDER BY expiration_date ASC, ABS(strike_price - $4) ASC
            LIMIT 10
        """

        # Get current stock price
        price_query = """
            SELECT close
            FROM sb.equity_bars_daily
            WHERE symbol = $1 AND trading_date = $2
            LIMIT 1
        """

        # Get summary metrics
        summary_query = """
            SELECT
                expiration_date,
                SUM(call_volume) as total_call_volume,
                SUM(put_volume) as total_put_volume,
                SUM(call_open_interest) as total_call_oi,
                SUM(put_open_interest) as total_put_oi
            FROM sb.options_chain
            WHERE symbol = $1 AND quote_date = $2
            GROUP BY expiration_date
            ORDER BY expiration_date ASC
            LIMIT 5
        """

        price_row = await self._fetch_one(price_query, {"symbol": symbol, "trading_date": trading_date})
        current_price = float(price_row["close"]) if price_row and price_row.get("close") else None

        if not current_price:
            raise HTTPException(404, f"No price data for {symbol}")

        # Strike range for ATM (within 5% of current price)
        strike_range = current_price * 0.05

        atm_options = await self._fetch_all(atm_query, {
            "symbol": symbol,
            "quote_date": trading_date,
            "min_expiration": trading_date + timedelta(days=1),
            "current_price": current_price,
            "strike_range": strike_range,
        })

        summary = await self._fetch_all(summary_query, {"symbol": symbol, "quote_date": trading_date})

        if not atm_options and not summary:
            raise HTTPException(404, f"No options data for {symbol}")

        # Calculate PCR
        if summary:
            total_put_vol = sum(float(s["total_put_volume"]) for s in summary if s.get("total_put_volume"))
            total_call_vol = sum(float(s["total_call_volume"]) for s in summary if s.get("total_call_volume"))
            pcr = total_put_vol / total_call_vol if total_call_vol > 0 else None
        else:
            pcr = None

        if mode == CardMode.beginner:
            next_exp = atm_options[0] if atm_options else None
            return {
                "symbol": symbol,
                "current_price": f"${current_price:.2f}" if current_price else None,
                "has_options": bool(atm_options),
                "next_expiration": str(next_exp["expiration_date"]) if next_exp else None,
                "days_to_expiration": (next_exp["expiration_date"] - trading_date).days if next_exp else None,
                "atm_call_price": f"${float(next_exp['call_ask']):.2f}" if next_exp and next_exp.get("call_ask") else None,
                "atm_put_price": f"${float(next_exp['put_ask']):.2f}" if next_exp and next_exp.get("put_ask") else None,
                "put_call_ratio": round(pcr, 2) if pcr else None,
                "pcr_interpretation": self._interpret_pcr_beginner(pcr) if pcr else "No data",
                "educational_tip": "Options give right to buy (call) or sell (put) stock at set price. ATM = at-the-money (strike near current price). Options expire worthless if not in-the-money.",
                "beginner_warning": "Options are complex and risky. Can lose 100% of premium. Paper trade first.",
            }
        elif mode == CardMode.intermediate:
            return {
                "symbol": symbol,
                "current_price": round(current_price, 2) if current_price else None,
                "atm_options_next_exp": [
                    {
                        "expiration": str(opt["expiration_date"]),
                        "strike": round(float(opt["strike_price"]), 2) if opt.get("strike_price") else None,
                        "call_bid_ask": f"${float(opt['call_bid']):.2f}/${float(opt['call_ask']):.2f}" if opt.get("call_bid") and opt.get("call_ask") else None,
                        "put_bid_ask": f"${float(opt['put_bid']):.2f}/${float(opt['put_ask']):.2f}" if opt.get("put_bid") and opt.get("put_ask") else None,
                        "call_iv": f"{float(opt['call_iv'])*100:.1f}%" if opt.get("call_iv") else None,
                        "put_iv": f"{float(opt['put_iv'])*100:.1f}%" if opt.get("put_iv") else None,
                    }
                    for opt in atm_options[:5]
                ],
                "volume_analysis": {
                    "put_call_ratio": round(pcr, 3) if pcr else None,
                    "interpretation": self._interpret_pcr(pcr) if pcr else "Unknown",
                },
                "expiration_summary": [
                    {
                        "expiration": str(s["expiration_date"]),
                        "call_volume": int(s["total_call_volume"]) if s.get("total_call_volume") else 0,
                        "put_volume": int(s["total_put_volume"]) if s.get("total_put_volume") else 0,
                        "call_oi": int(s["total_call_oi"]) if s.get("total_call_oi") else 0,
                        "put_oi": int(s["total_put_oi"]) if s.get("total_put_oi") else 0,
                    }
                    for s in summary
                ],
            }
        else:
            return {
                "symbol": symbol,
                "underlying_price": round(current_price, 4) if current_price else None,
                "atm_chain": [
                    {
                        "expiration_date": str(opt["expiration_date"]),
                        "days_to_expiration": (opt["expiration_date"] - trading_date).days,
                        "strike_price": round(float(opt["strike_price"]), 4) if opt.get("strike_price") else None,
                        "moneyness": round((float(opt["strike_price"]) - current_price) / current_price * 100, 2) if opt.get("strike_price") and current_price else None,
                        "call": {
                            "bid": round(float(opt["call_bid"]), 4) if opt.get("call_bid") else None,
                            "ask": round(float(opt["call_ask"]), 4) if opt.get("call_ask") else None,
                            "volume": int(opt["call_volume"]) if opt.get("call_volume") else 0,
                            "open_interest": int(opt["call_open_interest"]) if opt.get("call_open_interest") else 0,
                            "implied_volatility": round(float(opt["call_iv"]), 6) if opt.get("call_iv") else None,
                        },
                        "put": {
                            "bid": round(float(opt["put_bid"]), 4) if opt.get("put_bid") else None,
                            "ask": round(float(opt["put_ask"]), 4) if opt.get("put_ask") else None,
                            "volume": int(opt["put_volume"]) if opt.get("put_volume") else 0,
                            "open_interest": int(opt["put_open_interest"]) if opt.get("put_open_interest") else 0,
                            "implied_volatility": round(float(opt["put_iv"]), 6) if opt.get("put_iv") else None,
                        },
                    }
                    for opt in atm_options
                ],
                "aggregate_metrics": {
                    "put_call_volume_ratio": round(pcr, 6) if pcr else None,
                    "sentiment": self._classify_pcr(pcr) if pcr else "Unknown",
                },
                "by_expiration": [
                    {
                        "expiration_date": str(s["expiration_date"]),
                        "days_to_expiration": (s["expiration_date"] - trading_date).days,
                        "metrics": {
                            "total_call_volume": int(s["total_call_volume"]) if s.get("total_call_volume") else 0,
                            "total_put_volume": int(s["total_put_volume"]) if s.get("total_put_volume") else 0,
                            "total_call_oi": int(s["total_call_oi"]) if s.get("total_call_oi") else 0,
                            "total_put_oi": int(s["total_put_oi"]) if s.get("total_put_oi") else 0,
                            "put_call_volume_ratio": round(float(s["total_put_volume"]) / float(s["total_call_volume"]), 4) if s.get("total_call_volume") and float(s["total_call_volume"]) > 0 else None,
                            "put_call_oi_ratio": round(float(s["total_put_oi"]) / float(s["total_call_oi"]), 4) if s.get("total_call_oi") and float(s["total_call_oi"]) > 0 else None,
                        },
                    }
                    for s in summary
                ],
            }

    @staticmethod
    def _interpret_pcr_beginner(pcr: float) -> str:
        """Beginner interpretation of PCR."""
        if pcr > 1.5:
            return "Very bearish - many more puts than calls being traded"
        elif pcr > 1.0:
            return "Bearish - more puts than calls (fear/hedging)"
        elif pcr > 0.7:
            return "Neutral - balanced put/call activity"
        else:
            return "Bullish - more calls than puts (optimism)"

    @staticmethod
    def _interpret_pcr(pcr: float) -> str:
        """Intermediate interpretation of PCR."""
        if pcr > 1.5:
            return "Extremely bearish sentiment or heavy hedging"
        elif pcr > 1.0:
            return "Bearish/defensive positioning"
        elif pcr > 0.7:
            return "Neutral market sentiment"
        elif pcr > 0.5:
            return "Moderately bullish sentiment"
        else:
            return "Very bullish/speculative positioning"

    @staticmethod
    def _classify_pcr(pcr: float) -> str:
        """Classify PCR level."""
        if pcr > 1.2:
            return "very_bearish"
        elif pcr > 0.9:
            return "bearish"
        elif pcr > 0.7:
            return "neutral"
        elif pcr > 0.5:
            return "bullish"
        else:
            return "very_bullish"
