# Options Theory Playbook — NSE Index/Stock Options

Source: Zerodha Varsity Module 5 (Options Theory for Professional Trading), distilled into
a decision-oriented playbook for an AI trading agent. All options in India are
**European style, cash-settled** (NSE removed American options). No physical
delivery / early-assignment risk exists for either buyer or seller — settlement
happens only on expiry against the closing spot price.

---

## 1. Core Definitions & Formulas

**Intrinsic Value (IV)** — money the buyer would realize if exercised today. Never negative.

```
IV (Call) = Max[0, Spot − Strike]
IV (Put)  = Max[0, Strike − Spot]
```

**Time Value** — the rest of the premium; compensation the seller demands for the
risk that time + volatility could still push the option ITM.

```
Premium = Intrinsic Value + Time Value
```

- Deep OTM options: premium is 100% time value.
- Deep ITM options: premium is mostly intrinsic value, small time value.
- ATM options carry the highest time value component of any strike (see Gamma/Theta below).
- Time value decays to zero by expiry — an option is a wasting/depreciating asset.

**Moneyness classification** (drives Greek behavior — always classify a strike before
sizing or picking it):

| Strike vs Spot | Call Option | Put Option |
|---|---|---|
| Strike < Spot | ITM (higher below = "Deep ITM") | OTM |
| Strike ≈ Spot | ATM (closest strike to spot) | ATM |
| Strike > Spot | OTM (higher above = "Deep OTM") | ITM (higher above = "Deep ITM") |

Rule of thumb: for calls, all strikes below ATM are ITM, all above are OTM. For puts
it's the mirror image. Premiums always fall monotonically as you move from Deep ITM
→ ATM → Deep OTM (ITM strikes are always priced above OTM strikes of the same series).

---

## 2. Payoff Profiles — Buyer & Seller, Call & Put

### Formulas (P&L at/held-to expiry)

| Position | P&L Formula | Breakeven | Max Loss | Max Gain |
|---|---|---|---|---|
| **Long Call** (buy CE) | `Max[0,(Spot−Strike)] − Premium Paid` | `Strike + Premium Paid` | Premium paid (capped) | Unlimited |
| **Short Call** (sell/write CE) | `Premium Received − Max[0,(Spot−Strike)]` | `Strike + Premium Received` | Unlimited | Premium received (capped) |
| **Long Put** (buy PE) | `Max[0,(Strike−Spot)] − Premium Paid` | `Strike − Premium Paid` | Premium paid (capped) | Large (capped at Strike − Premium, since spot floors at 0) |
| **Short Put** (sell/write PE) | `Premium Received − Max[0,(Strike−Spot)]` | `Strike − Premium Received` | Large (down to Spot=0) | Premium received (capped) |

Key mechanics:
- The buyer's breakeven point is exactly the seller's "breakdown point" — same number, opposite meaning.
- Long option payoffs are asymmetric: capped loss, unbounded (or very large) gain.
- Short option payoffs are the mirror image: capped gain, unbounded (or very large) loss.
- P&L formulas above hold **only if held to expiry**. If squaring off mid-series, P&L is
  driven by the change in premium (i.e., by the Greeks), not by the expiry payoff formula.

### Decision table — market view → position

| Your View | Action | Position Name | Premium Cash Flow | Alternative |
|---|---|---|---|---|
| Bullish | Buy Call | Long Call | Pay | Buy futures/spot |
| Flat-to-Bullish | Sell Put | Short Put | Receive | Buy futures/spot |
| Flat-to-Bearish | Sell Call | Short Call | Receive | Sell futures |
| Bearish | Buy Put | Long Put | Pay | Sell futures |

**When each is appropriate:**
- **Long Call** — outright bullish, want defined/limited risk, willing to pay time value, expect a real directional move before expiry (not just IV expansion).
- **Short Call** — you believe price will stay flat or fall; want to harvest time decay; requires margin; unsuitable if you fear an upside surprise (unlimited risk).
- **Long Put** — outright bearish, defined risk; better than shorting futures when you fear a sharp adverse reversal (no MTM bleed beyond premium).
- **Short Put** — bullish-to-neutral, willing to collect premium and be "put" the downside risk; avoid before events/panic windows because "panic spreads faster than greed" — down-moves are faster/sharper than up-moves, so short puts get hurt quicker than short calls in the same %.

