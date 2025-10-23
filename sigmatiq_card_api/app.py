"""
Sigmatiq Card API - Main application.

Provides pre-formatted market data cards for UI integration.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sigmatiq_shared.cache import get_last_cache_metadata
from sigmatiq_shared.middleware import CacheHeaderASGIMiddleware

from .config import close_db_pools, get_settings
from .routes import cards

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    settings = get_settings()
    logger.info(f"Starting Sigmatiq Card API on port {settings.api_port}")
    logger.info(f"Cards DB: {settings.cards_database_url}")
    logger.info(f"Backfill DB: {settings.backfill_database_url}")

    yield

    # Shutdown
    logger.info("Shutting down Sigmatiq Card API")
    await close_db_pools()
    logger.info("Database pools closed")


# Create FastAPI application
app = FastAPI(
    title="Sigmatiq Card API",
    description="""
    Market data cards API providing pre-formatted, beginner-friendly data.

    ## Features
    - **EOD Cards**: Historical end-of-day market data
    - **Beginner-First**: Plain language explanations and labels
    - **Multi-Level**: Beginner, intermediate, and advanced modes
    - **Usage Analytics**: Track requests for insights

    ## Card Types
    - `market_breadth`: Overall market health (advancing/declining, highs/lows)
    - `ticker_performance`: Single stock analysis (price, volume, indicators)
    - `index_heatmap`: Major indices performance comparison

    ## Authentication
    All endpoints require an `X-User-Id` header for usage tracking.

    ## Response Format
    All card endpoints return a standardized `CardResponse` with:
    - `card_id`: Card identifier
    - `mode`: Complexity level used
    - `data`: Card-specific formatted data
    - `meta`: Metadata (date, fallback status, data source, timestamp)
    """,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add cache header middleware (reads contextvars and injects X-Sigma-Cache-* headers)
app.add_middleware(CacheHeaderASGIMiddleware, get_meta=get_last_cache_metadata)

# Register routers
app.include_router(cards.router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "name": "Sigmatiq Card API",
        "version": "0.1.0",
        "status": "operational",
        "docs": "/docs",
        "endpoints": {
            "cards": "/api/v1/cards/{card_id}",
        },
    }


@app.get("/healthz")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
