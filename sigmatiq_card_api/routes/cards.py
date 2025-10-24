"""
Cards API routes.

Provides endpoints for retrieving pre-formatted market data cards.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query

from ..config import get_backfill_pool, get_cards_pool
from ..handlers.economic_calendar import EconomicCalendarHandler
from ..handlers.index_heatmap import IndexHeatmapHandler
from ..handlers.market_breadth import MarketBreadthHandler
from ..handlers.market_regime import MarketRegimeHandler
from ..handlers.market_summary import MarketSummaryHandler
from ..handlers.options_0dte import ZeroDTEFlowHandler
from ..handlers.options_flow import OptionsFlowHandler
from ..handlers.options_gex import GEXHandler
from ..handlers.options_iv_skew import IVSkewHandler
from ..handlers.position_sizer import PositionSizerHandler
from ..handlers.risk_calculator import RiskCalculatorHandler
from ..handlers.sector_rotation import SectorRotationHandler
from ..handlers.technical_breadth import TechnicalBreadthHandler
from ..handlers.ticker_52w import Ticker52WHandler
from ..handlers.ticker_analyst import AnalystRatingsHandler
from ..handlers.ticker_breakout import BreakoutWatchHandler
from ..handlers.ticker_correlation import CorrelationAnalysisHandler
from ..handlers.ticker_dividends import DividendsCalendarHandler
from ..handlers.ticker_earnings import EarningsCalendarHandler
from ..handlers.ticker_insider import InsiderTransactionsHandler
from ..handlers.ticker_institutional import InstitutionalOwnershipHandler
from ..handlers.ticker_liquidity import LiquidityHandler
from ..handlers.ticker_momentum import MomentumPulseHandler
from ..handlers.ticker_news import NewsSentimentHandler
from ..handlers.ticker_options_chain import OptionsChainHandler
from ..handlers.ticker_performance import TickerPerformanceHandler
from ..handlers.ticker_relative_strength import RelativeStrengthHandler
from ..handlers.ticker_reversal import ReversalWatchHandler
from ..handlers.ticker_short_interest import ShortInterestHandler
from ..handlers.ticker_trend import TickerTrendHandler
from ..handlers.ticker_volatility import VolatilitySnapshotHandler
from ..handlers.unusual_options import UnusualOptionsHandler
from ..handlers.volume_profile import VolumeProfileHandler
from ..handlers.watchlist_stats import WatchlistStatsHandler
from ..models.cards import CardMode, CardResponse
from ..services.card_service import CardService

router = APIRouter(prefix="/cards", tags=["cards"])


async def get_card_service():
    """
    Dependency to create CardService with registered handlers.

    Returns:
        CardService: Configured card service
    """
    cards_pool = await get_cards_pool()
    backfill_pool = await get_backfill_pool()

    service = CardService(cards_pool=cards_pool, backfill_pool=backfill_pool)

    # Register market card handlers
    service.register_handler("economic_calendar", EconomicCalendarHandler(backfill_pool))
    service.register_handler("market_breadth", MarketBreadthHandler(backfill_pool))
    service.register_handler("index_heatmap", IndexHeatmapHandler(backfill_pool))
    service.register_handler("market_regime", MarketRegimeHandler(backfill_pool))
    service.register_handler("market_summary", MarketSummaryHandler(backfill_pool))
    service.register_handler("sector_rotation", SectorRotationHandler(backfill_pool))
    service.register_handler("technical_breadth", TechnicalBreadthHandler(backfill_pool))

    # Register ticker card handlers
    service.register_handler("ticker_performance", TickerPerformanceHandler(backfill_pool))
    service.register_handler("ticker_52w", Ticker52WHandler(backfill_pool))
    service.register_handler("ticker_breakout", BreakoutWatchHandler(backfill_pool))
    service.register_handler("ticker_dividends", DividendsCalendarHandler(backfill_pool))
    service.register_handler("ticker_earnings", EarningsCalendarHandler(backfill_pool))
    service.register_handler("ticker_liquidity", LiquidityHandler(backfill_pool))
    service.register_handler("ticker_momentum", MomentumPulseHandler(backfill_pool))
    service.register_handler("ticker_news", NewsSentimentHandler(backfill_pool))
    service.register_handler("ticker_relative_strength", RelativeStrengthHandler(backfill_pool))
    service.register_handler("ticker_reversal", ReversalWatchHandler(backfill_pool))
    service.register_handler("ticker_trend", TickerTrendHandler(backfill_pool))
    service.register_handler("ticker_volatility", VolatilitySnapshotHandler(backfill_pool))
    service.register_handler("volume_profile", VolumeProfileHandler(backfill_pool))

    # Register options card handlers
    service.register_handler("unusual_options", UnusualOptionsHandler(backfill_pool))
    service.register_handler("options_flow", OptionsFlowHandler(backfill_pool))
    service.register_handler("options_0dte", ZeroDTEFlowHandler(backfill_pool))
    service.register_handler("options_gex", GEXHandler(backfill_pool))
    service.register_handler("options_iv_skew", IVSkewHandler(backfill_pool))

    # Register Phase 2D institutional/sentiment handlers
    service.register_handler("ticker_short_interest", ShortInterestHandler(backfill_pool))
    service.register_handler("ticker_insider", InsiderTransactionsHandler(backfill_pool))
    service.register_handler("ticker_institutional", InstitutionalOwnershipHandler(backfill_pool))
    service.register_handler("ticker_analyst", AnalystRatingsHandler(backfill_pool))

    # Register Phase 3 utility and analysis handlers
    service.register_handler("ticker_correlation", CorrelationAnalysisHandler(backfill_pool))
    service.register_handler("ticker_options_chain", OptionsChainHandler(backfill_pool))
    service.register_handler("position_sizer", PositionSizerHandler(backfill_pool))
    service.register_handler("risk_calculator", RiskCalculatorHandler(backfill_pool))
    service.register_handler("watchlist_stats", WatchlistStatsHandler(backfill_pool))

    return service


@router.get("/{card_id}", response_model=CardResponse)
async def get_card(
    card_id: str,
    mode: CardMode = Query(CardMode.beginner, description="Complexity level"),
    symbol: Optional[str] = Query(None, description="Stock symbol (required for ticker cards)"),
    date_param: Optional[date] = Query(None, alias="date", description="Trading date (defaults to latest)"),
    x_user_id: str = Header(..., alias="X-User-Id", description="User identifier for analytics"),
    card_service: CardService = Depends(get_card_service),
):
    """
    Get card data.

    ## Parameters
    - **card_id**: Card identifier (e.g., 'market_breadth', 'ticker_performance', 'index_heatmap')
    - **mode**: Complexity level - beginner (plain language), intermediate (more detail), advanced (all metrics)
    - **symbol**: Stock symbol (required for ticker-specific cards like 'ticker_performance')
    - **date**: Trading date in YYYY-MM-DD format (defaults to most recent trading day)

    ## Headers
    - **X-User-Id**: User identifier for usage tracking

    ## Example Requests

    ```bash
    # Market breadth (beginner mode)
    curl -H "X-User-Id: test" \\
      "http://localhost:8006/api/v1/cards/market_breadth?mode=beginner"

    # Ticker performance (intermediate mode)
    curl -H "X-User-Id: test" \\
      "http://localhost:8006/api/v1/cards/ticker_performance?symbol=AAPL&mode=intermediate"

    # Index heatmap (advanced mode, specific date)
    curl -H "X-User-Id: test" \\
      "http://localhost:8006/api/v1/cards/index_heatmap?mode=advanced&date=2025-10-22"
    ```

    ## Response
    Returns a CardResponse with:
    - **card_id**: Card identifier
    - **mode**: Requested complexity level
    - **data**: Card-specific formatted data
    - **meta**: Metadata (trading date, fallback status, data source, timestamp)

    ## Error Responses
    - **400**: Bad request (e.g., missing required symbol parameter)
    - **403**: Card is disabled
    - **404**: Card not found or no data available for requested date
    - **500**: Internal server error
    """
    return await card_service.get_card_data(
        card_id=card_id,
        mode=mode,
        symbol=symbol,
        date_param=date_param,
        user_id=x_user_id,
    )
