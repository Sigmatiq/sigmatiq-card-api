# Sigmatiq Cards - Gradual Rollout Strategy

## Current Status (2025-10-23)

### Cards Implemented: 21 of 34 (62%)

**Phase 1 (MVP) - 11 cards:** ✅ Deployed to Beta
- market_breadth
- index_heatmap
- market_regime
- sector_rotation
- technical_breadth
- ticker_performance
- ticker_52w
- ticker_trend
- volume_profile
- unusual_options
- options_flow

**Phase 2A - 3 cards:** ✅ Code Complete, Ready for Testing
- market_summary (composite health score)
- ticker_momentum (RSI/MACD/Stochastic)
- ticker_volatility (ATR/Bollinger Bands)

**Phase 2B - 7 cards:** ✅ Code Complete, Ready for Testing
- ticker_relative_strength (RS percentile rankings)
- ticker_liquidity (dollar volume, liquidity ranks)
- ticker_breakout (52-week breakouts with volume confirmation)
- ticker_reversal (overbought/oversold reversal signals)
- options_iv_skew (IV percentile, expected moves)
- options_gex (dealer gamma positioning)
- options_0dte (0DTE flow monitoring)

---

## Rollout Strategy

### Principle: Test in Local → Beta → Production

Each card rollout follows this pattern:
1. **Local Testing** - Verify handler works with production data
2. **Beta Testing** - Deploy to beta environment, test with users
3. **Production** - Deploy to production after beta validation

### Data Validation Required

Before enabling any card, verify:
- [ ] **Data exists** in production backfill database (`sigmatiq_backfill`)
- [ ] **Data is recent** (updated daily/weekly as expected)
- [ ] **Data is complete** (no major gaps or null values)
- [ ] **Data is accurate** (spot-check against known values)

---

## Phase 2A Rollout Plan

### Card 1: market_summary (Composite Health Score)

**Dependencies:**
- `sb.market_breadth_daily` (REQUIRED)
- `sb.symbol_indicators_daily` for SPY (REQUIRED)
- `sb.equity_bars_daily` for SPY (REQUIRED)

**Testing Steps:**
1. **Local Test:**
   ```bash
   curl -H "X-User-Id: test" "http://localhost:8007/api/v1/cards/market_summary?mode=beginner"
   curl -H "X-User-Id: test" "http://localhost:8007/api/v1/cards/market_summary?mode=intermediate"
   curl -H "X-User-Id: test" "http://localhost:8007/api/v1/cards/market_summary?mode=advanced"
   ```
2. **Verify Response:**
   - Check composite score (0-100)
   - Verify classification (Bullish/Neutral/Bearish)
   - Confirm component breakdown in intermediate/advanced modes
3. **Deploy to Beta:**
   - Set `is_active = true` in beta cards catalog
   - Test with real users
   - Monitor error logs
4. **Production:**
   - After 1 week beta validation, deploy to prod

**Risk Level:** LOW (uses existing stable data sources)

---

### Card 2: ticker_momentum (RSI/MACD/Stochastic)

**Dependencies:**
- `sb.symbol_indicators_daily` (REQUIRED)

**Testing Steps:**
1. **Local Test:**
   ```bash
   curl -H "X-User-Id: test" "http://localhost:8007/api/v1/cards/ticker_momentum?symbol=AAPL&mode=beginner"
   curl -H "X-User-Id: test" "http://localhost:8007/api/v1/cards/ticker_momentum?symbol=SPY&mode=intermediate"
   curl -H "X-User-Id: test" "http://localhost:8007/api/v1/cards/ticker_momentum?symbol=TSLA&mode=advanced"
   ```
2. **Verify Response:**
   - Check RSI values (0-100)
   - Verify MACD histogram
   - Confirm momentum classification
3. **Test Edge Cases:**
   - Symbol with no data → expect 404
   - Invalid symbol → expect 404
   - Weekend date → expect fallback to last trading day
4. **Deploy to Beta**
5. **Production**

**Risk Level:** LOW (uses existing indicator data)

---

### Card 3: ticker_volatility (ATR/Bollinger Bands)

**Dependencies:**
- `sb.symbol_indicators_daily` (REQUIRED)
- `sb.equity_bars_daily` (REQUIRED)

**Testing Steps:**
1. **Local Test:**
   ```bash
   curl -H "X-User-Id: test" "http://localhost:8007/api/v1/cards/ticker_volatility?symbol=AAPL&mode=beginner"
   curl -H "X-User-Id: test" "http://localhost:8007/api/v1/cards/ticker_volatility?symbol=SPY&mode=intermediate"
   ```
2. **Verify Response:**
   - Check ATR values
   - Verify Bollinger Band metrics
   - Confirm volatility classification
   - Validate position sizing guidance
