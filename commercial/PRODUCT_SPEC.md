# Product Specification

## Core promise

**Know where to deploy GP before the market fully reacts.**

Every surface should answer one of four questions:

1. Where should fresh GP go?
2. Which current positions deserve more or less capital?
3. What changed in the market or catalyst environment?
4. What should I do now, at what price, and what invalidates the trade?

## Target customer

Primary customer: serious OSRS merchants and players with roughly 1b+ banks.

Best-fit customer characteristics:

- Holds multiple speculative positions.
- Cares about opportunity cost, not just nominal profit.
- Trades around updates, polls, raids, balance changes and supply shocks.
- Wants decision support rather than raw charts.
- Has enough GP that avoiding one bad allocation can justify the subscription.

## Tier design

### Scout — $29/month

- Shared hourly OSRS Merch Desk.
- Best use of fresh GP ranking.
- Up to 3 validated fast flips.
- Up to 3 swing/catalyst ideas.
- Conversion/arbitrage monitor.
- Official/JMod/social catalyst feed.
- What We Know / What We Think / What The Market Is Doing framework.
- No personalized portfolio calls.

### Pro — $79/month

Everything in Scout plus:

- Personal portfolio ledger.
- Cost basis and unrealized P/L.
- After-tax exit estimates.
- Position concentration.
- 5m / 1h / 6h / 24h / 7d context where supported.
- HOLD / ADD / TRIM / EXIT recommendations.
- Custom watchlist.
- Portfolio-specific catalyst impact.
- Capital rotation alerts.
- Entry/target/invalidation tracking.

### Private Desk — $249/month

Everything in Pro plus:

- Large-bank portfolio review.
- Custom thesis tracking.
- Priority catalyst research.
- Large-capital deployment plans.
- Liquidity-aware sizing for whale positions.
- Periodic manual review of concentration and stale theses.
- Limited seats.

The Private Desk does not take custody of GP, execute trades, log into accounts or share in profits.

## Dashboard information architecture

### Home / Command Center

Top row:

- Portfolio gross value.
- Recorded basis.
- Estimated after-tax P/L.
- Cash entered by user, if supplied.
- Largest concentration.
- Current risk score.

Primary card:

**BEST USE OF FRESH GP RIGHT NOW**

Shows ranked options such as Cash, conversion, fast flip, swing, or add-to-position.

Secondary cards:

- Top portfolio alert.
- Best validated trade.
- Biggest thesis risk.
- Latest catalyst.

### Portfolio

Each position shows:

- Item.
- Quantity.
- Basis.
- Current high/low and age.
- Current value.
- Gross and after-tax P/L.
- 1h / 24h / 7d movement.
- Liquidity.
- Concentration percentage.
- Thesis status.
- HOLD / ADD / TRIM / EXIT.
- Action price levels.

### Opportunities

Tabs:

- Fast Flips.
- Swing.
- Catalyst.
- Conversions.
- Watchlist.

Every actual trade card must include:

- Current HIGH / LOW and transaction ages.
- Entry zone.
- Ideal entry.
- Do-not-chase level.
- Targets.
- Invalidation.
- Expected after-tax ROI.
- Buy limit.
- Suggested capital.
- Expected profit per GE limit.
- Hold time.
- Liquidity.
- Opportunity Score.
- Conviction.
- Thesis.
- Main trap.

### Catalysts

Feed categories:

- Official Jagex.
- JMod comments.
- Polls/results.
- Game updates/hotfixes.
- Reddit/community intelligence.
- Market reaction.

Each catalyst receives:

- Status: NEW / DEVELOPING / CONFIRMED / WEAKENING / DISPROVEN / UNCHANGED.
- Evidence grade.
- Direction.
- Impact.
- Affected items.
- Whether the market appears to have priced it.

### Watchlists

Users can create named theses such as:

- Raid 4 elemental magic.
- Crush / Inquisitor.
- CoX prayer scroll rebound.
- Rune sink speculation.

Watchlists show correlated assets and relative performance, not isolated price charts.

## Alert philosophy

Do not notify for noise.

Alert only when one of these changes:

- Execution price crosses a meaningful level.
- Thesis probability changes.
- New official/JMod information appears.
- Weekly trend conflicts with short-term move.
- Liquidity deteriorates materially.
- A conversion crosses a required after-tax margin.
- Another opportunity materially dominates a current holding.

## Product differentiation

Raw prices are commodity data. The defensible layer is:

- Cross-timeframe interpretation.
- Portfolio-aware recommendations.
- Catalyst attribution.
- Conversion math.
- Liquidity-aware sizing.
- Adversarial thesis review.
- Capital rotation.
- Refusal to force a trade.

The product should repeatedly demonstrate that saying **CASH** is a valid signal.