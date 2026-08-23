# Architecture

## Design principles

1. Keep the live RuneLite/Wiki relay isolated from customer-specific state.
2. Never expose private user portfolio data in a public repository or shared cache.
3. Treat the price relay as market-data transport, not as the recommendation engine.
4. Keep recommendations reproducible from market state + user state + catalyst state.
5. Make data freshness visible everywhere.

## Recommended stack

### Web application

- Next.js + TypeScript.
- Tailwind CSS or equivalent utility styling.
- Deploy on Vercel or Cloudflare.

### Authentication / database

- Supabase Postgres + Auth for MVP, or Clerk + managed Postgres if preferred later.
- Row-level security on all customer portfolio and alert tables.

### Billing

- Stripe subscriptions.
- Webhook-driven entitlements.
- Tiers: Scout, Pro, Private Desk.

### Market data

- Existing `osrs-merch-relay` remains the cache/transport layer.
- All live market data continues to originate from prices.runescape.wiki/RuneLite.
- Production pipeline must send a descriptive User-Agent and follow Wiki acceptable-use guidance.
- Cache aggressively; do not make per-user duplicate requests to the upstream API.

### Intelligence engine

Separate service/job responsible for:

- Portfolio marking.
- Timeframe comparisons.
- Liquidity grading.
- Conversion math.
- Opportunity candidate generation.
- Catalyst item mapping.
- Capital rotation comparisons.
- Recommendation payload generation.

AI can generate narrative interpretation from structured evidence, but core prices, math, timestamps, position quantities and rules should remain deterministic.

## Proposed data model

### users

- id
- email
- display_name
- tier
- created_at

### portfolios

- id
- user_id
- name
- optional_cash_gp
- updated_at

### positions

- id
- portfolio_id
- item_id
- item_name
- quantity
- avg_basis_gp
- thesis_id nullable
- intent: merch | hold_for_use | speculation
- opened_at
- notes

### market_snapshots

Shared, not user-specific.

- item_id
- generated_at
- current_high
- current_low
- high_time
- low_time
- avg_5m fields
- avg_1h fields
- avg_6h fields
- avg_24h fields
- trend_7d
- trend_30d
- flow metrics

### theses

- id
- user_id nullable for shared theses
- title
- description
- evidence_grade
- catalyst_confidence
- direction
- status
- invalidation
- updated_at

### trade_ideas

- id
- item_id
- trade_type
- entry_min
- entry_max
- ideal_entry
- do_not_chase
- target_1
- target_2
- invalidation
- estimated_roi_after_tax
- buy_limit
- suggested_capital_gp
- opportunity_score
- conviction
- liquidity
- thesis
- main_risk
- created_at
- expires_at

### catalysts

- id
- source_type
- source_url
- source_actor
- published_at
- discovered_at
- title
- summary
- evidence_grade
- status
- impact
- direction
- affected_item_ids

### alerts

- id
- user_id
- alert_type
- payload
- created_at
- read_at

## Recommendation payload

Every generated recommendation should be stored as structured JSON before narrative rendering:

```json
{
  "item_id": 21880,
  "item": "Wrath rune",
  "action": "HOLD",
  "market_state": "Selling pressure",
  "current_high": 349,
  "current_low": 340,
  "high_age_seconds": 45,
  "low_age_seconds": 42,
  "weekly_change_pct": -2.87,
  "liquidity": "VERY LIQUID",
  "opportunity_score": 58,
  "conviction": 2,
  "reason_codes": ["weekly_downtrend", "seller_flow", "near_basis"],
  "invalidation": "buyer-side stabilization and weekly reversal"
}
```

Narrative text is then generated from this evidence rather than invented independently.

## Security / privacy

- Do not request RuneScape credentials.
- Do not store Jagex session tokens.
- Do not store payment card data directly; Stripe handles payment data.
- Encrypt secrets in deployment environment variables.
- Use RLS / per-user authorization for portfolios and watchlists.
- Admin access should be audited.
- Backups should exclude unnecessary logs containing user-entered notes.

## MVP integrations

Phase 1:

- Existing relay.
- Supabase.
- Stripe.
- Email alerts.

Phase 2:

- Discord role entitlement / alert delivery.
- Optional push notifications.
- More robust JMod/social ingestion.

## API usage

The OSRS Wiki real-time pricing project explicitly invites community-facing tools and recommends that real-time pipelines coordinate through its API discussion channel. Production deployment should therefore identify the service with a descriptive User-Agent and avoid abusive polling. The existing relay is the correct place to centralize upstream requests rather than having every subscriber hit the Wiki API independently.