**Structural symmetry to remember:**
- Buyer's max loss = seller's max gain (and vice versa) for the same strike/expiry.
- Statistically, 2 of the 3 possible outcomes (flat, down, up) favor the option seller on a call, and 2 of 3 favor the seller on a put too — option selling has a natural (not guaranteed) statistical edge, offset by tail/unlimited-loss risk. "Option writers eat like a chicken but s**t like an elephant" (Nassim Taleb) — small steady gains, occasional catastrophic loss.

---

## 3. Strike Selection by Time-to-Expiry (Buying Options)

Buying naked options is not a single-dimension bet — the right strike depends on
**(a) how much time is left in the series and (b) how fast you expect the target move to play out.** Use this table before buying any option:

| Trade initiated | Target expected within | Best strike to buy |
|---|---|---|
| 1st half of series | Same day / very fast (news, results) | Far OTM (2–3 strikes from ATM) |
| 1st half of series | ~5 days | Far OTM (2 strikes from ATM) |
| 1st half of series | ~15 days | ATM or slightly OTM (≤1 strike away) |
| 1st half of series | ~25 days | Slightly ITM |
| 1st half of series | On expiry day | ITM |
| 2nd half of series | Same day | Far OTM (2–3 strikes away) |
| 2nd half of series | ~5 days | Slightly OTM (≤1 strike away) |
| 2nd half of series | ~10 days | Slightly ITM or ATM |
| 2nd half of series | On expiry day | ITM |

Rules of thumb embedded in this table:
- **Fast, sharp moves → buy far OTM** (max leverage from low delta + gamma acceleration; this is how 100%+ intraday option returns happen).
- **Slow grind over many days, especially late in series → buy ITM/ATM** — OTM options bleed theta faster than they gain from a slow move; buyers often lose money on far-OTM options even when direction is correct, simply because the move wasn't fast enough.
- Never buy OTM purely because premium is "cheap" — cheap premium creates an illusion of low risk; realistically the probability of losing 100% of that premium is high.
- Applies symmetrically to puts.

---

## 4. Option Greeks

### 4.1 Delta — sensitivity to underlying's direction

```
Expected change in premium = Delta × Points change in underlying
```

- Call delta ranges **0 to +1** (or 0 to 100). Put delta ranges **−1 to 0** (or −100 to 0).
- Delta is bounded because an option (derivative) can never move faster than its own underlying, and premium can never go negative.

| Moneyness | Call Delta (approx) | Put Delta (approx) |
|---|---|---|
| Deep ITM | +0.8 to +1.0 | −0.8 to −1.0 |
| Slightly ITM | +0.6 to +1.0 | −0.6 to −1.0 |
| ATM | +0.45 to +0.55 | −0.45 to −0.55 |
| Slightly OTM | +0.3 to +0.45 | −0.45 to −0.3 |
| Deep OTM | 0 to +0.3 | −0.3 to 0 |

**Delta is additive** across positions on the same underlying — sum position deltas
(lots × delta, negative for shorts) to get net directional exposure:
- 2 ATM long options (delta 0.5 each) ≈ 1 long futures lot (delta 1).
- Shorting a call flips the sign of its delta contribution (short call = negative delta); shorting a put flips to positive delta.
- Net delta = 0 across a combined position is called **Delta Neutral** — insensitive to small directional moves, but still exposed to Vega/Theta/Gamma.
- A deep ITM option (delta ≈1) behaves almost exactly like a futures contract for spot moves — useful as a lower-margin futures substitute, but only while it stays deep ITM (delta must be monitored) and only if liquid enough.

