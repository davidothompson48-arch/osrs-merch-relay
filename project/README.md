# OSRS Merch Desk Project Memory

This directory is the persistent memory layer for the user's Old School RuneScape GE trading desk.

## Canonical files

- `OPERATING_SPEC.md` — normalized desk rules and report requirements from the master prompt.
- `project_state.json` — manifest/fingerprint of the project, generated files, collectors and automation state.
- `portfolio_ledger.json` — current known holdings, quantities, cost bases, unresolved positions and historical offers. Update whenever the user reports a buy/sell/fill/target.
- `data_gap_register.json` — unresolved portfolio/research facts that must not be guessed.
- `trade_journal.csv` — confirmed and evidence-backed executions.
- `scanner_feedback.json` — scanner recommendations/outcomes and execution lessons; only user-confirmed executions count empirically.
- `thesis_watchlist.json` — ongoing investment theses, failure modes and stale historical research bands. Historical price bands are never executable without fresh Wiki/RuneLite validation.
- `catalysts_verified.md` — official catalyst facts and verification status, separated from community speculation.
- `news_baseline.json` — known-news baseline that prevents old Jagex/community developments from being relabeled NEW every hour.
- `source_registry.json` — approved market/official/community source registry and forbidden current-price substitutes.
- `known_conversions.json` — static processing/conversion/set relationships; market values are always recalculated from fresh Wiki/RuneLite data.
- `related_items.json` — related-sector universe used by `collect_related.py`.

## Live generated files

- `snapshot.json` — fresh core portfolio + full-market scanner snapshot. All market fields originate only from `prices.runescape.wiki`.
- `related_watch.json` — fresh related-sector comparison tape, also only from `prices.runescape.wiki`.
- `market_universe/index.json` — fresh index for the complete Wiki-mapped tradeable/static item universe.
- `market_universe/A.json` ... `Z.json` plus `0-9/OTHER` as present — readable full-market shards containing item IDs, names, buy limits/static metadata, current HIGH/LOW/timestamps and 5m/1h/24h Wiki/RuneLite data. The current universe contains thousands of mapped items and refreshes hourly.
- `history/market_history.jsonl` — rolling compact history for portfolio/scanner/related-sector comparisons, retaining roughly 120 days at hourly cadence.
- `history/recent_history.json` — compact recent history intended for fast multi-snapshot change detection.

## Collection code

- `collect.py` — core portfolio plus broad-market scanner.
- `collect_related.py` — fixed related-sector universe and competing-thesis tape.
- `collect_universe.py` — complete Wiki item universe split into readable shards.
- `archive_snapshot.py` — rolling history and recent-history views.
- `.github/workflows/update-snapshot.yml` — runs all collectors/archive hourly and on supported test triggers.

## Source hierarchy

1. Current GE market data: ONLY `prices.runescape.wiki` / RuneLite-fed API, delivered directly or through this repository's relay files.
2. Official catalyst facts: Jagex/Old School official site, polls, updates and official social.
3. Community intelligence: Reddit/other OSRS community sources, always labeled as speculation unless independently confirmed.
4. User portfolio facts: newest explicit user statement wins. Offers do not count as fills unless confirmed.

## Data-quality principles

- Never silently fill a missing portfolio quantity, cash amount or cost basis; record it in `data_gap_register.json`.
- Never treat an offer as an executed trade without user confirmation.
- Never use historical research price bands as current market values.
- Never promote a Jagex proposal to a passed/implemented reward unless the relevant official result is verified.
- Use completed trades as scanner feedback, not as proof that the same trade remains valid later.
- Use `market_universe` to investigate arbitrary existing items referenced by new content without falling back to another market-data source.

## Non-negotiable rule

No third-party market-price substitute is allowed. If fresh RuneLite/Wiki market data is unavailable, report `LIVE RUNELITE DATA UNAVAILABLE` rather than guessing.