3. **Deploy to Beta**
4. **Production**

**Risk Level:** LOW

---

## Phase 2B Rollout Plan

### Priority 1: High-Value, Low-Risk Cards

#### Card 1: ticker_relative_strength (RS Percentile)

**Dependencies:**
- `sb.symbol_cross_sectional_eod` (rs_pct_20, rs_pct_60, rs_pct_120) - **VERIFY EXISTS**
- `sb.symbol_fundamentals_cache` (sector) - OPTIONAL

**Pre-Deployment Validation:**
```sql
-- Check data availability
SELECT COUNT(*) FROM sb.symbol_cross_sectional_eod
WHERE trading_date >= CURRENT_DATE - INTERVAL '7 days';

-- Check RS data completeness
SELECT
  trading_date,
  COUNT(*) as total_symbols,
  SUM(CASE WHEN rs_pct_60 IS NOT NULL THEN 1 ELSE 0 END) as with_rs_data
FROM sb.symbol_cross_sectional_eod
WHERE trading_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY trading_date
ORDER BY trading_date DESC;
```

**Testing Steps:**
1. **Verify Data Exists:** Run validation queries above
2. **Local Test:**
   ```bash
   curl -H "X-User-Id: test" "http://localhost:8007/api/v1/cards/ticker_relative_strength?symbol=AAPL&mode=beginner"
   ```
3. **Test Multiple Symbols:** AAPL, SPY, TSLA, NVDA, MSFT
4. **Deploy to Beta** if data exists
5. **Hold in Local** if data missing (need to backfill cross-sectional data first)

**Risk Level:** MEDIUM (depends on cross-sectional data availability)

---

#### Card 2: ticker_liquidity (Dollar Volume)

**Dependencies:**
- `sb.symbol_cross_sectional_eod` (liq_dollar_rank_20, rvol_pctile_20) - **VERIFY EXISTS**
- `sb.symbol_derived_eod` (volume, rvol, close) - REQUIRED

**Pre-Deployment Validation:**
```sql
-- Check liquidity data availability
SELECT
  trading_date,
  COUNT(*) as total_symbols,
  SUM(CASE WHEN liq_dollar_rank_20 IS NOT NULL THEN 1 ELSE 0 END) as with_liq_data
FROM sb.symbol_cross_sectional_eod
WHERE trading_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY trading_date
ORDER BY trading_date DESC;
```

**Testing Steps:**
1. **Verify Data Exists**
2. **Local Test**
3. **Deploy to Beta** if data exists

**Risk Level:** MEDIUM (depends on cross-sectional data)

---

### Priority 2: Advanced Cards (Require More Validation)

#### Card 3: ticker_breakout (52-Week Breakouts)

**Dependencies:**
- `sb.symbol_derived_eod` (is_breakout_52w, r_20d_pct, rvol) - **VERIFY EXISTS**
- `sb.symbol_52w_levels` (high_52w, high_52w_date) - **VERIFY EXISTS**
- `sb.symbol_cross_sectional_eod` (rs_pct_60) - OPTIONAL

**Pre-Deployment Validation:**
```sql
-- Check 52w data availability
SELECT COUNT(*) FROM sb.symbol_52w_levels
WHERE trading_date >= CURRENT_DATE - INTERVAL '7 days';

-- Check breakout flags
SELECT
  trading_date,
  SUM(CASE WHEN is_breakout_52w THEN 1 ELSE 0 END) as breakout_count
FROM sb.symbol_derived_eod
WHERE trading_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY trading_date
ORDER BY trading_date DESC;
```

**Risk Level:** MEDIUM (depends on derived fields)

---

#### Card 4: ticker_reversal (Overbought/Oversold)

**Dependencies:**
- `sb.symbol_derived_eod` (is_overbought, is_oversold, close_position_in_range, dist_to_ma20_pct, zscore_20) - **VERIFY EXISTS**
- `sb.symbol_indicators_daily` (rsi_14, stoch_k, stoch_d) - REQUIRED

**Risk Level:** LOW-MEDIUM

---

### Priority 3: Options Cards (Advanced Users Only)

#### Card 5: options_iv_skew (IV Percentile)

**Dependencies:**
- `sb.options_agg_eod` (iv30, iv_rank, iv_percentile, skew, expected_move_1d, expected_move_1w) - **VERIFY EXISTS**

**Pre-Deployment Validation:**
```sql
-- Check options aggregate data
SELECT
  as_of,
  COUNT(*) as symbols_with_options
FROM sb.options_agg_eod
WHERE as_of >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY as_of
ORDER BY as_of DESC;

-- Check data completeness
SELECT
  as_of,
  symbol,
  iv30,
  iv_percentile,
  expected_move_1w
FROM sb.options_agg_eod
WHERE symbol IN ('AAPL', 'SPY', 'TSLA')
  AND as_of >= CURRENT_DATE - INTERVAL '3 days'
ORDER BY as_of DESC, symbol;
```

