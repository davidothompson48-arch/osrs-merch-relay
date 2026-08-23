# Merch Desk Analytics — Founding Beta Operator Runbook

This runbook is for a manual beta before subscription automation exists.

## Daily operating principle

The product is market intelligence, not trade execution. Members control their own accounts, GP and GE orders.

The desk must be willing to say `CASH / NO TRADE`.

## Before taking the first payment

- Create and secure `osrsmerchdesk@gmail.com` with a unique password and 2FA.
- Create the Venmo Business Profile and complete available identity/business verification.
- Record the exact business-profile handle and QR code.
- Create the Discord server using `DISCORD_SETUP.md`.
- Replace all placeholder payment language on the beta page with the verified business-profile information.
- Decide the founding paid-through rule: recommended = 30 calendar days from activation.
- Create a simple customer/payment ledger.
- Read the current Jagex Rules, Fan Content Policy, and OSRS Wiki real-time price API acceptable-use guidance before public launch.
- Do not use Jagex logos, copied website layouts, ripped client assets or language implying official endorsement.

## Customer lifecycle

### 1. Prospect

Send only:
- landing page;
- current founding price;
- what is included;
- clear no-guarantee language.

Never promise a GP return or a specific monthly profit.

### 2. Payment

Confirm payment arrived through the business profile.

Record:
- Discord name;
- tier;
- amount;
- payment date;
- activation date;
- paid-through date;
- payment reference/status.

Do not store bank/card information.

### 3. Access

Assign Discord role and send welcome message.

### 4. Onboarding

Customer submits:
- active item positions;
- quantity;
- average cost basis;
- watchlist;
- broad risk/horizon preferences;
- portfolio constraints.

Never request:
- Jagex password;
- bank PIN;
- recovery email password;
- authenticator/recovery codes;
- session tokens/cookies;
- remote desktop access.

If a customer sends credentials anyway, tell them to change/revoke the exposed credential and do not retain it.

### 5. Portfolio activation

Validate:
- item name/ID mapping;
- quantity format;
- basis units;
- whether any position is sold/closed;
- whether any position is hold-for-use rather than a merch.

Unresolved values must remain unknown. Never guess a customer's basis or quantity.

### 6. Service delivery

Pro members receive:
- full market desk;
- validated fast flips;
- swing/catalyst watch;
- conversion math;
- JMod/social intelligence;
- personal portfolio state and calls.

Private Desk adds:
- higher-touch portfolio allocation;
- custom thesis research;
- larger-capital liquidity planning;
- priority portfolio-change review.

## Desk publication quality control

Before posting a trade:

1. Confirm current market inputs are RuneLite/Wiki-origin.
2. Verify HIGH/LOW transaction age.
3. Reject stale/asynchronous fake spreads.
4. Include 7-day context where available.
5. Calculate GE tax correctly.
6. Check current GE buy limit.
7. Size profit against realistic fill capacity.
8. State the main trap/bear case.
9. Disclose if the house/operator is already exposed to the same thesis when relevant to trust/conflict management.
10. Never present speculation as a Jagex confirmation.

## Suggested manual renewal process

Three days before expiration:

`Your Merch Desk Analytics access is paid through [DATE]. If you want to keep your founding access active, renew through the same business payment route before expiration.`

On expiration without renewal:
- remove paid Discord roles;
- mark inactive;
- do not delete operational records needed for bookkeeping;
- do not continue Private Desk work.

## Refund handling

Before launch, choose and publish a simple refund/cancellation policy. Suggested beta policy:

- Customers may cancel future renewals at any time because billing is manual.
- Case-by-case refunds for duplicate/incorrect payments or inability to deliver access.
- No refunds solely because a market call loses money.

Have an attorney review final consumer-facing terms before scaling materially.

## Bookkeeping

Keep business receipts and payment records separate from personal spending. Track gross revenue, Venmo fees, refunds and business expenses. Use a tax professional when revenue becomes meaningful.

## Upgrade trigger from manual beta to SaaS billing

Do not build automated billing just because it looks professional. Upgrade when one or more becomes true:

- manual renewal tracking is causing mistakes;
- 15–25+ active customers make role management annoying;
- churn/retention analytics matter;
- customers request card/autopay;
- access provisioning needs to be instant;
- you are spending more time on billing/admin than market research.

At that point, migrate to Stripe/subscription entitlements while preserving founding pricing for eligible customers.
