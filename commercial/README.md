# Merch Desk Analytics — Commercial MVP

Independent Grand Exchange market intelligence and portfolio analytics for Old School RuneScape merchants.

## Positioning

Merch Desk Analytics is not a price tracker and is not an account service. It converts RuneLite/Wiki market data, portfolio state, conversions, order flow and catalyst research into one decision:

**Where is the best risk-adjusted place to put GP right now?**

The service is designed first for serious merchants and high-bank-value players who care about capital allocation, liquidity, downside protection and timing.

## Founding beta offer

### Pro — $59 / 30 days

- Full recurring market desk.
- Fast flips, swings and catalysts when validated.
- Conversion/arbitrage monitoring.
- JMod/social catalyst intelligence.
- Personal portfolio ledger.
- Cost basis, current mark and after-tax P/L.
- Concentration/risk analysis.
- HOLD / ADD / TRIM / EXIT calls.
- Capital-rotation alerts.

### Private Desk — $199 / 30 days

Everything in Pro, plus:
- large-bank allocation review;
- custom thesis tracking;
- priority catalyst research;
- higher-touch liquidity and sizing analysis;
- limited to 10 founding seats.

No tier promises profit.

## Founding beta stack

The beta deliberately avoids a full SaaS build.

`RuneLite/Wiki -> existing market relay -> desk analysis -> private Discord + customer-specific portfolio state`

Payments: Venmo Business Profile during beta.

Access: manually assigned Discord roles.

Onboarding: local browser form generates a JSON portfolio payload.

Customer administration: local browser tool generates activation/renewal records and ledger rows.

Production customer state must not be stored in the public relay repository.

## Hard boundaries

- Real-world business payment only.
- Never accept GP or items as payment.
- Never log into a customer's Jagex account.
- Never request Jagex passwords, bank PINs, recovery/authenticator codes or session tokens.
- Never execute GE trades or automate gameplay.
- Never custody customer GP/items.
- Never charge a percentage of in-game profits.
- Never coordinate a pump or use subscribers as exit liquidity.
- Information, research and analytics only.

## Brand

Customer-facing brand: **Merch Desk Analytics**.

Planned support email: `osrsmerchdesk@gmail.com`.

Suggested legal entity: **Merch Desk Analytics LLC** or another generic analytics entity.

Use Old School RuneScape descriptively only, with a prominent independent-service disclaimer. Do not use Jagex logos, official-looking layouts or copied Jagex artwork/site content without permission.

## Prototype files

- `prototype/index.html` — founding beta landing page.
- `prototype/payment.html` — Venmo Business beta payment instructions/placeholders.
- `prototype/onboarding.html` — customer portfolio onboarding JSON generator.
- `prototype/dashboard.html` — demo-data dashboard concept.
- `prototype/admin.html` — local customer activation/renewal helper.

## Operations

- `LAUNCH_CHECKLIST.md` — owner actions and go-live gates.
- `OPERATOR_RUNBOOK.md` — customer lifecycle and desk QC.
- `DISCORD_SETUP.md` — roles, channels and access workflow.
- `templates/customer_ledger.csv` — manual customer/payment ledger format.
- `templates/WELCOME_MESSAGE.md` — activation welcome.
- `templates/CUSTOMER_MESSAGES.md` — renewal/security/support templates.
- `legal/TERMS_BETA_DRAFT.md` — working beta terms draft.
- `legal/PRIVACY_BETA_DRAFT.md` — working beta privacy draft.

## Production architecture later

Only after the manual beta proves demand:

`RuneLite/Wiki -> relay -> intelligence engine -> private user database -> portfolio engine -> authenticated dashboard + alerts`

Recommended later stack remains TypeScript/Next.js, Postgres/Supabase-style storage, Stripe subscriptions, and conventional web hosting. Provider choices are intentionally deferred.

## Validation target

Do not overbuild before this works:

- 5 paying customers;
- at least 3 renew after the first 30 days;
- at least 2 report that the allocation/portfolio layer changed a real decision;
- zero credential incidents;
- zero payment/access mistakes.

If that target is met, build the full SaaS.
