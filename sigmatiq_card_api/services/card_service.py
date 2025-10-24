"""
Card service - Main orchestration layer for card requests.

Handles:
1. Card validation (check card exists in registry)
2. Trading date resolution with fallback logic
3. Handler selection and data fetching
4. Usage logging
5. Response formatting
6. Caching (3-level: Memory L1, Redis L2, Postgres L3)

Uses dual database connections:
- cards_pool: For cd.cards_catalog queries
- backfill_pool: For sb.* market data queries
"""

import asyncio
import time
from datetime import date, datetime, timedelta
from typing import Any, Optional

import asyncpg
from fastapi import HTTPException
from sigmatiq_shared.cache import get_kv_cache, simple_key

from ..handlers.base import BaseCardHandler
from ..models.cards import CardCatalogEntry, CardCategory, CardEducation, CardMeta, CardMode, CardResponse
from .usage_tracking import UsageTrackingService


class CardService:
    """Service for orchestrating card data requests with 3-level caching."""

    # Cache configuration
    CACHE_NAMESPACE = "cards:eod"
    CACHE_TTL_SECONDS = 86400  # 24 hours for EOD data (doesn't change)
    CACHE_SWR_SECONDS = 120  # 2 minutes stale-while-revalidate

    def __init__(self, cards_pool: asyncpg.Pool, backfill_pool: asyncpg.Pool):
        """
        Initialize card service.

        Args:
            cards_pool: Database pool for sigmatiq_cards (cd.* schema)
            backfill_pool: Database pool for sigmatiq_backfill (sb.* schema)
        """
        self.cards_pool = cards_pool
        self.backfill_pool = backfill_pool
        self.usage_tracking = UsageTrackingService(cards_pool)
        self._handlers: dict[str, BaseCardHandler] = {}
        self.cache = get_kv_cache()

    def register_handler(self, card_id: str, handler: BaseCardHandler):
        """
        Register a card handler.

        Args:
            card_id: Card identifier
            handler: Handler instance
        """
        self._handlers[card_id] = handler

    async def get_card_metadata(self, card_id: str) -> CardCatalogEntry:
        """
        Get card metadata from catalog.

        Args:
            card_id: Card identifier

        Returns:
            Card catalog entry

        Raises:
            HTTPException: If card not found or inactive
        """
        query = """
            SELECT card_id, title, description, category, requires_symbol,
                   minimum_tier, is_active, created_at, updated_at,
                   short_description, long_description, when_to_use,
                   how_to_interpret, use_case_example, educational_tip,
                   skill_levels, tags
            FROM cd.cards_catalog
            WHERE card_id = $1
        """

        async with self.cards_pool.acquire() as conn:
            row = await conn.fetchrow(query, card_id)

        if not row:
            raise HTTPException(status_code=404, detail=f"Card '{card_id}' not found")

        card_meta = CardCatalogEntry(**dict(row))

        if not card_meta.is_active:
            raise HTTPException(
                status_code=403, detail=f"Card '{card_id}' is currently disabled"
            )

        return card_meta

    async def resolve_trading_date(
        self, target_date: Optional[date] = None
    ) -> tuple[date, bool]:
        """
        Resolve trading date with fallback logic.

        If target_date is not provided or is a weekend/holiday, fall back to
        the most recent trading day within the last 5 days.

        Args:
            target_date: Requested date (None = today)

        Returns:
            Tuple of (actual_date, fallback_applied)

        Raises:
            HTTPException: If no data found within 5-day window
        """
        if target_date is None:
            target_date = date.today()

        # Try to find data for the target date or up to 5 days prior
        for days_back in range(6):
            check_date = target_date - timedelta(days=days_back)

            # Check if data exists for this date (use market_breadth_daily as proxy)
            query = """
                SELECT trading_date
                FROM sb.market_breadth_daily
                WHERE trading_date = $1
                LIMIT 1
            """

            async with self.backfill_pool.acquire() as conn:
                row = await conn.fetchrow(query, check_date)

            if row:
                fallback_applied = days_back > 0
                return check_date, fallback_applied

        # No data found within 5-day window
        raise HTTPException(
            status_code=404,
            detail=f"No market data available for {target_date} or previous 5 days",
        )

    async def get_card_data(
        self,
        card_id: str,
        mode: CardMode,
        symbol: Optional[str],
        date_param: Optional[date],
        user_id: str,
    ) -> CardResponse:
        """
        Get card data - main entry point.

        Args:
            card_id: Card identifier
            mode: Complexity level
            symbol: Stock symbol (optional, depends on card)
            date_param: Requested date (optional, defaults to today)
            user_id: User identifier (for analytics)

        Returns:
            CardResponse with data and metadata

        Raises:
            HTTPException: If card not found, data unavailable, or other errors
        """
        start_time = time.time()

        try:
            # 1. Validate card exists and is active
            card_meta = await self.get_card_metadata(card_id)

            # 2. Validate symbol if required
            if card_meta.requires_symbol and not symbol:
                raise HTTPException(
                    status_code=400, detail=f"Card '{card_id}' requires a symbol parameter"
                )

            # 3. Resolve trading date with fallback
            # If symbol provided (ticker cards), attempt symbol-aware fallback first
            if symbol:
                resolved = await self._resolve_trading_date_for_symbol(symbol, date_param)
                if resolved is not None:
                    actual_date, fallback_applied = resolved
                else:
                    actual_date, fallback_applied = await self.resolve_trading_date(date_param)
            else:
                actual_date, fallback_applied = await self.resolve_trading_date(date_param)

            # 4. Get handler
            if card_id not in self._handlers:
                raise HTTPException(
                    status_code=500, detail=f"Handler not registered for card '{card_id}'"
                )

            handler = self._handlers[card_id]

            # 5. Fetch data from handler with caching
            # Build cache key: card_id|mode|symbol|date
            cache_key = simple_key(card_id, mode.value, symbol or "", actual_date.isoformat())

            # Try to get from cache first
            cached = await asyncio.get_event_loop().run_in_executor(
                None, self.cache.get, self.CACHE_NAMESPACE, cache_key, self.CACHE_TTL_SECONDS
            )

            if cached is not None:
                # Cache hit
                card_data = cached
            else:
                # Cache miss - fetch from handler
                card_data = await handler.fetch(mode=mode, symbol=symbol, trading_date=actual_date)

                # Store in cache for future requests
                await asyncio.get_event_loop().run_in_executor(
                    None, self.cache.set, self.CACHE_NAMESPACE, cache_key, card_data, self.CACHE_TTL_SECONDS
                )

            # Remove cache metadata from card_data before building response
            card_data_clean = {k: v for k, v in card_data.items() if k != "_cache_metadata"}

            # 6. Build response
            # Build education object if fields are available
            education = None
            if card_meta.short_description or card_meta.long_description:
                education = CardEducation(
                    short_description=card_meta.short_description,
                    long_description=card_meta.long_description,
                    when_to_use=card_meta.when_to_use,
                    how_to_interpret=card_meta.how_to_interpret,
                    use_case_example=card_meta.use_case_example,
                    educational_tip=card_meta.educational_tip,
                )

            meta = CardMeta(
                card_id=card_id,
                mode=mode,
                title=card_meta.title,
                category=CardCategory(card_meta.category),
                symbol=symbol,
                trading_date=actual_date,
                requested_date=date_param,
                fallback_applied=fallback_applied,
                data_source="postgresql",
                timestamp=datetime.utcnow(),
                education=education,
                skill_levels=card_meta.skill_levels or ["beginner"],
                tags=card_meta.tags or [],
            )

            response = CardResponse(card_id=card_id, mode=mode, data=card_data_clean, meta=meta)

            # 7. Log usage (fire-and-forget, non-blocking)
            response_time_ms = int((time.time() - start_time) * 1000)
            self.usage_tracking.log_card_request_background(
                user_id=user_id,
                card_id=card_id,
                mode=mode,
                symbol=symbol,
                date_param=date_param,
                actual_date=actual_date,
                response_status=200,
                response_time_ms=response_time_ms,
            )

            return response

        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise

        except Exception as e:
            # Log unexpected errors
            response_time_ms = int((time.time() - start_time) * 1000)
            self.usage_tracking.log_card_request_background(
                user_id=user_id,
                card_id=card_id,
                mode=mode,
                symbol=symbol,
                date_param=date_param,
                actual_date=date.today(),
                response_status=500,
                response_time_ms=response_time_ms,
            )

            raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

    async def _resolve_trading_date_for_symbol(
        self, symbol: str, target_date: Optional[date]
    ) -> Optional[tuple[date, bool]]:
        """Resolve trading date using symbol's latest available EOD within a 10-day window.

        Tries to find most recent row for the symbol on or before target date in
        sb.symbol_derived_eod. Returns (date, fallback_applied) or None if not found.
        """
        if target_date is None:
            target_date = date.today()

        query = """
            SELECT trading_date
            FROM sb.symbol_derived_eod
            WHERE symbol = $1 AND trading_date <= $2 AND trading_date >= ($2 - INTERVAL '10 days')
            ORDER BY trading_date DESC
            LIMIT 1
        """
        async with self.backfill_pool.acquire() as conn:
            row = await conn.fetchrow(query, (symbol or '').upper(), target_date)
        if row and row.get("trading_date"):
            d = row["trading_date"]
            return d, d != target_date
        return None
