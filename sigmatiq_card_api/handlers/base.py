"""
Base handler class for all card implementations.

All card handlers must inherit from BaseCardHandler and implement the fetch method.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Optional

import asyncpg

from ..models.cards import CardMode


class BaseCardHandler(ABC):
    """Abstract base class for card data handlers."""

    def __init__(self, db_pool: asyncpg.Pool):
        """
        Initialize handler with database pool.

        Args:
            db_pool: asyncpg connection pool
        """
        self.db_pool = db_pool

    @abstractmethod
    async def fetch(
        self,
        mode: CardMode,
        symbol: Optional[str],
        trading_date: date,
    ) -> dict[str, Any]:
        """
        Fetch card data from database.

        Args:
            mode: Complexity level (beginner/intermediate/advanced)
            symbol: Stock symbol (None for market-wide cards)
            trading_date: Trading date to fetch data for

        Returns:
            Dictionary with card-specific data formatted for the given mode

        Raises:
            ValueError: If symbol is required but not provided
            HTTPException: If data not found or database error
        """
        pass

    def _format_label(self, value: Any, suffix: str = "") -> str:
        """
        Helper to format values with labels for beginner mode.

        Args:
            value: Raw value
            suffix: Optional suffix (e.g., "%", "M shares")

        Returns:
            Formatted string
        """
        if isinstance(value, float):
            return f"{value:.2f}{suffix}"
        return f"{value}{suffix}"

    def _get_health_label(self, value: float, thresholds: dict[str, float]) -> str:
        """
        Helper to categorize numeric values into health labels.

        Args:
            value: Numeric value to categorize
            thresholds: Dictionary with 'good' and 'bad' threshold values

        Returns:
            Label: "healthy", "neutral", or "weak"
        """
        if value >= thresholds.get("good", 60):
            return "healthy"
        elif value <= thresholds.get("bad", 40):
            return "weak"
        else:
            return "neutral"

    def _add_educational_tip(self, card_id: str, mode: CardMode) -> Optional[str]:
        """
        Get educational tip for a card (beginner mode only).

        Args:
            card_id: Card identifier
            mode: Complexity level

        Returns:
            Educational tip string or None
        """
        if mode != CardMode.beginner:
            return None

        tips = {
            "market_breadth": (
                "Market breadth shows if price moves are supported by many stocks (healthy) "
                "or just a few large caps (potentially weak). When breadth is strong, rallies "
                "tend to be more sustainable."
            ),
            "ticker_performance": (
                "Price change tells you what happened, but volume and indicators show you "
                "the 'strength' behind the move. High volume = more conviction from traders."
            ),
            "index_heatmap": (
                "Major indices (S&P 500, Nasdaq, Dow) often move together, but differences "
                "can reveal rotation between sectors. Tech-heavy Nasdaq up more = growth outperforming."
            ),
        }

        return tips.get(card_id)

    async def _fetch_one(self, query: str, params: dict) -> Optional[asyncpg.Record]:
        """
        Fetch single row from database.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Database record or None if not found
        """
        async with self.db_pool.acquire() as conn:
            return await conn.fetchrow(query, *params.values())

    async def _fetch_all(self, query: str, params: dict) -> list[asyncpg.Record]:
        """
        Fetch multiple rows from database.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            List of database records
        """
        async with self.db_pool.acquire() as conn:
            return await conn.fetch(query, *params.values())