**Delta as probability**: Delta ≈ the market-implied probability the option expires ITM.
- Delta 0.30 ⇒ ~30% chance of expiring ITM (70% chance of expiring worthless) — a rational filter against buying cheap deep-OTM options with 2 days to expiry and a delta of ~0.1 (90% chance of a total loss).
- Conversely, shorting an option that already has delta near 1 (deep ITM) means the odds are already stacked against the seller — avoid writing deep ITM options expecting them to "come back OTM."

**Delta Acceleration stages** (delta vs. spot as option transitions moneyness):

| Stage | Moneyness transition | Delta behavior | Practical implication |
|---|---|---|---|
| Predevelopment | Deep OTM → OTM | Stays flat near 0 | Big % moves possible but need a huge underlying move; avoid buying, decent for selling (theta favors seller) |
| Takeoff & Acceleration | OTM → ATM | Rises fastest, most convex | **Best risk/reward zone to buy** — biggest % gains per point of underlying move; also biggest % risk |
| (ATM itself) | — | Hits ~0.5 | Most sensitive strike; moves even on small underlying changes; expensive; do not short casually |
| Stabilization | ATM → ITM → Deep ITM | Flattens out near 1 | Behaves like the underlying itself (like futures); "safe" directional proxy |

### 4.2 Gamma — rate of change of delta (2nd derivative of premium)

```
Change in Delta = Gamma × Change in underlying
New Delta = Old Delta + (Gamma × Δunderlying)
```

- Gamma is **always positive** for both calls and puts (unlike delta). Long options = "long gamma"; short options = "short gamma."
- **Gamma peaks at ATM** and is low for both deep ITM and deep OTM strikes — ATM options are most sensitive to changes in the underlying; OTM/ITM deltas react "slowly."
- **Gamma vs. time to expiry**: as expiry approaches, ATM gamma spikes sharply higher, while ITM/OTM gamma race toward zero. This means the closer to expiry, the more dangerous a short ATM position becomes (its delta — and therefore directional exposure — can swing violently for even small spot moves).
- **Gamma risk / position sizing trap**: a trader who sizes a short-option position by "number of lots vs. margin budget" can silently blow through their intended risk limit as gamma inflates delta against them when the market moves. Always recompute **position delta = Σ(lots × delta)** after a move, not just at trade inception.
- **Practical rules**:
  - Never short ATM options, and especially never short ATM options close to expiry (highest gamma risk).
  - OTM options (held short to expiry, expecting them to expire worthless) are the safer gamma profile for sellers.
  - Long-gamma positions (any long option) benefit from acceleration in the trader's favor when right; short-gamma positions get squeezed harder the more wrong they are.

### 4.3 Theta — time decay

```
New Premium ≈ Old Premium − |Theta| × days elapsed  (all else equal)
```

- Theta is expressed as points lost per day; conventionally shown negative for long positions (buyer bleeds daily) and positive for short positions (seller earns daily).
- **Decay curve shape is non-linear**: decay is slow when there are many days to expiry, and **accelerates sharply in the final 1–2 weeks** ("time decay curve" — a slow-then-steep drop, not a straight line).
- **Theta favors the option seller** — it is the seller's structural edge for holding to expiry.
- Trade-off for sellers:
  - **Sell early in the series (far from expiry)**: pocket a bigger absolute premium (more time value), but the daily decay rate is slow — takes longer to realize the gain and more days of directional risk exposure.
  - **Sell close to expiry**: premium collected is small (little time value left), but decay is fast — most of the "professional" premium-selling approach in this playbook favors selling **5–7 days before expiry** to let theta work hardest while limiting the exposure window.
- Buyers should recognize: every day held is a fixed, accelerating cost — do not buy options and "just hold" without a thesis on why the move happens soon.

### 4.4 Vega — sensitivity to implied volatility (IV)

```
Change in Premium ≈ Vega × (Change in IV, in percentage points)
```