**Risk Level:** HIGH (options data may not exist yet)

---

#### Card 6: options_gex (Dealer Gamma)

**Dependencies:**
- `sb.options_agg_eod` (dealer_net_delta, zero_gamma_level, gex) - **VERIFY EXISTS**
- `sb.symbol_derived_eod` (close) - REQUIRED

**Risk Level:** HIGH (GEX data may not exist)

---

#### Card 7: options_0dte (0DTE Flow)

**Dependencies:**
- `sb.options_agg_eod` (odte_total_oi, odte_flow_imbalance) - **VERIFY EXISTS**

**Risk Level:** HIGH (0DTE data may not exist)

---

## Enablement Control Strategy

### Option 1: Database-Driven (Recommended)

Use the `is_active` flag in `cd.cards_catalog`:

```sql
-- Enable a card
UPDATE cd.cards_catalog SET is_active = true WHERE card_id = 'market_summary';

-- Disable a card
UPDATE cd.cards_catalog SET is_active = false WHERE card_id = 'options_gex';

-- Check currently active cards
SELECT card_id, title, category, is_active FROM cd.cards_catalog
WHERE is_active = true
ORDER BY category, card_id;
```

**Pros:**
- No code changes needed
- Can enable/disable instantly
- Different settings for dev/beta/prod databases
- Easy rollback

**Cons:**
- None

---

### Option 2: Environment Variable (Backup)

Add environment variable for feature flags:

```python
# In config.py
ENABLED_CARDS = os.getenv("ENABLED_CARDS", "").split(",")

# In service
if card_id not in ENABLED_CARDS and not card_meta.is_active:
    raise HTTPException(403, "Card not available")
```

**Pros:**
- Can override database setting
- Useful for emergency disablement

**Cons:**
- Requires deployment to change
- More complex

---

## Recommended Rollout Timeline

### Week 1: Phase 2A (3 cards)
- **Day 1:** Test locally all Phase 2A cards
- **Day 2:** Deploy to beta (all 3 cards enabled)
- **Day 3-7:** Monitor beta, collect feedback

### Week 2: Phase 2B Priority 1 (2 cards)
- **Day 1:** Validate data availability for RS and Liquidity
- **Day 2:** Local testing
- **Day 3:** Deploy to beta if data exists
- **Day 4-7:** Monitor

### Week 3: Phase 2B Priority 2 (2 cards)
- Breakout, Reversal cards
- Same pattern

### Week 4: Phase 2B Priority 3 (3 options cards)
- **ONLY IF** options aggregate data exists in `sb.options_agg_eod`
- Otherwise, hold until data pipeline ready

---

## Monitoring & Rollback

### Metrics to Monitor

1. **Error Rate:**
   - Track 404s (no data)
   - Track 500s (handler errors)

2. **Response Times:**
   - Target: <500ms p95
   - Alert if >1s p95

3. **Data Freshness:**
   - Alert if data is >2 days old

### Rollback Process

If errors >5% for any card:

```sql
-- Immediate rollback
UPDATE cd.cards_catalog SET is_active = false WHERE card_id = 'problematic_card';
```

Then investigate and fix before re-enabling.

---

## Testing Checklist (Per Card)

Before enabling any card:

- [ ] Data exists in production database
- [ ] Local test passes for beginner mode
- [ ] Local test passes for intermediate mode
- [ ] Local test passes for advanced mode
- [ ] Test with multiple symbols (if ticker card)
- [ ] Test with date parameter (past date)
- [ ] Test error handling (invalid symbol, missing data)
- [ ] Verify educational content displays correctly
- [ ] Check response time (<500ms)
- [ ] Spot-check accuracy of calculated values

---

## Summary

**Immediate Action Items:**

1. **Run data validation queries** for all Phase 2B cards
2. **Test Phase 2A cards** locally (already have data)
3. **Enable Phase 2A** in beta this week
4. **Plan Phase 2B rollout** based on data availability findings

**Key Decision:**
- Phase 2B rollout depends on `sb.symbol_cross_sectional_eod` data availability
- If cross-sectional data doesn't exist, need to backfill before enabling RS/Liquidity/Breakout cards
- Options cards depend on `sb.options_agg_eod` data pipeline

**Next Steps:**
1. Verify what data exists in production `sigmatiq_backfill` database
2. Enable Phase 2A cards immediately (low risk)
3. Create data backfill plan for missing Phase 2B dependencies
