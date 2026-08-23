# Compliance and Operating Boundaries

This file defines conservative product rules intended to keep OSRS Merch Desk on the information/analytics side of the line rather than account services, gameplay automation, custody, or GP-for-service exchange.

This is an internal operating policy, not legal advice.

## Never do

- Accept GP, items, bonds, account names, accounts or other in-game value as payment.
- Offer service access in exchange for GP/items.
- Log into customer Jagex accounts.
- Request passwords, session tokens, bank PINs or recovery information.
- Execute Grand Exchange trades for customers.
- Automate mouse/keyboard/client actions.
- Operate a bot, macro, trade executor or client-control layer.
- Hold, transfer, pool, borrow or manage customer GP/items.
- Take a percentage of customer in-game profits.
- Guarantee profit, ROI, GP/hour or outcomes.
- Represent the service as Jagex-approved unless explicit written approval exists.

## Allowed product model

- Subscription paid in normal real-world currency through a payment processor.
- External web dashboard.
- Market analysis based on public RuneLite/Wiki price data.
- User-entered portfolio quantities/cost bases.
- Research, alerts, watchlists and recommendations.
- Manual customer support concerning product functionality and market interpretation.

## Marketing language

Prefer:

- Market intelligence.
- Portfolio analytics.
- Decision support.
- Trade research.
- Opportunity scanning.
- Catalyst monitoring.
- Risk-adjusted capital allocation.

Avoid:

- Guaranteed GP.
- Guaranteed profit.
- We make GP for you.
- Automated merching.
- Passive GP bot.
- We trade your account.

## Trademark / affiliation footer

Use a clear footer such as:

> OSRS Merch Desk is an independent third-party market analytics service. It is not affiliated with, endorsed by, or sponsored by Jagex. Old School RuneScape and related marks are the property of their respective owners.

Do not use official Jagex logos or create branding that implies official status.

## Market-data attribution

Product surfaces should disclose that real-time GE market data originates from the RuneLite-fed OSRS Wiki real-time pricing ecosystem.

The Wiki real-time prices project states that its API is available for community-facing tools and asks real-time pipeline operators to coordinate through its API discussion channel. Before public launch:

1. Use a descriptive production User-Agent identifying OSRS Merch Desk and a contact method.
2. Centralize polling through the relay/cache.
3. Avoid per-user direct polling of upstream endpoints.
4. Join/contact the Wiki API discussion channel to identify the project and learn about changes/maintenance.
5. Review current acceptable-use/licensing language before launch and before redistributing large portions of raw data.

## Subscription rules

- Billing in USD/card only for US launch unless payment processor configuration expands later.
- Clear recurring-billing disclosure.
- Self-service cancellation.
- Do not market refunds as compensation for trading losses.
- Subscription buys access to software/research, not a financial outcome.

## Customer data

Collect only what the product needs:

- Email.
- Subscription tier.
- User-entered OSRS item quantities and cost bases.
- Watchlists and preferences.

Do not require RuneScape login credentials.

## Risk disclosure

Every recommendations surface should make clear:

- GE prices can move rapidly.
- HIGH/LOW prints are asynchronous last trades rather than a guaranteed executable order book.
- Liquidity and transaction age matter.
- Recommendations are probabilistic research, not guarantees.
- Users control and execute their own trades.

## Launch legal review checklist

Before taking payments, review or obtain appropriate professional review of:

- Terms of Service.
- Privacy Policy.
- Refund/cancellation language.
- Trademark/fan-content positioning.
- Upstream data licensing/attribution.
- Payment processor business description.
- State/entity and tax obligations.

Until those are complete, label beta access appropriately and avoid implying formal legal clearance.