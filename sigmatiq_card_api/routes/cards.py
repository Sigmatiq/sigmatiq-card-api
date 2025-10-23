"""
Cards API routes.

Provides endpoints for retrieving pre-formatted market data cards.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query

from ..config import get_backfill_pool, get_cards_pool
from ..handlers.index_heatmap import IndexHeatmapHandler
from ..handlers.market_breadth import MarketBreadthHandler
from ..handlers.market_regime import MarketRegimeHandler
from ..handlers.options_flow import OptionsFlowHandler
from ..handlers.sector_rotation import SectorRotationHandler
from ..handlers.technical_breadth import TechnicalBreadthHandler
from ..handlers.ticker_52w import Ticker52WHandler
from ..handlers.ticker_performance import TickerPerformanceHandler
from ..handlers.ticker_trend import TickerTrendHandler
from ..handlers.unusual_options import UnusualOptionsHandler
from ..handlers.volume_profile import VolumeProfileHandler
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
    service.register_handler("market_breadth", MarketBreadthHandler(backfill_pool))
    service.register_handler("index_heatmap", IndexHeatmapHandler(backfill_pool))
    service.register_handler("market_regime", MarketRegimeHandler(backfill_pool))
    service.register_handler("sector_rotation", SectorRotationHandler(backfill_pool))
    service.register_handler("technical_breadth", TechnicalBreadthHandler(backfill_pool))

    # Register ticker card handlers
    service.register_handler("ticker_performance", TickerPerformanceHandler(backfill_pool))
    service.register_handler("ticker_52w", Ticker52WHandler(backfill_pool))
    service.register_handler("ticker_trend", TickerTrendHandler(backfill_pool))
    service.register_handler("volume_profile", VolumeProfileHandler(backfill_pool))

    # Register options card handlers
    service.register_handler("unusual_options", UnusualOptionsHandler(backfill_pool))
    service.register_handler("options_flow", OptionsFlowHandler(backfill_pool))

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
