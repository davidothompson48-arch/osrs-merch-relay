# Merch Desk Analytics — Discord Setup

Use Discord as the access layer for the founding beta. Keep it simple enough to operate manually.

## Roles

- `@Owner` — you only.
- `@Desk Admin` — future trusted operator role.
- `@Pro` — paid Pro members.
- `@Private Desk` — paid Private Desk members.
- `@Founding Member` — optional badge for all beta members.
- `@Expired` — optional holding role before removal.

Do not create roles implying Jagex affiliation, staff status, official status, or guaranteed profitability.

## Category: START HERE

### `#welcome`
Read-only.

Pin:
- What Merch Desk Analytics is.
- Independent/not affiliated with Jagex disclaimer.
- No GP payments.
- No account access.
- No guaranteed profits.
- Support email.

### `#rules-and-risk`
Read-only.

Rules:
1. Never post passwords, bank PINs, recovery codes, authenticator codes or account-access information.
2. Never offer or request GP/items as payment for access.
3. Members execute their own trades and bear their own market risk.
4. No market manipulation, coordinated pump requests, fake screenshots or fabricated fills.
5. No RWT, account services, botting, cheating or rule-breaking services.
6. Do not repost Private Desk reports publicly without permission.
7. Treat all opportunity calls as analysis, not guaranteed outcomes.

### `#announcements`
Read-only. Product changes, billing reminders, major desk notices.

## Category: PRO DESK

Visible to `@Pro` and `@Private Desk`.

### `#full-desk`
Post the complete recurring market desk report.

### `#fast-flips`
Only validated short-duration opportunities. Every post should include entry, do-not-chase, targets, invalidation, expected after-tax ROI, liquidity, buy limit and main trap.

### `#swing-catalyst`
Swing trades and catalyst-driven opportunities.

### `#jmod-catalysts`
Jagex/JMod/social catalyst intelligence. Separate confirmed statements from speculation.

### `#conversions`
Current processing/conversion arbitrage math.

### `#market-chat`
Member discussion. Do not let this become a pump room.

## Category: PORTFOLIOS

### `#portfolio-help`
Pro member support for onboarding corrections, quantity/basis updates and questions.

Do not have members publicly post sensitive account information. Portfolio item/quantity/basis data is sufficient.

## Category: PRIVATE DESK

Visible only to `@Private Desk` plus admins.

### `#private-desk-feed`
Higher-touch allocation ideas, large-bank liquidity notes and Private Desk-wide research.

### Private customer channels
Create one private channel per Private Desk customer only if needed, e.g. `#desk-alex`.

Permissions: customer + Owner/Admin only.

Use these for:
- portfolio changes;
- custom watchlists;
- thesis reviews;
- capital rotation;
- large order/liquidity planning.

Never request account credentials.

## Category: ADMIN

Owner/Admin only.

### `#new-payments`
Manual payment log notices.

### `#renewals`
Upcoming expirations and payment follow-up.

### `#customer-state`
Operational notes only. Do not store passwords or sensitive credentials.

### `#desk-qc`
Track bad calls, stale data incidents, customer feedback and scanner false positives.

## Founding member admission workflow

1. Confirm Venmo Business payment.
2. Add payment to `commercial/templates/customer_ledger.csv` or the production equivalent.
3. Assign `@Founding Member` plus `@Pro` or `@Private Desk`.
4. Send the welcome message from `commercial/templates/WELCOME_MESSAGE.md`.
5. Send the onboarding link/file instructions.
6. Review portfolio data for obvious quantity/basis mistakes.
7. Confirm the customer's activation date and renewal date.
8. For Private Desk, create a private channel only after onboarding is complete.

## Expiration workflow

1. Reminder approximately 3 days before expiration.
2. If renewed, update paid-through date.
3. If not renewed by expiration, remove paid role(s).
4. Preserve customer portfolio state for a short grace period if desired, but do not continue paid access.

## Anti-manipulation rule

The service should never coordinate members to push an item's price, create artificial scarcity, mass-buy to move a thin market, or unload inventory onto subscribers. Recommendations must arise from independently assessed market evidence and should disclose when the operator already holds the item.
