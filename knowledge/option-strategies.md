# NSE Option Strategies — Playbook

Source: Zerodha Varsity Module 6 (Option Strategies). This is a decision playbook for an AI
trading agent constructing option strategies on NSE (Nifty/stock options) — every entry below
should be directly usable to pick a strategy, choose strikes, compute max loss/gain/breakeven,
and decide when to adjust or exit. It is not a summary of theory.

The module covers ~13 strategies plus Max Pain/PCR. It does **not** actually work through Call
Butterfly, Straps, Strips, Bull/Bear Put Ladder, Iron Condor, Long/Short Butterfly, or Box (only
named in the orientation chapter's taxonomy, never built out) — treat any request for those as
out-of-scope for this source and say so.

## 1. Quick reference — outlook → strategy

| Outlook | Conviction | Net cash flow | Strategy |
|---|---|---|---|
| Bullish | Moderate (sub-5% index move; 5-8% for high-vol stock; sub-5% for low-vol stock) | Debit | Bull Call Spread |
| Bullish | Moderate, and put premiums are rich (market pulled back, IV elevated, ample DTE) | Credit | Bull Put Spread |
| Bullish | Outright/strong, expect a big move, low-to-moderate IV with ample DTE | Credit | Call Ratio Back Spread |
| Bullish | Outright/strong, convinced the market **will move** (either direction), often pre-event on a stock | Credit | Bear Call Ladder |
| Neutral | Want pure directional (futures-like) exposure via options, or arbitrage vs futures | Debit (small) | Synthetic Long |
| Bearish | Moderate (~4-5% correction), expect IV to rise into the move | Debit | Bear Put Spread |
| Bearish | Moderate, and call premiums are rich (market rallied, IV elevated, ample DTE) | Credit | Bear Call Spread |
| Bearish | Outright/strong, expect a big move | Credit | Put Ratio Back Spread |
| Neutral, big move expected, direction unknown | IV currently low, expected to rise, event-driven | Debit | Long Straddle (tighter, costlier) / Long Strangle (cheaper, wider breakeven) |
| Neutral, range-bound expected | IV currently high, expected to fall/cool off | Credit | Short Straddle (max premium, narrow range) / Short Strangle (lower premium, wider safety range) |

General rule repeated throughout the module: **higher conviction on the same outlook → wider
spread; lower conviction → tighter, safer spread.** Prefer credit structures over debit ones, all
else equal — but only when the credit is genuinely available (rich premium on the side sold), not by default.

## 2. Bullish strategies

### 2.1 Bull Call Spread

| Field | Detail |
|---|---|
| Market view | Moderately bullish — direction up, limited magnitude, not urgent on time |
| Construction | Buy 1 ATM (or lower-strike) CE **+** Sell 1 OTM (or higher-strike) CE. Same underlying, same expiry, same qty |
| Cash flow | Net **debit** ("debit bull spread") |
| Max Loss | `Net Debit = Premium Paid (lower strike) − Premium Received (higher strike)` — occurs at/below lower strike |
| Max Gain | `Spread − Net Debit`, where `Spread = Higher Strike − Lower Strike` — occurs at/above higher strike |
| Breakeven | `Lower Strike + Net Debit` |

**Strike-distance tradeoff** (100-pt wide spread, three examples from the module): ITM+ATM →
lowest breakeven but worst risk:reward (risk 69 to make 31); classic ATM+OTM → balanced (risk 60
to make 40); OTM+OTM → best risk:reward but highest breakeven (risk 51 to make 49). **Wider
spread = higher max profit potential but also a higher breakeven** — don't chase width without conviction.

**Strike selection by days-to-expiry** (assumes a ~3.75% expected move, from the module's
optimization charts):

| Position in series | Move expected within | Best strikes |
|---|---|---|
| 1st half (start of series) | 5 days | Far OTM both legs |
| 1st half | 15 days | Slightly OTM both legs |
| 1st half | 25 days / at expiry | ATM + near strike (OTM legs start losing money) |
| 2nd half (last 15 days) | 1-5 days | Far OTM both legs |
| 2nd half | 10 days | Slightly OTM (1 strike away from ATM) |
| 2nd half | At expiry | ATM |

Theta governs this table — the closer to expiry, the closer to ATM the spread must be to stay
profitable; far-OTM spreads decay to worthless fastest. **Exit**: max loss is capped and known at
entry, so there's nothing to defensively adjust — exit early only to lock in gains near max profit.

### 2.2 Bull Put Spread

| Field | Detail |
|---|---|
| Market view | Moderately bullish, ideally after a decline (put premiums swollen), IV elevated, ample time to expiry |
| Construction | Buy 1 OTM PE (lower strike) **+** Sell 1 ITM PE (higher strike). Same underlying, expiry, qty |
| Cash flow | Net **credit** ("credit spread") — preferred by the author over the debit Bull Call Spread whenever conditions allow |
| Max Loss | `Spread − Net Credit`, where `Net Credit = Premium Received (higher/ITM) − Premium Paid (lower/OTM)` |
| Max Gain | `Net Credit` |
| Breakeven | `Higher Strike − Net Credit` |

**Strike selection**: any OTM/ITM pair works — further apart = larger spread = larger max profit
*and* larger max loss, scaling together. High conviction → larger spread; low conviction →
smaller spread. **Prefer over Bull Call Spread when**: market has cracked, put premiums are
rich, IV is high, ample DTE, and you expect the market to hold up rather than fall further.

### 2.3 Call Ratio Back Spread

| Field | Detail |
|---|---|
| Market view | Outright bullish (not just moderate) — the module frames it as "make money as long as the market moves in either direction," but strongly favors up |
| Construction | Sell 1 ITM CE (lower strike) **+** Buy 2 OTM CE (higher strike), strict 2:1 ratio (scalable to 4:2, 6:3, …). Same underlying, expiry |
| Cash flow | Usually net **credit** |
| Max Loss | `Spread − Net Credit`, where `Spread = Higher Strike − Lower Strike`, `Net Credit = Premium Received (ITM) − 2×Premium (OTM)`. **Occurs exactly at the Higher Strike** (the "double whammy" point — short leg is deep ITM, long legs still worthless) |
| Payoff below lower strike | Flat at `+Net Credit` (limited but positive if bullish view is wrong and market falls) |
| Max Gain | Unlimited above upper breakeven |
| Lower Breakeven | `Lower Strike + Net Credit` |
| Upper Breakeven | `Higher Strike + Max Loss` |

**Strike selection**: in the 1st half of the series, sell slightly-ITM and buy slightly-OTM
(near-the-money) regardless of DTE — far-OTM combinations lose money even when directionally
right. In the 2nd half, the optimal combo shifts to **both legs ITM** (deep-ITM short,
slightly-ITM long) — an unusual, non-classic combination that beats every other pairing that late.

**Volatility/Theta** (read before deploying): with ample DTE (~30 days) rising IV **helps** a lot
(module example: payoff moves from −67 to +43 as IV goes 15%→30%); at ~15 days it still helps,
less; with **few days to expiry, rising IV hurts** (counter-intuitive — near expiry, higher IV
raises the odds the long OTM legs finish OTM, so they don't compensate for the fixed max-loss
zone). Do not deploy close to expiry if you expect IV to rise.

**Exit**: max loss sits precisely at the short strike, so the strategy is most dangerous when the
market stalls right there into expiry — if conviction on the big move fades, close rather than hold.

### 2.4 Bear Call Ladder

Despite the name, this is a **bullish** strategy — an improvisation over the Call Ratio Back
Spread that finances the long legs with a deeper ITM short.

| Field | Detail |
|---|---|
| Market view | Outright bullish, and specifically confident the market **will move significantly** — the author suggests this works best on **individual stocks around quarterly results**, not on the index |
| Construction | Sell 1 ITM CE **+** Buy 1 ATM CE **+** Buy 1 OTM CE, strict 1:1:1 ratio (scalable). Same underlying, expiry |
| Cash flow | Net **credit**, typically better cash flow than the equivalent Call Ratio Back Spread |
| Max Loss | `Spread − Net Credit`, where `Spread` = difference between the short (ITM) and the ATM long strike, `Net Credit = Premium Received (ITM) − Premium Paid (ATM + OTM)`. **Occurs across the ATM-to-OTM strike range** (loss is flat/similar at both middle and highest strike) |
| Payoff below lower strike | Flat at `+Net Credit` |
| Max Gain | Unlimited above upper breakeven |
| Lower Breakeven | `Lower (ITM short) Strike + Net Credit` |
| Upper Breakeven | `(ATM Strike + OTM Strike) − ITM Strike − Net Credit` — i.e. sum of the two long strikes minus the short strike minus net credit |

**Key risk**: there is a real, non-trivial **loss zone between the lower and upper breakeven** —
the strategy is punished hardest if the market simply does nothing. Only deploy when convinced
the underlying will move meaningfully, regardless of direction. Greeks behave like the Call
Ratio Back Spread — rising IV helps with ample DTE, hurts close to expiry.

## 3. Synthetic Long & Arbitrage

| Field | Detail |
|---|---|
| Market view | Replicate a **long futures** payoff using options — pure directional exposure, delta ≈ +1, linear payoff |
| Construction | Buy 1 ATM CE **+** Sell 1 ATM PE. Same underlying, same strike, same expiry |
| Cash flow | Small net debit typically (difference between call and put premium — should be small/zero per put-call parity) |
| Breakeven | `ATM Strike + Net Premium Paid` |
| Payoff | Linear like a long future — profit/loss unbounded and symmetric around breakeven (module verifies ±200-point symmetry around the breakeven point) |

**Why use it**: replicate futures exposure via options, or as the long leg of a
**put-call-parity arbitrage**: `Long Synthetic Long + Short Futures ≈ 0` (parity says this nets
to zero P&L at any expiry level). If executing `Long ATM Call + Short ATM Put + Short Futures`
(same expiry, strike ≈ futures price) produces a **non-zero, positive P&L at every tested expiry
level**, that's a locked-in, direction-independent arbitrage. **Net out costs before trading it**:
brokerage, STT (heavy on ITM options carried to expiry), stamp duty, other taxes. Rule of thumb: a
raw edge of ~10 points usually isn't worth it after costs even with a discount broker (breakeven
~4-5 pts); look for 15-20+ point edges, and consider squaring off just before expiry to dodge the
STT trap on ITM options (small give-up in points to do so).

