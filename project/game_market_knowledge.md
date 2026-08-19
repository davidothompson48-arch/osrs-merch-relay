# OSRS Game & Market Knowledge Baseline

Updated: 2026-08-19 UTC

Purpose: durable mechanics/meta context for the OSRS Merch Desk. This file is NOT an authority for live GE prices. Every current price, volume, spread, momentum or liquidity claim must still come exclusively from prices.runescape.wiki / RuneLite-fed relay data.

## Source hierarchy

1. Official Jagex/Old School newsposts and polls for announced, proposed, passed, delayed, changed or released content.
2. OSRS Wiki for stable mechanics, formulas, drop tables and strategy context.
3. prices.runescape.wiki RuneLite-fed APIs for all live market data.
4. Reddit/YouTube/X/community discussion for sentiment and idea discovery only; never promote speculation to fact without official corroboration.

## Market structure

- Grand Exchange tax is 2% on most transactions, capped at 5,000,000 gp per item. Tax rounds down. A portion funds Jagex item-sink purchases, with most tax removed from the game.
- Fast-flip analysis must therefore clear tax plus execution/slippage, not merely show a raw HIGH/LOW spread.
- Buy limits, crafting/conversion relationships, drop-source elasticity, alch floors, NPC-shop ceilings, death/reclaim mechanics, item sinks and substitute goods can dominate an item's long-run price behavior.
- A catalyst is not enough by itself. Distinguish: confirmed mechanic -> likely demand/supply channel -> current market confirmation -> entry/exit quality.

## Elemental Magic mechanics

- Elemental weaknesses apply to Strike/Bolt/Blast/Wave/Surge spells on the standard spellbook.
- Each 1% elemental weakness grants +1% Magic accuracy and +1% elemental-weakness damage.
- Weakness damage is calculated separately from ordinary equipment Magic damage: floor(base max * weakness %) is added after the ordinary max-hit calculation. Rounding matters.
- Harmonised nightmare staff has +15% Magic damage and casts standard offensive spells at 4 ticks, one tick faster than ordinary standard-spell casting.
- Tome of fire adds 10% damage to fire spells in PvM.
- Searing page recipe: 1 Burnt page + 100 Sunfire runes -> 1 Searing page. Searing pages charge the Tome of fire and create a recurring sink for Burnt pages and Sunfire runes.
- 1 Tome of fire (empty) can be exchanged one-way for 250 Burnt pages. This creates an economic linkage/floor-ceiling relationship between Tome and Burnt pages.
- Treat any exact ordering of future +2 max-hit effects in the combat formula as implementation-sensitive until Jagex or live-game testing confirms it. Do not automatically assume future flat +2 effects are multiplied identically to base spell max unless verified.

## Summer Sweep-Up 2026: elemental amulets

Official proposal context from the June 2026 Summer Sweep-Up:

- Four early-game elemental amulets were proposed, each providing +2 max hit to its corresponding element and +10 Magic accuracy:
  - Amulet of Air: Air Diamond + relevant runes + Amulet of Magic.
  - Amulet of Water: Water Sapphire + relevant runes + Amulet of Magic.
  - Amulet of Earth: Earth Emerald + relevant runes + Amulet of Magic.
  - Amulet of Fire: Fire Ruby + relevant runes + Amulet of Magic.
- At 30 Runecraft, players are proposed to combine all four elemental amulets into an Elemental Amulet with +2 max hit to all elemental spells and +10 Magic accuracy.
- Market implication: if implementation consumes each component amulet, one finished Elemental Amulet would indirectly require four Amulets of Magic. This is a logical recipe inference from the proposal wording and should be re-verified when final implementation details are published.
- Supply response matters: Amulets of Magic are low-level craft/enchant items, so a confirmed sink can cause an announcement/release shock but also rapidly induce new supply.

## The Fractured Archive / Raids 4

- The Fractured Archive is targeted for late 2026 and passed its original raid lock-in poll with 94.5% Yes.
- Jagex describes it as Old School's toughest raid yet, combat-focused and Theatre-of-Blood-like, with no puzzle rooms, scaling intended for 2-8 players; solos possible but difficult.
- Reward lock-in poll ran 3-10 August 2026. All six functional reward questions passed:
  - Elemental Fragments: 85.8% Yes.
  - Rondache: 80.7% Yes.
  - Zorya's Tome: 90.4% Yes.
  - Zeal: 86.1% Yes.
  - Ascension Crossbows: 85.6% Yes.
  - Breaker: 88.4% Yes.
- The Obligator won the Breaker visual ranked-choice vote.

### Elemental Fragments

- Untradeable raid rewards.
- Consuming one for an element increases max hit of that element's spells by 2.
- Jagex expects them to be relatively common and use pity-RNG mechanics.
- This creates potential post-raid demand for standard elemental spell infrastructure rather than direct tradeable-fragment speculation.

### Breaker

- Confirmed as a hard-hitting best-in-slot Crush megarare reward.
- Final poll-blog mechanics: rolls damage twice by default, three times if Crush is the target's second-weakest Melee defence, and four times if Crush is the weakest Melee defence; best roll is used.
- Can hit targets along a 3-tile line; size interaction provides extra damage on larger targets.
- Jagex explicitly says it will require Ascension Shards plus 'a rune of some kind' and has NOT selected/announced which rune yet.
- Therefore Wrath-rune-for-Breaker is speculation, not confirmed. Maintain competing-rune analysis.
- Jagex said Nex Crush defence will be lowered so Breaker becomes new BIS there.

