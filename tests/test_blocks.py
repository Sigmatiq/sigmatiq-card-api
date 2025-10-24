import types

from sigmatiq_card_api.handlers.ticker_performance import TickerPerformanceHandler
from sigmatiq_card_api.handlers.market_breadth import MarketBreadthHandler
from sigmatiq_card_api.handlers.unusual_options import UnusualOptionsHandler
from sigmatiq_card_api.handlers.market_regime import MarketRegimeHandler
from sigmatiq_card_api.handlers.market_summary import MarketSummaryHandler


def test_ticker_performance_action_block_basic():
    h = TickerPerformanceHandler(db_pool=None)  # db not used by helper
    block = h._build_action_block_beginner(
        symbol="AAPL",
        rsi_14=55,
        atr_pct=1.8,
        dist_ma20=2.0,
        dist_ma50=4.0,
        macd=0.5,
        macd_signal=0.1,
        rvol=1.2,
    )
    assert "entry" in block and "invalidation" in block and "risk" in block


def test_market_breadth_bias_block():
    h = MarketBreadthHandler(db_pool=None)
    block = h._build_bias_block(pct_above_ma50=65.0, ad_ratio=1.2, new_highs=50, new_lows=20)
    assert block["bias"] in ("risk_on", "neutral", "risk_off")


def test_unusual_options_strategy_hint():
    h = UnusualOptionsHandler(db_pool=None)
    features = {"days_to_earnings": 5}
    hint = h._build_strategy_hint(iv30=55.0, features=features)
    assert hint["iv_regime"] == "High"
    assert hint["event_window_days"] == 5
    assert "suggestion" in hint


def test_market_regime_bias_block():
    h = MarketRegimeHandler(db_pool=None)
    block = h._build_bias_block("TREND")
    assert block["bias"] == "risk_on"


def test_market_summary_bias_block():
    h = MarketSummaryHandler(db_pool=None)
    block = h._build_bias_block("Bullish", 65.0)
    assert block["bias"] == "risk_on"
