"""
Configuration management for Card API.

Loads settings from environment variables and provides dual database connections:
- Cards DB (sigmatiq_cards): For catalog and usage tracking (cd.* schema)
- Backfill DB (sigmatiq_backfill): For market data (sb.* schema)
"""

import os
from functools import lru_cache
from typing import Optional

import asyncpg
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Databases (dual connection)
    cards_database_url: str = "postgresql://postgres:password@localhost:5432/sigmatiq_cards"
    backfill_database_url: str = "postgresql://postgres:password@localhost:5432/sigmatiq_backfill"

    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8006
    log_level: str = "INFO"

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:5173"

    # Cache Configuration (3-level: Memory L1, Redis L2, Postgres L3)
    sigma_kv_pg_url: Optional[str] = None
    sigma_kv_enable_mem: bool = True
    use_redis_cache: bool = False
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_url: Optional[str] = None

    # Future: Polygon API (Phase 2)
    polygon_api_key: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global database connection pools
_cards_pool: Optional[asyncpg.Pool] = None
_backfill_pool: Optional[asyncpg.Pool] = None


async def get_cards_pool() -> asyncpg.Pool:
    """
    Get or create cards database connection pool.

    Used for: cd.cards_catalog, cd.cards_usage_log

    Returns:
        asyncpg.Pool: Connection pool for sigmatiq_cards database
    """
    global _cards_pool

    if _cards_pool is None:
        settings = get_settings()
        _cards_pool = await asyncpg.create_pool(
            settings.cards_database_url,
            min_size=2,
            max_size=10,
            command_timeout=60,
        )

    return _cards_pool


async def get_backfill_pool() -> asyncpg.Pool:
    """
    Get or create backfill database connection pool.

    Used for: sb.market_breadth_daily, sb.symbol_derived_eod, sb.* tables

    Returns:
        asyncpg.Pool: Connection pool for sigmatiq_backfill database
    """
    global _backfill_pool

    if _backfill_pool is None:
        settings = get_settings()
        _backfill_pool = await asyncpg.create_pool(
            settings.backfill_database_url,
            min_size=2,
            max_size=10,
            command_timeout=60,
        )

    return _backfill_pool


async def close_db_pools():
    """Close all database connection pools."""
    global _cards_pool, _backfill_pool

    if _cards_pool is not None:
        await _cards_pool.close()
        _cards_pool = None

    if _backfill_pool is not None:
        await _backfill_pool.close()
        _backfill_pool = None
