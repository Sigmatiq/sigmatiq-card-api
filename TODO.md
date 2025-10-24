# TODO — Sigmatiq Card API (Trader-Facing Enhancements)

This checklist captures upgrades to make cards more actionable for users and tighten implementation details.

## Action Blocks (Insight → Trade Plan)
- [ ] Add `action_block` to card responses with:
  - [ ] Entry context and trigger (e.g., pullback to MA20 with RSI>50)
  - [ ] Invalidation level (e.g., swing low − 1×ATR)
  - [ ] Risk unit (ATR% stop distance) and sizing hint
  - [ ] Targets (near = prior high, stretch = +R multiples)
  - [ ] Confidence score from confluence (trend + momentum + breadth + liquidity)
  - [ ] Post-check guidance (e.g., 10–30m volume pace ≥ 1.2×)
- [ ] Implement first in:
  - [ ] `market_breadth`
  - [ ] `index_heatmap`
  - [ ] `ticker_performance`
  - [ ] (next) `ticker_momentum`, `unusual_options`

## Beginner-First UX
- [ ] Expand `education` fields per card with “how it helps” and “what to avoid”
- [ ] Add a short pre-trade checklist: trend alignment (D/W), RSI zone, breadth not weak, no imminent earnings

## Multi‑Timeframe + Liquidity
- [ ] Add higher-timeframe alignment flags (Daily + Weekly trend) to ticker cards
- [ ] Add tradability metrics: median dollar volume, spread tier; warn on illiquid

## Options / Events Awareness
- [ ] In options cards, show earnings proximity and caution on short vol near events
- [ ] Calibrate IV/skew signals by outcomes; prefer defined-risk suggestions for beginners

## Data/Queries (Correctness & Robustness)
- [ ] Fix `index_heatmap` advanced mode: query should include `trading_date` since formatter references it
  - File: `sigmatiq_card_api/handlers/index_heatmap.py` — add `trading_date` to SELECT
- [ ] Consider symbol-aware fallback: on ticker cards, if chosen trading_date lacks data for symbol, fall back to latest for that symbol (bounded window)
- [ ] Keep parameter binding explicit: ensure parameter order matches `$1,$2` (current dict insertion order works; consider tuples for clarity)
- [ ] Confirm `preset_id = 'all_active'` exists in `sb.market_breadth_daily` (adjust if necessary)

## Text/Encoding Cleanups
- [ ] Replace corrupted emojis/strings in handlers:
  - [ ] `ticker_performance.py` (price emoji/labels)
  - [ ] `ticker_momentum.py` (beginner emoji map)
  - [ ] `unusual_options.py` (IV labels and expected move text)
- [ ] Normalize README encoding and remove stray characters in diagrams

## Logging & Secrets
- [ ] Mask DB credentials in startup logs (log host/db only)

## Validation & CI
- [ ] Add basic tests (health, key card endpoints) with test fixtures
- [ ] Add CI workflow (ruff/black check, pytest)

## Outcomes & Calibration (Later)
- [ ] Extend `cd.cards_usage_log` to store forward returns/stop-hit/target-hit for calibration
- [ ] Use outcomes to refine thresholds (e.g., momentum score bands, breadth cutoffs)

---

Notes
- Migrations live in `sigmatiq-database`; this API depends on:
  - `sb.market_breadth_daily`, `sb.symbol_derived_eod`, `sb.symbol_indicators_daily`, `sb.options_agg_eod`
  - `cd.cards_catalog`, `cd.cards_usage_log`
- Compliance: keep “live” features derived-only; do not expose raw Polygon feeds.
