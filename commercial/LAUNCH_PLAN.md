# Launch Plan

## Launch strategy

Launch as a paid beta aimed at serious merchants rather than trying to win the entire OSRS market immediately.

Goal: prove that customers will repeatedly pay for interpretation, portfolio intelligence and catalyst monitoring before investing heavily in custom infrastructure.

## Offer

### Founding Scout

$19/month for first 50 users, then $29/month.

Includes shared desk, opportunity feed, catalysts, fast flips and conversions.

### Founding Pro

$59/month for first 25 users, then $79/month.

Includes personalized portfolio tracking and capital rotation.

### Founding Private Desk

$199/month for first 10 users, then $249/month.

Includes higher-touch portfolio reviews and custom thesis tracking.

Founding prices stay locked while the customer remains continuously subscribed.

## Why founding pricing

- Creates urgency without fake scarcity.
- Rewards early product feedback.
- Lets us test willingness to pay below final price.
- Makes the eventual standard price increase credible.

## Customer acquisition

Primary channels:

1. OSRS merching / economy communities where promotion is permitted.
2. X account posting catalyst/tape observations with delayed or partial examples.
3. Reddit educational posts where self-promotion rules permit it.
4. Discord partnerships with PvM/merchant communities.
5. Referral program after retention is proven.

Do not spam communities or conceal commercial affiliation.

## Content strategy

Public content demonstrates reasoning, not just calls.

Examples:

- "Why +4% today does not mean a weekly reversal."
- "This 8% GE spread is fake: transaction age explains why."
- "The conversion is profitable only below this input price."
- "A JMod comment changed the beneficiary, not the catalyst."
- "When cash is the highest-conviction trade."

The free content should establish that the service rejects bad setups rather than producing endless buy signals.

## Beta onboarding

1. Customer chooses tier.
2. Creates account.
3. Accepts terms/risk disclosure.
4. Pro/Private users enter portfolio holdings manually or paste a supported CSV template.
5. System validates item names/IDs, quantity and basis.
6. Customer selects watchlist themes.
7. Dashboard generates initial portfolio diagnosis.
8. Alerts begin only after portfolio validation.

Never ask for account credentials.

## MVP success metrics

First 30 days:

- 25+ paying users.
- At least 10 Pro users.
- At least 3 Private Desk users.
- 60%+ weekly active usage.
- Less than 10% involuntary churn from product confusion/billing issues.
- At least 5 retained customers explicitly reporting that portfolio/catalyst analysis changed a decision.

Do not judge product quality by whether every recommended trade wins.

## Build sequence

### Stage 0 — current

- Product specification.
- Commercial boundaries.
- Architecture.
- Landing prototype.
- Dashboard prototype.

### Stage 1 — sellable beta

- Separate private application repository.
- Production domain.
- Auth.
- Stripe subscriptions.
- User/tier database.
- Shared desk ingestion from relay.
- Portfolio CRUD.
- Basic personalized dashboard.
- Email alerts.
- Admin console.

### Stage 2 — retention

- Custom watchlists.
- Catalyst feed.
- Conversion engine UI.
- Alert preferences.
- Portfolio import template.
- Historical recommendation tracking.
- Trade journal feedback.

### Stage 3 — scale

- Discord entitlement/alerts.
- Better social/JMod ingestion.
- Referral program.
- Team/admin tooling.
- Model evaluation and recommendation quality dashboards.
- Mobile-first PWA or native wrapper only if usage justifies it.

## Accounts the owner must create/control

These should remain owner-controlled; credentials should never be pasted into chat or committed to GitHub.

- `osrsmerchdesk@gmail.com` with a unique password and 2FA.
- New legal entity.
- Stripe account under that entity.
- Domain registrar account.
- Supabase project.
- Vercel/Cloudflare deployment account.
- Discord server/account if Discord is used.

## Suggested domain shortlist

Check availability before purchase:

- osrsmerchdesk.com
- gedesk.gg
- merchdesk.gg
- osrsdesk.com

Brand can remain OSRS Merch Desk even if the shortest practical domain differs.

## Owner decisions deferred until required

The MVP can proceed without these, but they must be resolved before accepting payments:

- State of LLC formation.
- Final launch budget.
- Final domain.
- Final legal documents.
- Payment processor approval/configuration.

## Launch gate

Do not take paid subscriptions until:

- production site is HTTPS;
- billing/cancellation works;
- support email is active;
- privacy/terms pages exist;
- customer data is isolated per user;
- relay data attribution and API behavior are reviewed;
- recommendation pages show freshness and risk disclosures;
- no account credentials or GP transfer are part of onboarding.