- Vega is **always positive** for both calls and puts — rising IV inflates premiums; falling IV deflates them, regardless of direction.
- **Effect of Vega is largest early in the series (many days to expiry)** and shrinks as expiry nears — a 15%→30% IV jump moves a 30-day option ~95%, but the same jump moves a 5-day option only ~47%.
- OTM options are proportionally most sensitive to Vega — a spike in IV can keep an OTM option's premium elevated (and delta non-zero) even when the underlying itself has moved against it. Historical case: on 24-Aug-2015 Nifty fell 4.9% but far OTM calls still rose 50–80% in premium, purely because India VIX spiked 64% that day (Vega effect overwhelmed the (small) Delta effect on those low-delta strikes).
- **Practical rule**: buy options when you expect IV to rise; sell/write options when you expect IV to fall or is already elevated. Never evaluate a long-option trade purely on direction — a correct direction call can still lose money if IV collapses simultaneously (classic post-event "IV crush").

### 4.5 Greek cross-interactions — checklist before any option trade

1. What is my **directional (Delta)** exposure, net of all legs?
2. What is my **Gamma** exposure — is my delta at risk of blowing out against me on a fast move (especially if short and near expiry)?
3. What is my **Theta** — is time decay working for me (short) or against me (long), and how fast does it accelerate from here to expiry?
4. What is my **Vega** — do I expect IV to rise or fall over the holding period, and does that help or hurt this position?
5. Is there a scheduled event (results, RBI policy, election) inside my holding window that could spike IV or Delta simultaneously?

---

## 5. Volatility

### 5.1 What volatility is

Volatility = standard deviation (SD) of returns = a statistical measure of dispersion/risk,
**not** simply "how much the market moves up and down." A stock with SD 45% is riskier
(wider dispersion of likely outcomes) than one with SD 25%, independent of direction.

### 5.2 Calculating historical volatility (from price data)

1. Download daily closing prices.
2. Compute daily **log returns**: `Return = LN(Today's Price / Yesterday's Price)`.
3. Compute `STDEV()` of the daily log returns → this is **daily volatility**.
4. Annualize: `Annual Volatility = Daily Volatility × SQRT(365)` (or SQRT(252) for trading days).
5. To go the other way: `Daily Volatility = Annual Volatility / SQRT(365 or 252)`.
6. To scale to any holding period *t* (in days): `Period Volatility = Daily Volatility × SQRT(t)`.

### 5.3 Normal distribution & range estimation

Daily/periodic returns of stocks and indices are approximately **normally distributed**
(bell curve) around a mean. Standard deviation bands:

| Band | % of outcomes contained | Practical read |
|---|---|---|
| ±1 SD | 68% | "Likely" range |
| ±2 SD | 95% | "Very likely" range |
| ±3 SD | 99.7% | Extreme; beyond this = **Black Swan** territory (rare, non-zero probability) |

Range formula for price *t* days/years ahead:

```
Upper Range = Spot × exp(Mean_period + SD_period)
Lower Range = Spot × exp(Mean_period − SD_period)
```
(use `Mean_period = daily mean × t`, `SD_period = daily SD × SQRT(t)`; multiply SD by 1, 2,
or 3 for the desired confidence band.)

### 5.4 Volatility types

| Type | What it is | Use |
|---|---|---|
| **Historical Volatility** | SD of past realized returns | Quick "back of envelope" input to a pricing calculator |
| **Forecasted Volatility** | Modeled prediction of future volatility (e.g. GARCH(1,1)/(1,2)) | Statistical edge over guessing |
| **Implied Volatility (IV)** | Volatility implied by current market option prices; the market's consensus expectation | Most valuable — directly priced into premiums; check via option chain |
| **Realized Volatility** | Actual volatility that occurred over a completed period (hindsight) | Benchmark to judge whether today's IV is rich or cheap vs. history |

- **India VIX** = NSE's official implied-volatility index, computed from the Nifty options order book (best bid/ask of near + next month contracts); represents expected annualized volatility over the next 30 calendar days. Often called the "Fear Index" — rising VIX ⇒ rising uncertainty, be careful of steep moves in either direction.
- You do **not** need a directional view to trade options — a volatility view (IV rising/falling) is a legitimate, separate edge; many professional options traders trade volatility, not direction.