## 4. Bearish strategies

### 4.1 Bear Put Spread

| Field | Detail |
|---|---|
| Market view | Moderately bearish (~4-5% correction quantified in the module) |
| Construction | Buy 1 ITM PE (higher strike) **+** Sell 1 OTM PE (lower strike). Same underlying, expiry, qty |
| Cash flow | Net **debit** |
| Max Loss | `Net Debit = Premium Paid − Premium Received` |
| Max Gain | `Spread − Net Debit` |
| Breakeven | `Higher Strike − Net Debit` |

**Strike selection by days-to-expiry** (expecting a ~4% down move):

| Position in series | Move expected within | Higher strike | Lower strike |
|---|---|---|---|
| 1st half | 5 days | Far OTM | Far OTM |
| 1st half | 15 days | ATM | Slightly OTM |
| 1st half | 25 days | ATM | OTM |
| 1st half | At expiry | ATM | OTM |
| 2nd half | Same day | OTM | OTM |
| 2nd half | 5 days | ITM/OTM | OTM |
| 2nd half | 10 days | ITM/OTM | OTM |
| 2nd half | At expiry | ITM/OTM | OTM |

**Volatility effect**: cost barely moves with IV when there's ample DTE (30 days); sensitivity
rises sharply as expiry nears. **Only put this on if you expect IV to increase**, especially in
the back half of the series; avoid it if you expect IV to fall.

