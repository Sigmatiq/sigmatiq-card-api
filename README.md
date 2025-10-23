# Sigmatiq Card API

Market data cards API providing both EOD (end-of-day) and Live (real-time) formatted data.

## Overview

The Card API provides pre-formatted, beginner-friendly market data cards for UI integration. It offers:

- **EOD Cards** (`/api/v1/cards/*`) - Historical end-of-day data from PostgreSQL
- **Live Cards** (`/api/v1/live/cards/*`) - Real-time data from Polygon API (Phase 2)
- **Data Endpoints** (`/api/v1/data/*`) - Raw database access (Phase 3)
- **Live Data** (`/api/v1/live/data/*`) - Raw real-time data (Phase 4)

## Quick Start

```bash
# Install dependencies
pip install -e .

# Set up environment
cp .env.example .env
# Edit .env with your database credentials

# Run the API
python -m uvicorn sigmatiq_card_api.app:app --host 0.0.0.0 --port 8006 --reload
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8006/docs
- ReDoc: http://localhost:8006/redoc

## Example Usage

```bash
# Get market breadth card (beginner mode)
curl -H "X-User-Id: test" \
  "http://localhost:8006/api/v1/cards/market_breadth?mode=beginner"

# Get ticker performance (intermediate mode)
curl -H "X-User-Id: test" \
  "http://localhost:8006/api/v1/cards/ticker_performance?symbol=AAPL&mode=intermediate"

# Get index heatmap
curl -H "X-User-Id: test" \
  "http://localhost:8006/api/v1/cards/index_heatmap?mode=beginner"
```

## Card Modes

- **beginner**: Plain language, educational tips, simplified metrics
- **intermediate**: More technical terms, additional indicators
- **advanced**: Full technical detail, all available metrics

## Architecture

```
sigmatiq_card_api/
├── app.py                     # FastAPI application
├── routes/
│   └── cards.py               # Card endpoints
├── services/
│   ├── card_service.py        # Orchestration layer
│   └── usage_tracking.py      # Analytics logging
├── handlers/
│   ├── base.py                # Base handler class
│   ├── market_breadth.py      # Market breadth card
│   ├── ticker_performance.py  # Ticker performance card
│   └── index_heatmap.py       # Index heatmap card
├── models/
│   └── cards.py               # Pydantic models
└── migrations/
    └── 0001_cards_tables.sql  # Database schema
```

## Database Schema

Two main tables:

- `sb.cards_catalog` - Card registry (metadata, feature flags)
- `sb.cards_usage_log` - Usage analytics (non-blocking async logging)

## Future Monetization

The architecture is designed to extend easily for monetization:
- Tier limits (already in schema, not enforced yet)
- API keys (can be added later)
- Rate limiting (Redis-based when needed)
- Billing events (Stripe integration when needed)

## Phase Roadmap

- ✅ **Phase 1** (TODAY): EOD Cards - 3 cards implemented
- **Phase 2** (Week 2): Live Cards - Real-time data via Polygon
- **Phase 3** (Week 2): EOD Data - Raw database endpoints
- **Phase 4** (Week 3): Live Data - Raw real-time endpoints

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black sigmatiq_card_api/

# Lint
ruff check sigmatiq_card_api/
```

## License

Proprietary - Sigmatiq Platform