### 5.5 Volatility Smile

For the same underlying and expiry, IV is **not** uniform across strikes — it is lowest at
ATM and rises as you move further OTM/ITM in either direction, producing a "smile" shape
when plotted (IV on Y-axis, strike on X-axis). Practical implication: don't assume flat IV
across a chain when pricing spreads — far OTM legs will carry richer IV than ATM legs.

### 5.6 Volatility Cone — IV percentile logic (buy vs. sell premium)

Method: for each expiry window (10, 20, 30, 45, 60, 90 days), calculate the historical
distribution (max, +2SD, +1SD, mean, −1SD, −2SD, min) of *realized* volatility over many
past expiries. Plot this as a "cone." Then overlay **today's implied volatility** for each
strike/expiry on the same cone.

**Decision rule:**
- IV plotting near/above **+2 SD** of its historical cone for that time-to-expiry ⇒ option is trading **rich/costly** ⇒ favor **selling/writing** (shorting volatility), expecting IV to mean-revert down.
- IV plotting near/below **−2 SD** ⇒ option is trading **cheap** ⇒ favor **buying** (going long volatility).
- Applies across different strikes of the same security AND across different securities (e.g., compare Nifty ATM IV of ~25% vs. SBI ATM IV of ~52% — the cone tells you which one is actually "expensive" relative to its own history, not just which number is bigger).
- Only apply this to **liquid** contracts — illiquid strikes distort IV readings.

This is the closest analogue in this source material to an "IV percentile" signal: **high
IV-vs-own-history → sell premium; low IV-vs-own-history → buy premium.**

---

## 6. Black-Scholes Inputs & Put-Call Parity

### 6.1 Black-Scholes model — what goes in / what comes out

Treat it as a black box:

