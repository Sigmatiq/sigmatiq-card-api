"""
Risk Calculator Handler - Risk/reward ratio and trade analysis calculator.

Utility card for analyzing trade risk:
- Risk/reward ratio calculation
- Win rate needed for profitability
- Expected value calculation
- Breakeven analysis

No database dependency - pure calculation utility.
"""

from datetime import date
from typing import Any, Optional

from ..models.cards import CardMode
from .base import BaseCardHandler


class RiskCalculatorHandler(BaseCardHandler):
    """Handler for risk_calculator card - risk/reward analysis."""

    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """Risk/reward calculator - educational framework."""

        if mode == CardMode.beginner:
            return {
                "tool_type": "risk_calculator",
                "description": "Calculate if a trade has good risk/reward before entering",
                "basic_formula": "R:R Ratio = Potential Profit ÷ Potential Loss",
                "example_good_trade": {
                    "entry": 50,
                    "target": 56,
                    "stop": 48,
                    "potential_profit": 6,
                    "potential_loss": 2,
                    "risk_reward_ratio": "3:1 (Excellent!)",
                    "explanation": "$6 profit potential vs $2 risk = 3:1. Only need 33% win rate to break even.",
                },
                "example_bad_trade": {
                    "entry": 50,
                    "target": 51,
                    "stop": 48,
                    "potential_profit": 1,
                    "potential_loss": 2,
                    "risk_reward_ratio": "0.5:1 (Poor!)",
                    "explanation": "$1 profit vs $2 risk = 0.5:1. Need 67% win rate to break even. Avoid!",
                },
                "beginner_rules": [
                    "Minimum 2:1 risk/reward for most trades",
                    "3:1 or better = great trade setup",
                    "Never take trades worse than 1:1",
                    "Higher R:R allows lower win rate",
                ],
                "educational_tip": "You can be wrong more than half the time and still make money IF you have good risk/reward ratios.",
            }
        elif mode == CardMode.intermediate:
            return {
                "tool_type": "risk_calculator",
                "formulas": {
                    "risk_reward_ratio": "R:R = (Target - Entry) ÷ (Entry - Stop)",
                    "breakeven_win_rate": "Breakeven % = 1 ÷ (1 + R:R)",
                    "expected_value": "EV = (Win% × Avg Win) - (Loss% × Avg Loss)",
                },
                "rr_breakeven_table": [
                    {"rr": "1:1", "breakeven_wr": "50%", "comment": "Poor - need to win half"},
                    {"rr": "1.5:1", "breakeven_wr": "40%", "comment": "Acceptable for high win rate strategies"},
                    {"rr": "2:1", "breakeven_wr": "33%", "comment": "Good - standard minimum"},
                    {"rr": "3:1", "breakeven_wr": "25%", "comment": "Excellent - can lose 3 of 4"},
                    {"rr": "5:1", "breakeven_wr": "16.7%", "comment": "Outstanding - rare setups"},
                ],
                "win_rate_analysis": {
                    "description": "At 2:1 R:R, your expected return by win rate:",
                    "30_pct_wr": "-$10 per $100 risked (losing)",
                    "40_pct_wr": "+$20 per $100 risked (profitable)",
                    "50_pct_wr": "+$50 per $100 risked (excellent)",
                },
                "practical_application": {
                    "day_trading": "Need 2-3:1 minimum due to frequent stops",
                    "swing_trading": "2:1 minimum, 3:1 preferred",
                    "position_trading": "1.5-2:1 acceptable if high win rate",
                },
            }
        else:
            return {
                "tool_type": "risk_calculator",
                "advanced_calculations": {
                    "expected_value_formula": "EV = Σ(Probability × Outcome)",
                    "ev_example": {
                        "win_prob": 0.45,
                        "avg_win": 300,
                        "loss_prob": 0.55,
                        "avg_loss": 100,
                        "calculation": "(0.45 × $300) - (0.55 × $100) = $135 - $55 = $80 EV per trade",
                        "interpretation": "Positive EV system - profitable long-term",
                    },
                    "kelly_fraction_relationship": {
                        "description": "Optimal bet size relates to edge and odds",
                        "formula": "f* = edge ÷ odds = (p×b - q) ÷ b",
                        "connection": "Higher R:R allows larger position with same edge",
                    },
                    "sharpe_ratio_approximation": {
                        "formula": "Sharpe ≈ (Avg Return - Rf) ÷ StdDev",
                        "interpretation": ">1.0 good, >2.0 excellent, >3.0 exceptional",
                    },
                },
                "system_evaluation": {
                    "minimum_viable_system": {
                        "description": "Minimum stats for profitable system",
                        "requirements": [
                            "Win Rate × Avg R:R > 1.0 (breakeven)",
                            "Win Rate × Avg R:R > 1.3 (covers costs/slippage)",
                            "Sample size > 30-50 trades (statistical significance)",
                        ],
                    },
                    "system_comparison": [
                        {
                            "name": "High Win Rate",
                            "win_rate": 0.65,
                            "avg_rr": 1.2,
                            "expectancy": 0.36,
                            "style": "Mean reversion, tight stops",
                        },
                        {
                            "name": "Trend Following",
                            "win_rate": 0.40,
                            "avg_rr": 3.0,
                            "expectancy": 0.80,
                            "style": "Momentum, wide stops, asymmetric",
                        },
                        {
                            "name": "Balanced",
                            "win_rate": 0.50,
                            "avg_rr": 2.0,
                            "expectancy": 0.50,
                            "style": "Swing trading, selective entries",
                        },
                    ],
                },
                "risk_metrics": {
                    "max_drawdown": "Largest peak-to-trough decline",
                    "recovery_factor": "Net Profit ÷ Max Drawdown (>2.0 good)",
                    "profit_factor": "Gross Profit ÷ Gross Loss (>1.5 good, >2.0 excellent)",
                    "consecutive_losses": "Plan for 5-10 in a row (2.5x your average)",
                },
            }
