# OSRS investment desk — post–Fractured Archive recalibration
Research date: 2026-11-05 | This document is evidence/context, not a live order sheet.

## Scope and source policy
- Prices, volumes, bid/ask prints: only RuneLite-derived data exposed by prices.runescape.wiki and relayed into market_universe. Read market_radar.json and speculative_park_snapshot.json for contemporaneous records.
- Official roadmap, blog and implemented mechanics: Jagex and the OSRS Wiki.
- Reddit: *self-reported investor sentiment only*. Never infer actual aggregate positions, probabilities, insider knowledge or future prices from posts.
- A high RuneLite transaction price means an instant-buy print; a low price means an instant-sell print. These are not an order book, and asynchronous prints can be crossed.

## Resolved: Raid 4 is live
The Fractured Archive launched October 20, 2026. The Obligator uses **1 Ascension shard + 20 Nature runes + 20 Death runes for 10 charges**. Wrath rune speculation tied to this charging mechanic is **disproven**. Archive pre-release probability trees; never silently reinstate them.

Source: https://oldschool.runescape.wiki/w/Obligator

A November 3 announcement raised the possibility of upcoming changes to Ascension shard availability/use-rate. Do not assume proposed changes are already live and do not catch a falling knife on a supply-sensitive item ahead of patch details.

Source: https://www.gielinorgains.com/game-updates/2026-11-03-quest-month-kick-off-tfa-tweaks-and-more

## Future catalyst: Gemstone Dragons / Diamond Dragon
Dungeons of Gielinor is on the Spring 2027 roadmap. The existence of the content theme is not a proof that all three dragon hunter weapons will be best in slot or that drops will support sustained farming. Reddit reports sizable dragonbane inventories, introducing crowding and sell-the-news risk.

Watch: dragon hunter lance, dragon hunter crossbow, dragon hunter wand. Prefer patient bids, a capped and correlated basket, and exits on a validated demand event rather than unconditional release-day holding. Re-underwrite at each boss-stat or reward-blog announcement.

Roadmap: https://oldschool.runescape.wiki/w/Upcoming_updates
Community example: https://www.reddit.com/r/GrandExchangeBets/comments/1xol28s/best_bet_or_most_retarded/

## Supply risk: underwater gem mining and crafting
October 29 Deep Sea Diving proposal includes gem rocks and jewellery production changes. The proposal is not implemented; production rates, poll results and economic significance are not known. The direction of the *possible future supply* risk for diamonds, rubies and red topaz is more directly identifiable than a confident price forecast.

Source: https://beta.osrs.cloud/news/deep-sea-diving-expansion

Diamond -> 12 diamond bolt tips remains a measurable *conversion*, not an automatic arbitrage: check output prices and tax, player time, realistic sell-through and the chance of compressing your own margin.

## Supply risk: Menaphos and a true Soul Altar
Roadmap proposes a true Soul Altar for 90 Runecraft. It may increase Soul rune supply, but no reliable per-hour output or adoption rate has yet been established. Don't take a negative recent price move as proof of an imminent reversion.

Source: https://oldschool.runescape.wiki/w/Upcoming_updates

## Market-regime and deflation hypothesis
market_radar.json runs an equal-weight *selected-item* geometric price index, including cross-sector comparisons to the 24h price baseline. It appends daily prices to history/market_regime_daily.jsonl. Only when valid 7-day and 30-day historical observations exist should it report changes in a fixed basket and an inverse cash-purchasing-power proxy.

This is not a monetary-supply or full-game inflation measure. Price decline may reflect new reward supply, botting, altered player demand, substitutions, tax and changes to account progression. Do not conclude "OSRS is deflating" from a single snapshot or a selected basket.

## Mandatory execution and risk gates
1. Confirm current cash, actual holdings and offers; project/portfolio_ledger.json contains old entries and is not a trading instruction.
2. Confirm both RuneLite transaction sides are fresh; reject crossed/asynchronous prints and tiny-volume hype trades.
3. After GE tax, price impact and cash lockup, does the planned trade clear an attractive *net* risk-adjusted profit hurdle?
4. Never exceed 30% liquid GP in all speculative parks or 18% in a correlated future-content theme. Zero allocation is acceptable.
5. Explicitly define the next catalyst, thesis invalidation, target time horizon, and patient exit method before entering a position.
6. Do not treat model scenario probabilities as empirical calibration; the sample of user-confirmed executed trades remains limited.

## Next checkpoints
- November 2026: examine the *implemented*, not merely announced, Ascension shard update. Compare post-patch average prices and trade volume.
- Next Gemstone Dragon information release: revise style-specific DPM assumptions and crowding. Look for negative surprises as well as confirmations.
- Deep Sea Diving poll: update proposed gem supply assumptions only after confirmed results, then monitor actual launch.
- Menaphos design and RuneCraft rates: test whether new Soul rune production is economically meaningful.
- After 7 and 30 days of market_radar history: review selected basket purchasing-power trend, constituent coverage and outliers, with cash as the null benchmark.

No GE trades have been placed by this desk.