**Delta note** (applies to any multi-leg position, introduced here): sum the signed deltas of
each leg (short options flip sign) to read the net directional bias — a bear put spread nets
negative, confirming bearish bias; a sum near 0 means "delta neutral," reacting mainly to
volatility/time rather than direction.

### 4.2 Bear Call Spread

| Field | Detail |
|---|---|
| Market view | Moderately bearish, ideally after a rally (call premiums swollen), IV favorable, ample DTE |
| Construction | Buy 1 OTM CE (higher strike) **+** Sell 1 ITM CE (lower strike). Same underlying, expiry, qty |
| Cash flow | Net **credit** — the reason to prefer this over Bear Put Spread when conditions allow |
| Max Loss | `Spread − Net Credit` |
| Max Gain | `Net Credit` |
| Breakeven | `Lower Strike + Net Credit` |

**Strike selection by days-to-expiry** (expecting a ~4% down move):

| Position in series | Move expected within | Higher strike | Lower strike |
|---|---|---|---|
| 1st half | 5 days | Far OTM | ATM + 2 strikes |
| 1st half | 15 days | Far OTM | ATM + 2 strikes |
| 1st half | 25 days | OTM | ATM + 1 strike |
| 1st half | At expiry | OTM | ATM |
| 2nd half | 5 days | Far OTM | Far OTM |
| 2nd half | 15 days | Far OTM | Slightly OTM |
| 2nd half | 25 days | Slightly OTM | ATM |
| 2nd half | At expiry | OTM | ATM/ITM |