### Rondache

- +2 Flat Armour and Magic Resist in the poll blog.
- Stores mitigated damage as charges, up to 20, then can spend charges on an instant Shield Bash special attack.
- Shield Bash accuracy uses Crush accuracy from charges, armour and jewellery, not mainhand weapon accuracy.
- Strength is intended to be comparable to Avernic while offering no ordinary accuracy bonus; Jagex explicitly watches interaction with Avernic/ToB value.
- Market watch should include 1H Crush weapons, Avernic, defensive/chip-damage metas and crush jewellery/armour, but do not assume Inquisitor mace is required.

### Zorya's Tome

- Two-handed Magic special-attack weapon; technically a powered staff.
- Normal attack: 3-tick, base max hit 18.
- Poll version: +45 Magic accuracy, +15% Magic damage.
- Special attack and the following three attacks receive +150% accuracy and +60% damage; the next three attacks fire at 2 ticks if the initial special hits.
- Jagex positions it as a PvM DPS spec weapon, not a primary sustained-DPS replacement for Shadow.

### Ascension Crossbows

- Rapid-fire dual-wield Heavy-ranged crossbows, intended as raid-tier replacement/upgrade to blowpipe niches, especially tanky or Heavy-Ranged-weak targets.
- Use Ascension Bolts made from Ascension Shards; initial bolt set includes regular, Diamond and Onyx variants.
- Ascension Shards are also intended as Breaker charge material, creating cross-demand for the same raid resource.
- Diamond/Onyx input relationships deserve conversion and demand monitoring, but current market prices must come only from RuneLite-fed Wiki APIs.

## Shadow / endgame Magic hierarchy

- Tumeken's shadow is the generalist Magic megarare. Its built-in spell receives 3x worn Magic attack and Magic-damage bonuses outside ToA (4x inside), with a 100% total Magic-damage cap.
- Shadow's core edge is extreme accuracy plus scaling with worn Magic damage; it should not be assumed to benefit from elemental weakness because its powered spell is not an elemental standard spell.
- Harmonised + elemental spells can beat or approach Shadow in sufficiently favorable elemental-weakness encounters because Harm casts standard spells at 4 ticks and weakness grants both accuracy and additive weakness damage.
- Do not assume Jagex must buff Shadow because an elemental specialist wins a niche. Generalist-megarare + specialist-elemental niches is a coherent design outcome.

## Nightmare / Phosani market context

- Nightmare uniques have historically been very rare, but Project Rebalance substantially improved rates.
- Current normal Nightmare base unique context from Wiki: armour/mace/staff table and orb table are separate; specific orb rates at normal Nightmare are around 1/960 at base scaling context.
- Phosani's Nightmare remains a high-variance solo farm; Project Rebalance improved specific orb rate to 1/1600, specific Inquisitor piece 1/700, mace 1/1250, staff 1/533 (verify current table before giving exact expected-hour estimates because later updates can change rates).
- Nightmare is strategically interesting when both Harmonised/elemental and Inquisitor/Crush catalysts are active, but 'aligned catalysts' does not automatically make it best GP/hour.

## 2026 confirmed/relevant broader changes

- Summer Sweep-Up July gear changes buffed Sanguinesti staff, Soulreaper axe, Ghrazi rapier, Blade of Saeldor, Pegasian boots, Master Wand, Ancient Sceptres and Inquisitor helm, among others.
- CoX unique weighting changes reduce Arcane/Dex prayer-scroll weighting while increasing relative rates of other uniques; this is a direct supply-side catalyst, but price action still determines timing.
- Hybrid armour was removed from the Raid 4 reward package. Do not revive that thesis unless Jagex proposes it again from a different source.

## Desk reasoning rules learned

- Never confuse 'more units consumed per conversion' with 'more price leverage' without considering production elasticity and substitute supply.
- For linked goods, calculate conversion parity after GE tax using executable RuneLite HIGH/LOW values.
- For equipment catalysts, separate one-time adoption demand from recurring consumable demand.
- For boss farming recommendations, distinguish expected GP/hour, variance, unique-table alignment with our theses, kill-time skill requirements and capital opportunity cost.
- Before making DPS-based merch calls, verify attack speed, base hit, damage multipliers, accuracy formula, weakness calculation, rounding order and whether the effect applies to powered vs standard spells.
- When Jagex wording says 'proposed' or 'we'd like to', do not call it released or confirmed until a lock-in poll/release confirms status.

## Primary static sources

- Official OSRS home/news: https://oldschool.runescape.com/
- Official 2026 polls: https://oldschool.runescape.com/polls/2026
- Raid 4 reward lock-in poll: https://oldschool.runescape.com/polls/2026/1762
- Raid 4 reward poll blog: https://secure.runescape.com/m=news/the-fractured-archive---rewards-poll-blog?oldschool=1
- Raid 4 first rewards proposal: https://secure.runescape.com/m=news/the-fractured-archive---first-rewards-proposal?oldschool=1
- OSRS Wiki Elemental weakness / Maximum magic hit / Harmonised nightmare staff / Tumeken's shadow / Nightmare pages for stable mechanics.

This file should be amended whenever a verified mechanic materially changes a merch thesis.