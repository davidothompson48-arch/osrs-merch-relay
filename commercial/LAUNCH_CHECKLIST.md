# Merch Desk Analytics — Launch Checklist

## Owner actions required before accepting money

- [ ] Create `osrsmerchdesk@gmail.com`.
- [ ] Use a new unique password and enable 2FA.
- [ ] Create a Venmo Business Profile.
- [ ] Complete available Venmo identity/business verification.
- [ ] Record the exact Venmo Business handle.
- [ ] Save the official Venmo Business QR code.
- [ ] Create the Merch Desk Analytics Discord server.
- [ ] Apply roles/channels from `DISCORD_SETUP.md`.
- [ ] Decide whether the beta starts as sole proprietor or after the new entity is formed.
- [ ] Open/choose a separate bank destination for business receipts when practical.
- [ ] Decide whether the founding beta is US-only initially. Recommended: yes, until payment/tax/privacy obligations are reviewed for broader markets.

## Build actions already staged

- [x] Independent commercial brand: Merch Desk Analytics.
- [x] Founding offer: Pro $59 / 30 days.
- [x] Founding offer: Private Desk $199 / 30 days, capped at 10 seats.
- [x] Landing page prototype.
- [x] Payment flow page with business-profile placeholders.
- [x] Portfolio onboarding generator.
- [x] Dashboard prototype.
- [x] Discord structure.
- [x] Customer welcome/renewal messages.
- [x] Customer/payment ledger template.
- [x] Operator runbook.
- [x] Draft beta terms.
- [x] Draft beta privacy notice.
- [x] Hard no-GP/no-account-access/no-execution boundaries.

## Before publishing the landing page

- [ ] Replace Venmo placeholder with the verified business handle/QR.
- [ ] Replace any temporary onboarding link with the hosted URL.
- [ ] Host the landing/payment/onboarding pages on a dedicated domain or subdomain.
- [ ] Move production customer app files to a separate private repository.
- [ ] Keep customer records and payment data out of the public relay repository.
- [ ] Add Terms and Privacy links to the hosted footer.
- [ ] Have final consumer-facing legal text reviewed before meaningful scale.
- [ ] Read current Jagex Rules and Fan Content Policy again at launch.
- [ ] Avoid Jagex logos, official-looking layouts and copied Jagex artwork/site content.
- [ ] Use Old School RuneScape only descriptively, with clear independent-service disclaimer.

## Market-data production checks

- [ ] Preserve prices.runescape.wiki/RuneLite as the only current GE market source for desk execution analytics.
- [ ] Use a descriptive User-Agent/identification for any direct API traffic.
- [ ] Cache/relay efficiently rather than multiplying direct API traffic per customer.
- [ ] Contact/coordinate with the Wiki real-time price API community if production traffic becomes substantial.
- [ ] Ensure no customer browser/client directly hammers the Wiki API.

## First customer test

Run the entire workflow with one friendly beta tester before public sales:

1. Tester visits landing page.
2. Tester reads pricing/boundaries.
3. Tester makes a test business payment.
4. Operator confirms payment.
5. Operator generates activation/paid-through record.
6. Tester gets Discord role.
7. Tester opens onboarding page.
8. Tester downloads onboarding JSON.
9. Operator validates portfolio fields.
10. Tester receives first personalized desk output.
11. Operator asks what was confusing, slow or unnecessary.

Do not recruit broadly until this path works end-to-end.

## First revenue target

Do not optimize for hundreds of users.

Initial validation target:
- 5 paying customers total;
- at least 3 still active after their first 30-day period;
- at least 2 customers who say the portfolio/capital-allocation layer changed a real decision;
- zero credential/account-access incidents;
- zero payment/role mistakes.

If those are achieved, then build automated authentication, Stripe subscriptions and per-user dashboards.