**Inputs:**
1. Spot price (use Futures price instead if the option's underlying is a futures contract — e.g., most commodity/currency options; use Spot for equity options)
2. Strike price
3. Interest rate — risk-free rate, conventionally the RBI 91-day T-bill rate
4. Implied volatility — pull from the option chain / IV surface
5. Dividend per share (only if underlying goes ex-dividend before expiry)
6. Number of calendar days to expiry

**Outputs:**
- Theoretical premium (call and put)
- All Greeks: Delta, Gamma, Theta, Vega (and higher-order Greeks like "Speed"/Gamma-of-Gamma, generally not needed outside institutional books)

**What actually matters for premium magnitude, ranked by typical impact:** time to
expiry and IV move the needle the most (see Theta/Vega sections); interest rate and
dividend inputs are comparatively minor for short-dated equity/index options but should
still be fed correctly, especially dividend for stock options with an ex-date inside the
expiry window.

Model outputs are theoretical and can diverge slightly from live market premiums due to
input/assumption error — treat BS output as a strong reference, not gospel truth.

### 6.2 Put-Call Parity (PCP)

```
Put + Spot = PV(Strike) + Call
≈ Put + Spot = Strike + Call   (approximation ignoring discounting over short tenors)
```

Holds when: both are ATM, European, same expiry, held to expiry. Logic check: holding
(Put + Stock) must have an identical payoff to holding (Call + Cash equal to strike),
whichever direction the underlying moves — verify any options-arbitrage or synthetic
position idea against this identity before trusting it.

---

## 7. Strike Selection & Discipline for Writing (Selling) Options

A systematic premium-selling checklist (SD-based strike selection), derived from the
"select strikes 1 SD away and short them" approach:

1. Compute daily mean and daily SD (annualized as needed) for the underlying.
2. Scale to the number of trading days left to expiry: `Period SD = Daily SD × SQRT(days_to_expiry)`.
3. Compute the 1-SD (or 2-SD, for more safety) upper/lower price band for that expiry window.
4. **Sell calls above the upper band** and/or **sell puts below the lower band** — both are statistically likely (68% / 95% confidence, respectively) to expire worthless.
5. **Do not buy** options beyond that band expecting them to land ITM — the odds are against you.

Additional operating rules distilled from the professional-writer walk-through:

- **Prefer writing calls over writing puts.** Panic/down-moves happen faster than
  greed/up-moves — a written OTM put can transition to ATM/ITM faster than a symmetric
  written OTM call, all else equal.
- **Timing**: prefer writing in the **last week before expiry** (e.g., 5–7 days out) so theta
  decay is working hardest and the SD-implied range (scaled by fewer remaining days) is
  narrower, improving win-probability, even though absolute premium collected is lower.
- **SD choice trade-off**: 1 SD away = higher premium, lower confidence (68%); 2 SD away =
  lower premium, higher confidence (95%). Use 2 SD when writing earlier in the series (more
  days = more uncertainty to buffer); 1 SD is acceptable only in the final days.
- **Avoid writing options into scheduled events** (monetary policy, results, elections) —
  event-driven IV/Delta spikes can blow through your SD assumptions, which are built on
  "normal," not event-elevated, volatility.
- **Never write naked options with more than ~15 days to expiry** as a rule of thumb —
  too much time for the underlying to travel against the position.
- **Exit discipline**: get out the moment a written option transitions from OTM to ATM —
  don't wait for it to become a problem.
- **Track markets continuously while short** — awareness is the only mitigant against
  the low-probability, high-severity "Black Swan" tail; the strategy's edge is real but
  a single bad tail event can erase many months of collected premium.
- **Minimize expenses (brokerage/slippage)** — trading larger size per trade dilutes
  fixed per-lot costs; keep it as a smaller share of collected premium.
- **Capital allocation discipline (one worked example from the source)**: cap short-term/
  options-writing exposure to a small slice of total capital (e.g., no more than ~35% of the
  short-term trading bucket, itself a minority of total capital — netting to roughly
  single-digit % of overall capital at risk per strategy at any time). Diversify across
  a handful of liquid names/indices rather than concentrating.

### Volatility-based stop-loss (for directional futures/option trades)

Fixed % stop-losses ignore a stock's natural daily noise and get whipsawed. Instead:

```
Period Volatility = Daily Volatility × SQRT(holding_period_days)
Stop-Loss Price   = Entry Price × (1 − Period Volatility)   [for a long trade]
```

Compare the volatility-derived stop to your technical/chart-based stop; if the technical
stop sits **inside** the volatility-implied noise band, it is too tight and will likely
be triggered by noise rather than a genuine thesis failure — widen it (and re-check that
the reward-to-risk ratio, ideally ≥ 1.5, still holds at the wider stop).

---

## 8. Margin & Assignment Notes for Sellers

- **Buyers** pay premium upfront; that premium is their entire capital at risk. No margin required to buy.
- **Sellers/writers** face theoretically unlimited risk (short call) or very large risk (short put, floor at spot = 0), so exchanges require **margin** — broadly comparable in magnitude to the margin required for an equivalent futures position (check via SPAN/margin calculator; do not assume selling one option lot is materially "lighter" than a futures lot).
- **Assignment**: irrelevant in the traditional (early-exercise) sense for Indian markets — **all NSE options are European and cash-settled**, so there is no early-assignment risk; settlement (and the seller's payout obligation) crystallizes only at expiry against the closing spot reference. The seller's only real-time risk driver is mark-to-market on the margin account as the position's Greeks move against them.
- Because sellers carry gamma risk (Section 4.2), the effective directional exposure of a short-options book can exceed what raw lot-count budgeting implies — always re-derive **position delta** after every material spot move, not just at entry, when managing margin/risk limits.
- Deep ITM long options can be used as a lower-margin proxy for a futures position (delta ≈ 1) — useful for capital efficiency, but only while delta stays near 1 and liquidity is adequate; this is a long-side technique, not relevant to margin-constrained short sellers.

---

## 9. Quick-Reference Checklists

**Before buying any option:**
- [ ] What's my directional thesis and expected magnitude of move?
- [ ] How many days to expiry, and which half of the series am I in?
- [ ] How fast do I expect the target to play out? → use the Section 3 table to pick ITM/ATM/OTM.
- [ ] Do I expect IV to rise or fall over the holding period? (Buying into falling/crushing IV is a headwind even if direction is right.)
- [ ] What is delta telling me about implied probability of finishing ITM — am I paying for a lottery ticket?
- [ ] Defined stop (premium level or thesis-invalidation level) and target set before entry.

**Before selling/writing any option:**
- [ ] Where does today's IV sit vs. its historical cone for this time-to-expiry — rich enough to justify selling?
- [ ] Is there an event inside the holding window? If yes, reconsider or size down.
- [ ] Strike chosen via SD-band (1 SD near expiry, 2 SD if further out)?
- [ ] Margin available and position-delta (not just lot count) within risk budget?
- [ ] Exit plan if option transitions OTM → ATM?
- [ ] Capital allocated to this trade within the pre-defined % of total capital?

**Position-level, at any time:**
- [ ] Net position Delta (sum of lots × delta across all legs)?
- [ ] Net Gamma exposure — could a fast move blow the effective delta budget?
- [ ] Net Theta — is time working for or against the book overall?
- [ ] Net Vega — is the book exposed to an IV event in either direction?

---

## Opinion protocol

When the strategist (this agent) expresses a view on NSE index/stock options, it must be
structured as follows so it is auditable and executable:

1. **Underlying & instrument** — index or stock, and whether the view is expressed via
   options, futures, or spot (state why options specifically, if chosen — e.g., "defined
   risk preferred over futures due to reversal risk").
2. **Structure** — exact position(s): e.g., "Long Call," "Short Put," "Bull Call Spread,"
   naming every leg. No unnamed/implicit positions.
3. **Strikes & expiry** — exact strike(s) and expiry date, justified against:
   - Section 3's time-to-expiry/target-speed table (moneyness choice), and
   - Section 6.2/5.6 IV cone context (is this strike rich or cheap right now).
4. **Max loss** — computed number (per lot and notionally), using the payoff formulas
   in Section 2. For short/naked legs with theoretically unlimited loss, state the
   practical worst-case assumption used (e.g., an N-SD move) and the hard exit rule.
5. **Max gain** — computed number or "unlimited" (state the realistic target, not just
   the theoretical cap, referencing the target price/move thesis).
6. **Breakeven(s)** — exact price level(s) using Section 2 formulas.
7. **Greeks exposure summary** — net Delta, Gamma, Theta, Vega of the full structure
   (not just the dominant leg), each with a one-line practical read (e.g., "Vega +120:
   position benefits if IV rises before expiry; Theta −45/day: costs ~45 pts/day of
   inaction").
8. **IV context** — current IV of the strikes involved vs. their historical
   cone/percentile (rich/cheap/neutral), and whether the trade is direction-driven,
   volatility-driven, or both.
9. **Time horizon** — expected holding period and the specific trigger for exit
   (target hit, stop hit, time-based exit such as "before an event," or Greek-based
   exit such as "close if option transitions OTM→ATM").
10. **Confidence (0–100)** — a single number reflecting conviction, calibrated as:
    - Below 40: thesis is speculative / low-probability (e.g., low-delta OTM buy) — size small.
    - 40–60: balanced, data-supported view but meaningful uncertainty (e.g., typical
      directional option buy on a technical setup).
    - 60–80: high-conviction, backed by multiple confirming signals (e.g., SD-band
      premium sale with no event risk, or fundamentals + technicals aligned).
    - Above 80: reserved for near-mechanical, well-precedented setups (e.g., selling
      deep-OTM premium far outside a 2-SD band with no event in window and ample liquidity).
    - Confidence must be explicitly reconciled with the max-loss/max-gain asymmetry —
      a high-confidence label on an unlimited-loss short position still requires the
      hard exit rule from point 4 to be stated.

Every opinion must include all ten points; an opinion missing max loss, breakeven, or
the Greeks summary is incomplete and should not be presented as final.
