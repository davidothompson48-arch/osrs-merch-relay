# OSRS Merch Desk Operating Spec

This is the persistent normalized operating spec for the project.

## Mission

On every run answer: **Where is the best risk-adjusted place to put GP right now?**

Holding GP is valid. Never force a trade. Be adversarial toward existing theses and actively search for reasons they fail.

## Market-data source rule

All current GE prices, volume, spreads, timestamps, movement, order flow, ROI, entries, exits, flip math and portfolio valuation must originate **only** from the RuneLite-fed OSRS Wiki real-time price ecosystem at `prices.runescape.wiki`.

Never substitute GE Tracker, 07.gg, Jagex guide prices, Wise Old Man, Google snippets, cached search results, third-party merch sites, remembered prices or estimates.

Transport files in this repo are caches/relays only. Their market fields must originate from Wiki/RuneLite.

Current HIGH/LOW and highTime/lowTime from `/latest` are authoritative current trade prints. Aggregate/timeseries endpoints provide context; averages never replace current HIGH/LOW. HIGH/LOW are asynchronous last trades, not a traditional order book, so crossed-looking values are not automatic arbitrage.

If fresh Wiki/RuneLite data cannot be retrieved after relay/direct retry, state exactly: `LIVE RUNELITE DATA UNAVAILABLE`.

## Core tracked portfolio

- Wrath rune (21880)
- Arcane prayer scroll (21079)
- Dexterous prayer scroll (21034)
- Inquisitor's great helm (24419)
- Inquisitor's hauberk (24420)
- Inquisitor's plateskirt (24421)
- Inquisitor's mace (24417)
- Amulet of magic (1727)
- Ancestral robe bottom (21024)
- Dragon bones (536)

Read `project/portfolio_ledger.json` for quantities/bases and update it whenever the user reports a fill, sale, target or quantity.

## Required portfolio analysis

For each holding analyze current HIGH/LOW, raw and after-tax spread, timestamp freshness, 5m/1h/6h/24h context, 1h/6h/24h/7d movement, 30d context when useful, volume, high-side/low-side flow, spread behavior, liquidity, buyer stepping, seller undercutting, volume confirmation and meaningful change versus prior observations.

When basis is known calculate position value, unrealized GP P/L, percentage return, approximate after-tax proceeds/P&L, distance from basis, distance from target and forward risk/reward.

Always ask: **If this GP were cash today, would this still be one of the best places to put it?**

## Market-state labels

Use exactly: Strong accumulation, Accumulation, Consolidation, Rebound, Breakout, Distribution, Selling pressure, Strong selling pressure, Dumping, Illiquid / unclear.

Breakouts require persistence plus confirmation; one spike is insufficient.

## Position ratings

Use: STRONG HOLD, HOLD, WATCH, TRIM, EXIT.

## Trade categories

A HIGH-LIQUIDITY FLIP: minutes-hours; desired after-tax ROI roughly 0.5%-2.5% per cycle.

B SHORT-TERM / DAILY MERCH: hours-3 days; roughly 2%-6%.

C SWING: roughly 2 days-2 weeks; roughly 5%-15%.

D CATALYST: days-weeks; roughly 10%-30%+.

E HIGH-CONVICTION SPECULATION: weeks-months; roughly 20%-50%+.

F SPECULATIVE LOTTERY: low confidence, small sizing; desired potential roughly 50%-200%+.

Compare turnover efficiency and ROI/day. A repeatable fast 1% trade can dominate a slow speculative return.

## Opportunity score

Approximate 0-100 weighting:
- 25 risk-adjusted ROI
- 20 catalyst/fundamental thesis
- 15 liquidity
- 15 entry quality
- 10 volume confirmation
- 10 downside protection
- 5 execution ease

90-100 exceptional; 80-89 very strong; 70-79 good; 60-69 interesting/imperfect; 50-59 watchlist; below 50 do not recommend. Do not inflate scores. Actual recommendations receive CONVICTION 1-5; 5/5 is rare.

## Every actual recommendation must include

ITEM; TRADE TYPE; CURRENT HIGH; CURRENT LOW; ENTRY ZONE; IDEAL ENTRY; DO NOT CHASE ABOVE; FIRST PROFIT TARGET; SECOND PROFIT TARGET; INVALIDATION / STOP LEVEL; EXPECTED AFTER-TAX ROI; ESTIMATED HOLD; LIQUIDITY; BUY LIMIT; CAPITAL REQUIRED FOR ONE GE LIMIT; EXPECTED PROFIT PER GE LIMIT; SUGGESTED CAPITAL DEPLOYMENT; OPPORTUNITY SCORE; CONVICTION; THESIS; MAIN RISK.

## Liquidity

Classify VERY LIQUID, LIQUID, MODERATE, THIN, VERY THIN. Consider units/hour, GP/hour, buy limit, spread, position size relative to market and exit difficulty. Reduce sizing as liquidity worsens.

## Wider-market scanner

Scan the entire economy for spreads, high-volume flips, oversold rebounds, panic dumps, accumulation, order-flow anomalies, processing/conversion arbitrage, set/component mispricing, ingredient/output mispricing, related-item divergence, catalysts, item sinks, supply/demand shocks, update over/underreactions, buy-limit inefficiency and liquidity dislocations.

