# OSRS Merch Desk Project Memory

This directory is the persistent memory layer for the user's Old School RuneScape GE trading desk.

## Canonical files

- `OPERATING_SPEC.md` — normalized desk rules and report requirements.
- `portfolio_ledger.json` — current known holdings, quantities, cost bases, unresolved positions and historical offers. Update whenever the user reports a buy/sell/fill/target.
- `trade_journal.csv` — confirmed and evidence-backed executions used to improve scanner selection.
- `thesis_watchlist.json` — ongoing investment theses, failure modes and stale historical research bands. Historical price bands are never executable without fresh Wiki/RuneLite validation.
- `catalysts_verified.md` — official catalyst facts and verification status, separated from community speculation.
- `related_items.json` — related-sector universe used by `collect_related.py`.

## Live generated files at repository root

- `snapshot.json` — fresh core portfolio + full-market scanner snapshot. All market fields originate only from `prices.runescape.wiki`.
- `related_watch.json` — fresh related-sector comparison tape, also only from `prices.runescape.wiki`.
- `history/market_history.jsonl` — rolling compact history for portfolio/scanner/related-sector comparisons.

## Source hierarchy

1. Current GE market data: ONLY `prices.runescape.wiki` / RuneLite-fed API, delivered directly or through this repository's relay files.
2. Official catalyst facts: Jagex/Old School official site, polls, updates and official social.
3. Community intelligence: Reddit/other OSRS community sources, always labeled as speculation unless independently confirmed.
4. User portfolio facts: newest explicit user statement wins. Offers do not count as fills unless confirmed.

## Non-negotiable rule

No third-party market-price substitute is allowed. If fresh RuneLite/Wiki market data is unavailable, report `LIVE RUNELITE DATA UNAVAILABLE` rather than guessing.
