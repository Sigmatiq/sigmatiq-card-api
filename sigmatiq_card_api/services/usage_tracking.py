"""
Usage tracking service for analytics.

Logs card requests to database in fire-and-forget manner (non-blocking).
"""

import asyncio
import logging
from datetime import date
from typing import Optional

import asyncpg

from ..models.cards import CardMode

logger = logging.getLogger(__name__)


class UsageTrackingService:
    """Service for logging card usage analytics."""

    def __init__(self, db_pool: asyncpg.Pool):
        """
        Initialize usage tracking service.

        Args:
            db_pool: Database connection pool
        """
        self.db_pool = db_pool

    async def log_card_request(
        self,
        user_id: str,
        card_id: str,
        mode: CardMode,
        symbol: Optional[str],
        date_param: Optional[date],
        actual_date: date,
        response_status: int,
        response_time_ms: int,
        tier: str = "free",
        credits_charged: float = 1.0,
    ):
        """
        Log a card request to database (async, non-blocking).

        This method should be called with asyncio.create_task() to avoid blocking
        the response to the user.

        Args:
            user_id: User identifier
            card_id: Card identifier
            mode: Complexity level
            symbol: Stock symbol (optional)
            date_param: Requested date (optional)
            actual_date: Actual trading date used
            response_status: HTTP response status code
            response_time_ms: Response time in milliseconds
            tier: User tier (for future analysis)
            credits_charged: Credits consumed (for future billing)
        """
        try:
            query = """
                INSERT INTO cd.cards_usage_log (
                    user_id, card_id, mode, symbol, date_param, actual_date,
                    response_status, response_time_ms, tier, credits_charged
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """

            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    query,
                    user_id,
                    card_id,
                    mode.value,
                    symbol,
                    date_param,
                    actual_date,
                    response_status,
                    response_time_ms,
                    tier,
                    credits_charged,
                )

            logger.info(
                f"Logged usage: user={user_id} card={card_id} mode={mode.value} "
                f"status={response_status} time={response_time_ms}ms"
            )

        except Exception as e:
            # Log error but don't raise - we don't want analytics to break the API
            logger.error(f"Failed to log card usage: {e}", exc_info=True)

    def log_card_request_background(
        self,
        user_id: str,
        card_id: str,
        mode: CardMode,
        symbol: Optional[str],
        date_param: Optional[date],
        actual_date: date,
        response_status: int,
        response_time_ms: int,
        tier: str = "free",
        credits_charged: float = 1.0,
    ):
        """
        Log card request in background (fire-and-forget).

        This is a synchronous wrapper that creates an async task.

        Usage:
            usage_service.log_card_request_background(...)
        """
        asyncio.create_task(
            self.log_card_request(
                user_id=user_id,
                card_id=card_id,
                mode=mode,
                symbol=symbol,
                date_param=date_param,
                actual_date=actual_date,
                response_status=response_status,
                response_time_ms=response_time_ms,
                tier=tier,
                credits_charged=credits_charged,
            )
        )