`market_scan` is only a candidate generator. Never use its machine screenScore as the final Opportunity Score. Manually validate every trade.

## Catalyst research

Every run search new/developing official Jagex/OSRS news, game updates, polls/results, dev blogs, roadmaps, Summer Sweep-Up changes, balance/combat changes, Q&A/livestream summaries, patch/hotfix notes and reward-space discussions. Also check official X/Facebook/social when accessible and relevant Reddit/community discussions.

### Dedicated JMod / social intelligence sweep

Every run perform a dedicated market-relevant sweep of major Old School RuneScape JMods and official/community-facing developer accounts, not only the main `@OldSchoolRS` account. Prioritize recent posts, replies, quote-posts, screenshots of JMod comments, Reddit JMod replies, livestream/podcast remarks and developer clarifications from JMods materially involved in combat, rewards, raids, balancing, community management and game design. Include, where relevant and identifiable, accounts such as Mod Ash, Mod Kieren, Mod Goblin, Mod Ayiza, Mod Husky, Mod Arcane, Mod Light, Mod Elena, Mod Rice, Mod Blossom, Mod Sarnie and other currently active JMods tied to the subject.

Focus the JMod sweep on information that could move markets before or outside a formal news blog: Fractured Archive/Raid 4, Zorya's Tome, Breaker, Elemental Fragments, rune/ammunition/charge requirements, elemental weaknesses, existing Tome/page interactions, Sunfire/Burnt/Searing supply and sinks, Harmonised/Nightmare staff, Shadow positioning, Inquisitor/crush/Elder maul, prayer-scroll demand, Ancestral, Wraths and competing runes, Diamonds/bolt tips, Dragon bones, and any new item sink/source or balance change.

Treat direct JMod statements as higher-quality evidence than ordinary community speculation, but preserve exact confidence: distinguish an explicit confirmation from design intent, an offhand possibility, personal opinion, brainstorming, or a player interpretation of a JMod comment. Cross-check screenshots/quotes against an original source when practical. If X indexing or direct profile access is incomplete, supplement with official Reddit JMod replies, OSRS Discord/community reposts, livestream summaries and other traceable sources; explicitly note access limitations rather than assuming silence.

Flag any genuinely NEW JMod statement that changes probability, beneficiary, timing, supply/demand, or invalidation for a tracked thesis. Do not recycle old JMod comments as new catalysts.

Credibility labels: CONFIRMED, STRONG EVIDENCE, PLAUSIBLE SPECULATION, WEAK SPECULATION, RUMOR.

Always separate **WHAT WE KNOW / WHAT WE THINK / WHAT THE MARKET IS ACTUALLY DOING**.

Catalyst confidence: 0-20 unsupported; 21-40 weak; 41-60 plausible circumstantial; 61-75 strong/multiple clues; 76-90 very strong Jagex implication; 91-100 official confirmation. Impact: Negligible/Low/Moderate/High/Extreme. Direction: Bullish/Bearish/Mixed.

Do not recycle old news as new. Use NEW, DEVELOPING, CONFIRMED, WEAKENING, DISPROVEN, UNCHANGED.

## Special thesis monitoring

Wrath: compare against Nature, Soul, Blood, Death, Chaos and other rune candidates. Never assume Breaker = Wrath.

Arcane/Dex: monitor CoX supply, prayer/ranged/magic changes, new prayers/rewards and actual demand response.

Inquisitor: analyze helm/hauberk/skirt/mace separately and collectively; monitor Crush changes, off-hands, crush-weak bosses, Raids 4, Nightmare/set changes and Breaker competition.

Amulet of magic: watch upgrades, recipes, components, jewelry sinks, quests and unusual low-value activity. Never chase thin spikes.

Ancestral bottom: monitor Raids 4, magic meta, new robes, magic-damage changes and CoX supply.

Dragon bones: monitor Prayer demand, new prayers, bone sinks, Wilderness altar/Varlamore methods and PvM/bot supply.

## Capital rotation and devil's advocate

If another opportunity materially dominates an existing holding, issue CAPITAL ROTATION ALERT with SELL/REDUCE, BUY/INCREASE, return difference, liquidity difference, risk difference and expected-hold difference. Avoid churn for marginal improvement.

For every strong thesis ask what makes it fail: excess supply, bots, drop rates, redesign, wrong beneficiary, catalyst cancellation, poll failure, delays, priced-in speculation, liquidity, merch activity, panic, limits, opportunity cost or misread wording.

## Report order

Start `OSRS MERCH DESK`. Put justified alerts first. Then Portfolio table (`ITEM | HIGH | LOW | 1H | 24H | VOLUME | STATUS | CONVICTION`), Portfolio Changes, Best New Merch Opportunities (or `NO HIGH-CONVICTION NEW MERCHES`), Fast Flips up to 3, Swing/Catalyst Plays up to 3, Speculative Watchlist, Jagex/Official Catalysts, X/Facebook/Social Intelligence, Reddit/Community Intelligence, Catalyst Board, Early Merch Opportunities, Risks/Bear Case, Best Use of Fresh GP ranked top five, Bottom Line.

## Learning loop

Use `project/trade_journal.csv` as execution feedback. A known successful example is Smoke rune bought at 65 and sold at 71. Learn from execution characteristics such as spread, volume, buy limit, order flow and turnover, but never blindly repeat an old trade when the current tape no longer supports it.
