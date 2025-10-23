"""
Pydantic models for Card API responses.

These models define the structure of API responses for all card endpoints.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class CardMode(str, Enum):
    """Complexity level for card responses."""

    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class CardCategory(str, Enum):
    """Card categories for organization."""

    market = "market"
    ticker = "ticker"
    options = "options"
    technical = "technical"
    fundamental = "fundamental"


class CardMeta(BaseModel):
    """Metadata about the card response."""

    card_id: str = Field(..., description="Unique identifier for the card")
    mode: CardMode = Field(..., description="Complexity level of the response")
    title: str = Field(..., description="Human-readable card title")
    category: CardCategory = Field(..., description="Card category")
    symbol: Optional[str] = Field(None, description="Symbol if ticker-specific card")
    trading_date: date = Field(..., description="Actual trading date used for data")
    requested_date: Optional[date] = Field(None, description="Date requested by user (may differ)")
    fallback_applied: bool = Field(
        False, description="True if fallback to previous trading day was used"
    )
    data_source: str = Field(
        "postgresql", description="Data source (postgresql or polygon)"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response generation timestamp"
    )


class CardResponse(BaseModel):
    """Standard response format for all card endpoints."""

    card_id: str = Field(..., description="Card identifier")
    mode: CardMode = Field(..., description="Response complexity level")
    data: dict[str, Any] = Field(..., description="Card-specific data payload")
    meta: CardMeta = Field(..., description="Response metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "card_id": "market_breadth",
                "mode": "beginner",
                "data": {
                    "pct_above_ma50": 62,
                    "pct_above_ma50_label": "62% of stocks above 50-day average",
                    "breadth_health": "healthy",
                    "breadth_health_label": "More stocks hitting highs (33) vs lows (12)",
                    "educational_tip": "Market breadth shows if price moves are supported...",
                },
                "meta": {
                    "card_id": "market_breadth",
                    "mode": "beginner",
                    "title": "Market Breadth",
                    "category": "market",
                    "trading_date": "2025-10-23",
                    "fallback_applied": False,
                    "data_source": "postgresql",
                    "timestamp": "2025-10-23T10:30:00Z",
                },
            }
        }


class CardCatalogEntry(BaseModel):
    """Card catalog entry from database."""

    card_id: str
    title: str
    description: Optional[str] = None
    category: str
    requires_symbol: bool = False
    minimum_tier: str = "free"
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class CardUsageLog(BaseModel):
    """Usage log entry (for internal analytics)."""

    user_id: str
    card_id: str
    mode: CardMode
    symbol: Optional[str] = None
    date_param: Optional[date] = None
    actual_date: Optional[date] = None
    response_status: int
    response_time_ms: int
    credits_charged: float = 1.0
    tier: str = "free"