**Volatility effect**: identical pattern to Bear Put Spread — negligible IV sensitivity with
ample DTE, growing sharply near expiry. Only deploy when you expect IV to increase.

### 4.3 Put Ratio Back Spread

| Field | Detail |
|---|---|
| Market view | Outright bearish |
| Construction | Sell 1 ITM PE (higher strike) **+** Buy 2 OTM PE (lower strike), strict 2:1 ratio. Same underlying, expiry |
| Cash flow | Net **credit** — must be executed for a net credit; do not initiate if it's a net debit |
| Max Loss | `Spread − Net Credit`. **Occurs exactly at the Lower Strike** (mirror of the call ratio back spread's danger point) |
| Payoff above higher strike | Flat at `+Net Credit` (limited profit if market rises instead) |
| Max Gain | Unlimited below lower breakeven |
| Lower Breakeven | `Lower Strike − Max Loss` |
| Upper Breakeven | `Lower Strike + Max Loss` |

**Strike selection**: stick to the classic ITM (short) + OTM (long) combination regardless of
time-to-expiry — unlike the call ratio backspread, there's no 2nd-half exception here.
**Volatility effect**: rising IV helps with ample DTE, moderately helps at 15 days, negligible
impact with few days left — near expiry you only need to be right on direction.

## 5. Neutral / volatility strategies

These are **delta-neutral** — direction doesn't matter, but IV read and event timing are everything.

### 5.1 Long Straddle

| Field | Detail |
|---|---|
| Market view | Big move expected, **direction unknown** — best set up around a specific catalyst (earnings, major event) |
| Construction | Buy 1 ATM CE **+** Buy 1 ATM PE, same strike, same underlying, same expiry |
| Cash flow | Net **debit** |
| Max Loss | `Net Premium Paid` — occurs exactly at the ATM strike (flat market is the worst outcome) |
| Max Gain | Unlimited in either direction (V-shaped payoff) |
| Upper Breakeven | `ATM + Net Premium` |
| Lower Breakeven | `ATM − Net Premium` |
| Delta | ~0 (Call ≈ +0.5, Put ≈ −0.5, net zero) — delta-neutral |

**What must align for profitability** (all five, per the module): (1) IV **relatively low** at
entry; (2) IV **increases** during the hold; (3) the market makes a **large** move — magnitude,
not direction, matters; (4) that move happens **quickly, well within expiry** (theta decay
accelerates exponentially in the last week); (5) best deployed around **major events whose actual
outcome differs drastically from consensus** — if the outcome merely confirms what's priced in,
IV collapses post-announcement and the straddle loses even with the "right" direction (bought
high IV, effectively settled at low IV). Numeric example: a straddle costing ~2.2% of spot to
breakeven needs roughly a 3%+ total move (breakeven + target profit) within the expiry window —
a high bar to check against before entering.

### 5.2 Short Straddle

| Field | Detail |
|---|---|
| Market view | Range-bound expected; or IV currently elevated and expected to **collapse** after a known event |
| Construction | Sell 1 ATM CE **+** Sell 1 ATM PE, same strike/underlying/expiry |
| Cash flow | Net **credit** |
| Max Gain | `Net Premium Received` — occurs exactly at the ATM strike (best case: market doesn't move) |
| Max Loss | Unlimited in either direction (inverted-V payoff) |
| Upper Breakdown | `ATM + Net Premium` |
| Lower Breakdown | `ATM − Net Premium` |
| Delta | ~0 — delta-neutral |

**Ideal setup** (mirror of the long straddle): IV relatively **high** at entry, expected to
**fall** during the hold. Module case study: sell the ATM straddle **3-4 days before a scheduled
event** (e.g. quarterly results) to harvest the pre-event IV premium, then **close immediately
after the announcement** as IV crushes — don't hold through the full decay curve once the
IV-crush thesis has played out (Infosys example: sold for 95, closed for 75 within minutes of the
results print — the call's rise was smaller than the put's IV-driven fall). **Unlimited-risk
warning**: uncapped loss on both sides — size and monitor accordingly, with a clear
stop/adjustment trigger (e.g. a breach of either breakdown point).

### 5.3 Long Strangle

An OTM-strike version of the long straddle, built to **reduce cost** at the expense of a wider breakeven.

| Field | Detail |
|---|---|
| Market view | Same as long straddle — large move expected, direction unknown, event-driven |
| Construction | Buy 1 OTM CE **+** Buy 1 OTM PE, equidistant from ATM, same ratio (1:1 or scaled equally), same underlying/expiry |
| Cash flow | Net debit, cheaper than the equivalent straddle |
| Max Loss | `Net Premium Paid` — flat across the entire range **between** the two strikes (not a single point, unlike the straddle) |
| Max Gain | Unlimited in either direction |
| Upper Breakeven | `CE Strike + Net Premium` |
| Lower Breakeven | `PE Strike − Net Premium` |
| Delta | ~0 (OTM legs each ~0.3 or less, nets close to zero but not perfectly, since the two OTM deltas need not be identical) |

Same five alignment conditions as the long straddle apply (low IV at entry, IV rises during
hold, large fast move, event-driven with an outcome that surprises consensus).

### 5.4 Short Strangle

| Field | Detail |
|---|---|
| Market view | Range-bound — best on names in a clear, established trading range (module example: Reliance stuck between 850-1000 for an extended period) |
| Construction | Sell 1 OTM CE **+** Sell 1 OTM PE, equidistant from ATM, same ratio, same underlying/expiry |
| Cash flow | Net credit, smaller than the equivalent short straddle |
| Max Gain | `Net Premium Received` — flat across the entire range between the two strikes |
| Max Loss | Unlimited beyond either strike |
| Upper Breakeven | `CE Strike + Net Premium` |
| Lower Breakeven | `PE Strike − Net Premium` |

**Playbook use**: identify range-bound names (double/triple top-and-bottom price action), write
strikes **outside** the established range, and watch closely for breakouts/breakdowns — wider
strikes (vs. a short straddle) buy real safety margin, but risk stays unlimited if the range
fails; a breach of either strike is the exit trigger, not a level to average into.

## 6. Max Pain & Put-Call Ratio (context tools, not standalone strategies)

### 6.1 Max Pain

Theory (contested — the module presents it candidly as "believe what you want"): option writers,
as a group, tend to profit more consistently than buyers, so the strike at which **option writers
collectively lose the least money** is, per this theory, where the underlying is more likely to expire.

**Computation**:
```
For each strike K, assume market expires exactly at K:
  Call writer loss at K  = Σ over all call strikes k≤K of  max(K−k, 0) × OI(call, k)
  Put writer loss at K   = Σ over all put strikes k≥K of   max(k−K, 0) × OI(put, k)
  Total pain(K) = Call writer loss at K + Put writer loss at K

Max Pain strike = argmin_K [ Total pain(K) ]
```
Run across every listed strike (a spreadsheet/script in practice) and take the strike with
minimum aggregate writer loss.

**Practical adjustment used by the author** (do not use raw Max Pain unmodified): freeze the OI
snapshot and compute at a **fixed point — 15 days to expiry** (OI shifts daily, so the raw answer
drifts if recomputed constantly); take the raw Max Pain strike and add a **5% safety buffer**
(empirically ~1.5-2 SD away, i.e. ~34% probability of the market moving beyond it); treat
Max Pain → Max Pain+5% as the expected expiry zone; bias toward **writing calls beyond the top of
that range** while **avoiding naked puts** ("panic spreads faster than greed" — down-moves can
outrun the buffer faster than up-moves); hold to expiry once written, avoid averaging into losers.

### 6.2 Put-Call Ratio (PCR)

```
PCR = Total Put OI / Total Call OI
```
Contrarian indicator:

| PCR value | Reading | Contrarian trade bias |
|---|---|---|
| > ~1.3 | Extreme bearishness (heavy put buying) — market "oversold" | Look for upside reversal |
| 0.5 – 1.0 | Normal trading activity | No signal, ignore |
| < ~0.5 | Extreme bullishness (heavy call buying) — market "overbought" | Look for downside reversal |

The 1.3 / 0.5 thresholds are **Nifty-calibrated examples, not universal constants** — back-test
extreme-value thresholds per underlying (e.g. Infosys may flag "extreme" at a different PCR
level than the index) before using PCR as an actual signal.

## 7. Greeks cheat sheet across all strategies

| Strategy | Cash flow | Theta (time decay) | Vega (rising IV) — ample DTE | Vega — near expiry |
|---|---|---|---|---|
| Bull Call Spread | Debit | Works against you (long leg decays faster than short) | Minor | Strike choice must tighten to ATM |
| Bull Put Spread | Credit | Works for you | Minor | Minor |
| Call Ratio Back Spread | Credit | Mixed (short gains, longs decay) | **Helps** | **Hurts** |
| Bear Call Ladder | Credit | Mixed | **Helps** | **Hurts** |
| Synthetic Long | Small debit | Roughly neutral (mimics futures) | Roughly neutral | Roughly neutral |
| Bear Put Spread | Debit | Works against you | Negligible | Only enter if IV expected to **rise** |
| Bear Call Spread | Credit | Works for you | Negligible | Only enter if IV expected to **rise** |
| Put Ratio Back Spread | Credit | Mixed | **Helps** | Negligible impact either way |
| Long Straddle | Debit | Strongly against you (biggest theta drag of all) | Strongly **helps** | Strongly against you (needs the move to already be in motion) |
| Short Straddle | Credit | Strongly for you | Strongly **hurts** | Strongly for you (ideal exit zone if IV has crushed) |
| Long Strangle | Debit | Against you | Helps | Against you |
| Short Strangle | Credit | For you | Hurts | For you |

(Delta rule for reading net bias on any multi-leg position is in §4.1.)

## 8. Strategy selection decision tree

Walk top-to-bottom using directional bias, conviction, current IV level/regime, and DTE:

```
1. Directional view? NO → step 5 (Neutral). YES → step 2.

2. Conviction? MODERATE → step 3. STRONG/OUTRIGHT (big move, or convinced market WILL move) → step 4.

3. Moderate Directional
   BULLISH: IV elevated + market already pulled back (rich put premiums)? YES → Bull Put Spread
            (credit). NO → Bull Call Spread (debit); strikes from the DTE table in §2.1.
   BEARISH: IV elevated + market already rallied (rich call premiums)? YES → Bear Call Spread
            (credit). NO → Bear Put Spread (debit), only if you also expect IV to rise; strikes
            from the DTE table in §4.1/§4.2.

4. Strong Directional
   BULLISH: ample DTE (1st half) + IV low/moderate → Call Ratio Back Spread (sell slightly-ITM,
            buy 2x slightly-OTM). Ample DTE + convinced of a sharp move on a specific STOCK around
            an event (earnings) → Bear Call Ladder (sell 1 ITM, buy 1 ATM + 1 OTM; accept the
            mid-range loss zone). Few DTE left + IV expected to rise → reconsider, both ratio
            strategies are hurt by rising IV near expiry; prefer a plain Bull Call Spread.
   BEARISH: → Put Ratio Back Spread (sell 1 ITM PE, buy 2x OTM PE); works with ample DTE and is
            indifferent to IV near expiry — the more forgiving of the two ratio structures.

5. Neutral (magnitude/IV view, no direction)
   Big move expected, direction unknown:
     IV LOW + expected to RISE (event pending, consensus likely surprised) → Long Straddle
       (tightest breakeven, costlier) or Long Strangle (cheaper, wider breakeven).
     IV already high / no catalyst → don't buy volatility; go to the range case below instead.
   Range-bound expected:
     IV HIGH + known catalyst about to resolve, expect IV to collapse after → Short Straddle
       (max premium, tightest range, uncapped risk) or Short Strangle (lower premium, wider
       safety margin, uncapped risk).
     Well-established range (double/triple top-bottom), no near-term catalyst → Short Strangle,
       strikes outside the range; a breach of either strike is the adjustment trigger.

6. Cross-check with Max Pain / PCR (context, not a standalone trigger):
   Max Pain + 5% buffer → plausible expiry zone; bias short-strike placement (any credit
     strategy above) outside that zone, and prefer writing calls over naked puts beyond it.
   PCR > ~1.3 (back-tested per underlying) → lean away from fresh bearish credit structures
     (contrarian bullish); PCR < ~0.5 → lean away from fresh bullish credit structures
     (contrarian bearish). Both are a soft tilt, not an override of the analysis above.
```

## Opinion protocol

Whenever this agent expresses a view that could be traded via an NSE option strategy, structure
the opinion as follows — every field is mandatory, not optional color:

1. **Underlying & directional view** — instrument, bullish/bearish/neutral, magnitude expected
   (moderate vs. outright), and the one-line thesis (fundamental, technical, quantitative, or
   event-driven).
2. **Strategy choice rationale** — name the specific structure from §1-§5 and justify it against
   directional conviction, current IV level/regime (elevated vs. depressed, which side's premium
   is rich), and days-to-expiry. State why a simpler alternative (naked option, or the debit
   version of the chosen credit spread) was not preferred.
3. **Construction** — every leg: buy/sell, strike (ITM/ATM/OTM plus actual strike), option type,
   ratio, same expiry confirmed. Net cash flow (debit or credit) and the amount.
4. **Max loss / max gain / breakeven(s)** — from the formulas above, in points and % of spot. If
   max loss or gain is unlimited (any short straddle/strangle, or beyond a ratio-spread's danger
   strike), say so explicitly rather than omitting the field.
5. **Greeks read** — net position delta (sum of signed leg deltas) confirming the intended bias
   or delta-neutrality; theta impact (for/against); and the vega read from §7, stating whether
   the current DTE bucket makes IV a tailwind, headwind, or negligible for this structure.
6. **Invalidation / adjustment trigger** — the specific price level (a breakeven, a ratio
   spread's danger strike, a short strangle's range boundary) or event outcome (IV crush
   confirmed, consensus matched vs. surprised) that would make the agent close or adjust,
   independent of a raw stop-loss.
7. **Confidence (0-100)** — calibrated to strength of the directional evidence, confidence in the
   IV forecast specifically (several of these strategies are won or lost on the IV call, not the
   direction call), and how much of the thesis depends on an event outcome that could surprise
   either way. State the number and the one or two biggest drivers of uncertainty.
