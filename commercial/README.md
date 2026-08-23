# OSRS Merch Desk — Commercial MVP

Independent market intelligence and portfolio analytics for Old School RuneScape merchants.

## Positioning

OSRS Merch Desk is not a price tracker. The product converts RuneLite/Wiki market data, portfolio state, conversions, order flow, and catalyst research into a single decision: **where is the best risk-adjusted place to put GP right now?**

The service is designed first for serious merchants and high-bank-value players who care about capital allocation, liquidity, downside protection, and timing.

## Product tiers

- **Scout — $29/mo**: shared market desk, live opportunity feed, catalysts, fast flips, conversions, weekly trend context.
- **Pro — $79/mo**: Scout + personal portfolio ledger, P/L, concentration, HOLD/ADD/TRIM/EXIT calls, custom watchlist and alerts.
- **Private Desk — $249/mo**: Pro + higher-touch portfolio review, large-bank capital rotation, custom thesis tracking and priority research. Capacity limited.

No tier promises profit.

## Hard boundaries

- USD/card subscription only.
- Never accept GP or items as payment.
- Never log into a customer's Jagex account.
- Never execute GE trades or automate gameplay.
- Never custody customer GP/items.
- Never charge a percentage of in-game profits.
- Information, research and analytics only.

## Brand

Customer-facing brand: **OSRS Merch Desk**.

Planned support email: `osrsmerchdesk@gmail.com`.

Suggested legal entity: **Merch Desk Analytics LLC** or another generic analytics entity, rather than placing `OSRS` in the legal company name.

Footer/disclaimer language should clearly state that the service is independent and is not affiliated with, endorsed by, or sponsored by Jagex.

## Architecture

`prices.runescape.wiki / RuneLite -> existing relay -> market intelligence engine -> per-user portfolio engine -> web dashboard + alerts`

The existing `osrs-merch-relay` remains the source/transport layer. The customer application should ultimately move to a separate private repository. This `commercial-mvp` branch is only a staging area because the connected GitHub action cannot create a new repository.

## Immediate launch objective

Do not overbuild. Validate that people will pay for the interpretation layer before building a full trading terminal.

MVP launch surface:

1. Landing/pricing page.
2. Authentication.
3. Subscription entitlement.
4. Shared hourly desk.
5. Portfolio onboarding/import.
6. Personalized portfolio dashboard.
7. Catalyst/JMod feed.
8. Alerts.
9. Admin view for users, tiers and flagged opportunities.

See the other files in this folder for product, architecture, compliance and launch specifications.