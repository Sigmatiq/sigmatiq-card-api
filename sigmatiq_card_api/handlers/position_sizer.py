"""
Position Sizer Handler - Calculate position sizes based on risk parameters.

Utility card that helps traders size positions appropriately:
- Risk-based position sizing
- Kelly Criterion calculator
- Fixed fractional method
- Volatility-adjusted sizing

No database dependency - pure calculation utility.
"""

from datetime import date
from typing import Any, Optional

from fastapi import HTTPException

from ..models.cards import CardMode
from .base import BaseCardHandler


class PositionSizerHandler(BaseCardHandler):
    """Handler for position_sizer card - position sizing calculator."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Position sizing calculator - requires query parameters.

        Expected query params: account_size, risk_pct, entry_price, stop_price
        """
        # This is a utility card - returns educational framework
        # Actual calculations would be done client-side or via additional params

        if mode == CardMode.beginner:
            return {
                "tool_type": "position_sizer",
                "description": "Calculate how many shares to buy based on your risk tolerance",
                "formula_simple": "Shares = (Account Size × Risk %) ÷ (Entry Price - Stop Price)",
                "example": {
                    "account_size": 10000,
                    "risk_per_trade_pct": 1,
                    "entry_price": 50,
                    "stop_loss": 48,
                    "calculation": "($10,000 × 1%) ÷ ($50 - $48) = $100 ÷ $2 = 50 shares",
                    "max_loss_if_stopped": "$100 (1% of account)",
                },
                "beginner_rules": [
                    "Never risk more than 1-2% of account on single trade",
                    "Always use stop losses",
                    "Smaller position = less stress",
                    "Account for commissions in calculation",
                ],
                "educational_tip": "Position sizing is THE most important risk management tool. Even great traders lose when position sizing is wrong.",
            }
        elif mode == CardMode.intermediate:
            return {
                "tool_type": "position_sizer",
                "methods": {
                    "fixed_risk": {
                        "description": "Risk fixed % of capital per trade",
                        "formula": "Shares = (Account × Risk%) ÷ (Entry - Stop)",
                        "recommended_risk": "0.5-2% for most traders",
                    },
                    "volatility_based": {
                        "description": "Adjust size based on stock volatility (ATR)",
                        "formula": "Shares = (Account × Risk%) ÷ (ATR × Multiplier)",
                        "use_when": "Trading different volatility stocks",
                    },
                    "kelly_criterion": {
                        "description": "Mathematical optimal sizing based on edge",
                        "formula": "f = (p × b - q) ÷ b",
                        "warning": "Use half-Kelly or quarter-Kelly to be safe",
                    },
                },
                "position_limits": {
                    "beginner": "Max 5% per position, max 3-4 positions",
                    "intermediate": "Max 10% per position, max 5-8 positions",
                    "advanced": "Max 20% per position (concentrated strategy)",
                },
                "risk_examples": [
                    {"account": 10000, "risk_pct": 1, "shares_50_stock_2_stop": 50},
                    {"account": 25000, "risk_pct": 2, "shares_100_stock_5_stop": 100},
                    {"account": 50000, "risk_pct": 1.5, "shares_75_stock_3_stop": 250},
                ],
            }
        else:
            return {
                "tool_type": "position_sizer",
                "advanced_methods": {
                    "fixed_fractional": {
                        "formula": "Position Size = (Account × f) ÷ Price",
                        "parameters": {"f": "fixed fraction (e.g., 0.02 for 2%)"},
                        "pros": "Simple, consistent",
                        "cons": "Doesn't account for volatility differences",
                    },
                    "volatility_adjusted": {
                        "formula": "Shares = (Account × Risk%) ÷ (ATR × ATR_Multiplier)",
                        "parameters": {
                            "ATR": "Average True Range (14-period typical)",
                            "ATR_Multiplier": "2-3x for stop placement",
                        },
                        "pros": "Normalizes risk across different volatility stocks",
                        "cons": "Requires ATR calculation",
                    },
                    "kelly_criterion": {
                        "formula": "f* = (p × b - q) ÷ b",
                        "parameters": {
                            "p": "probability of win",
                            "q": "probability of loss (1-p)",
                            "b": "win/loss ratio",
                        },
                        "example": "p=0.6, b=2:1 → f* = (0.6×2 - 0.4)÷2 = 0.4 (40%)",
                        "warning": "Use fractional Kelly (0.25-0.5 of full Kelly) due to estimation error",
                        "pros": "Mathematically optimal for bankroll growth",
                        "cons": "Requires accurate win rate and R:R estimates",
                    },
                    "optimal_f": {
                        "description": "Ralph Vince's Optimal f",
                        "formula": "f = largest loss ÷ largest winning trade",
                        "pros": "Based on actual trade history",
                        "cons": "Can be aggressive, use fractional",
                    },
                },
                "correlation_adjustment": {
                    "description": "Reduce total exposure when positions are correlated",
                    "formula": "Adjusted_Risk = Base_Risk × sqrt(1 + (n-1) × ρ)",
                    "example": "3 tech stocks with 0.7 correlation → reduce each position by ~30%",
                },
                "practical_limits": {
                    "single_position": "Never exceed 25% of account (extreme limit)",
                    "sector_concentration": "Max 30-40% in any sector",
                    "total_exposure": "100% = fully invested, 150% = 1.5x leveraged (danger zone)",
                },
            }
