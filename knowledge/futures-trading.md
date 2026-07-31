# NSE Futures Trading — Playbook

Source: Zerodha Varsity Module 4 (Futures Trading). This is a decision playbook for an AI
trading agent, not a summary — every rule below should be directly usable to size a trade,
compute a margin, read an OI print, or write an opinion.

## 1. Contract mechanics — the fixed facts

A futures contract is a standardized, exchange-traded, cash-settled (for equity/index futures
in India) agreement to transact an underlying at a future date, at a price fixed today.

- **Lot size** — minimum (and only multiple) tradeable quantity. Fixed per contract, exchange-set.
  You cannot trade odd quantities.
- **Contract Value (CV)** = Lot Size × Futures Price. This is the notional exposure, not the cash you pay.
- **Expiry** — last Thursday of the month (India convention). At any time, exactly 3 contracts
  trade per underlying:
  - **Near/current month** — expires this month
  - **Mid month** — expires next month
  - **Far month** — expires the month after
  - Current month price < mid month price < far month price, *normally* (futures at premium
    increases with time to expiry — see Section 4). On expiry day, the current-month contract
    is removed and a new far-month contract is introduced; mid → current, far → mid.
- **Settlement**: equity/index futures are cash-settled. If a position is not squared off before
  expiry, the exchange auto-squares it off at the closing spot price (spot and futures always
  converge exactly at expiry — this is structural, not a forecast).
- **Rollover**: to keep a directional view alive beyond current-month expiry, square off the
  current-month contract near expiry and open the same position in the next-month contract.
  Rollover % (how much OI is being carried to the next series) is a sentiment gauge, not a hard
  signal — high long rollover is read as bullish, high short rollover as bearish, but treat as soft context only.
- **Liquidity check before any trade**: use impact cost, not just OI/volume.
  - Impact cost = (best-ask − best-bid) / [(best-ask + best-bid)/2], expressed as %.
  - This is the cost of an instant round-trip (buy at ask, sell at bid) and estimates slippage
    on a market order.
  - Benchmark: Nifty futures ≈ 0.0125% (extremely liquid). Anything materially above that,
    especially >0.1-0.3%, means market orders will bleed money — prefer limit orders, and size
    down. Never route a large market order into a name with wide bid-ask/thin depth.

## 2. Margin & M2M — the daily cash cycle

### 2.1 Margin composition

```
Initial Margin (IM) = SPAN Margin + Exposure Margin
```

- **SPAN Margin** — exchange-mandated minimum, computed by an algorithm keyed heavily to the
  underlying's *volatility* (higher expected volatility → higher SPAN %). Also called the
  **Maintenance Margin** — this is the floor that must never be breached while the position is open.
- **Exposure Margin** — additional cushion for adverse M2M moves, broker/exchange-set, typically
  ~4–5% of contract value (can be higher for volatile/single names; index futures overall
  margin is materially lower, ~12–15%, vs individual stock futures which can run 15–60%
  depending on volatility).
- Both SPAN and Exposure are quoted as a **% of Contract Value**, and CV moves every day with
  the futures price — so **margin requirement changes daily even with no new trade.**
- Margin must be maintained for as long as the position (long or short) is open — same
  requirement for buyer and seller.

### 2.2 Mark-to-Market (M2M) — worked mechanics

Every day the position is open, P&L is settled in cash against the *previous close* (not the
original entry price). This resets the "cost basis" to the prior close each night.

```
Day 1 M2M   = (Day-1 Close − Entry Price) × Lot Size     [credited/debited same evening]
Day N M2M   = (Day-N Close − Day(N-1) Close) × Lot Size
Exit-day M2M = (Exit Price − Prior Close) × Lot Size
```

Sum of all daily M2M = (Exit Price − Entry Price) × Lot Size = total P&L. Four equivalent ways
to reconcile P&L on a closed trade:
1. Sum of all M2M entries
2. Final cash released − Initial margin blocked
3. Final Contract Value − Initial Contract Value
4. (Exit price − Entry price) × Lot size

**Margin call mechanic**: each day, compare `Cash Balance (deposit + cumulative M2M)` against
`current Total Margin requirement (SPAN + Exposure, recomputed off today's CV)`.
- If Cash Balance ≥ SPAN alone → generally fine, no forced action, even if it dips below
  SPAN+Exposure (brokers usually tolerate down to SPAN).
- If Cash Balance < SPAN → **margin call**: broker demands top-up immediately; failing that,
  broker force-closes the position (some brokers cut in real time, no call given).
- Rule of thumb for the agent: treat "cash balance vs SPAN" as the hard kill-line for any open
  futures position; treat "cash balance vs SPAN+Exposure" as the soft warning line.

**Worked example (HDFC Bank, long, lot 250, buy ₹938.7, SPAN 7.5%, Exposure 5%):**
- Day 0: CV = 250×938.7 = ₹234,675. IM = 12.5% of CV = ₹29,334.
- A single bad day: price falls to ₹880 (from a prior close of 955): M2M loss = (955−880)×250 =
  ₹18,750. New CV = 250×880 = ₹220,000 → SPAN = ₹16,500, Exposure = ₹11,000, Total margin =
  ₹27,500. If cash balance after the loss (₹14,659 in the worked case) < SPAN (₹16,500) →
  margin call triggers.

### 2.3 Why margins exist

Margin + daily M2M is the exchange's mechanism to eliminate counterparty default risk (the
central weakness of OTC forwards). Practical implication: **never treat "margin available" as
"safe to hold"** — margin is a % of a moving contract value; a string of adverse M2M days can
force liquidation well before a stop-loss level is hit if the account is thinly capitalized.

### 2.4 Product type ↔ margin tradeoff (more risk info disclosed → lower margin)

| Product | Info given to RMS | Relative margin | Use when |
|---|---|---|---|
| NRML | None (duration unknown, no SL) | Highest (full SPAN+Exposure) | Carrying position overnight/multi-day |
| MIS | Intraday only | Lower than NRML | Pure intraday, no SL specified |
| CO (Cover Order) | Intraday + stoploss | Lower than MIS | Intraday with a firm SL |
| BO (Bracket Order) | Intraday + SL + target (+ optional trailing SL) | Same as CO (target doesn't affect risk, so no extra margin benefit) | Intraday with SL, target, and optional trailing |

Calendar spreads (simultaneous long+short, same underlying, different expiries) also get large
margin relief because net directional risk is near zero — see Section 5.

## 3. Leverage — why it cuts both ways

```
Leverage = Contract Value / Margin Required
Breakeven-wipeout move (%) = 1 / Leverage
```

- Worked example: TCS, CV ₹295,250, Margin ₹41,335 → Leverage = 7.14x. A 14% adverse move
  (1/7.14) wipes out the entire margin. At 42x leverage, a mere 2.3% adverse move wipes out
  the margin (and, symmetrically, a 2.3% favorable move roughly doubles it).
- **Rule of thumb from the source material**: keep leverage around 1:10 to 1:12; avoid going
  materially higher. Higher leverage = higher risk of ruin for the same conviction level, not
  "free" extra return.
- Leverage explains why futures returns can look explosive vs spot for the identical price
  move (worked example: same ₹2362→₹2519 TCS move gave 5.79% spot return over 9 days vs 47%
  futures return on margin, annualizing to 235% vs 1925% — the move is identical, only the
  base capital differs).
- **Payoff is linear**: P&L = (Exit − Entry) × Lot Size × Number of lots, symmetric in both
  directions, unbounded loss potential on the wrong side (particularly dangerous when short,
  where theoretical upside/loss is unbounded). Futures is a zero-sum instrument — no value is
  created, money simply transfers from the losing side to the winning side. This is a hint
  that a directional futures trade should never be evaluated purely on expected profit; always
  size against max loss.

### 3.1 Position-sizing formula for the agent

Given available capital `C` and a decision to risk fraction `r` of it on one futures name:
```
Max margin to deploy = r × C
Lots affordable       = floor(Max margin to deploy / Margin per lot)
Effective leverage    = (Lots × Contract Value per lot) / (Lots × Margin per lot)
Capital at risk to stop-loss = Lots × Lot Size × |Entry − Stop|
```
Never size lots off "how much capital I have" divided by "contract value" — always divide by
**margin required**, and separately verify the resulting capital-at-risk-to-stop is inside the
agent's per-trade risk budget (independent of what leverage allows).

## 4. Futures pricing, fair value, and premium/discount

### 4.1 The pricing formula (cost-of-carry model)

```
Futures Price = Spot Price × [1 + rf × (x/365) − d]
```
where `rf` = annualized risk-free rate (proxy: 91-day T-bill), `x` = days to expiry,
`d` = expected dividend yield (as a fraction) over the holding period to expiry.

- This is the **theoretical fair value**. The actual traded price is the **market price**;
  the two usually differ slightly due to transaction costs, taxes, and margin funding costs,
  and the gap tends to widen as `x` (days to expiry) grows.
- **Basis / Spread** = Futures Price − Spot Price. Structurally: as expiry approaches, `x→0`,
  so the fair-value basis shrinks to zero — **futures and spot must converge exactly at
  expiry**, regardless of prior premium/discount. This convergence is a certainty, not a
  probabilistic edge, and is the foundation of all cash-and-carry / basis trades.

### 4.2 Premium / Discount interpretation

| Condition | Equity term | Commodity term | Read |
|---|---|---|---|
| Futures price > Spot price | Premium | Contango | Normal/default state (positive cost of carry) |
| Futures price < Spot price | Discount | Backwardation | Short-term supply/demand imbalance, or strong bearish pressure/high dividend expectation pulling futures below spot |

- A large, growing premium into expiry is normal cost-of-carry, **not** inherently bullish.
- A discount (or a shrinking/negative premium) signals near-term selling pressure in the
  futures relative to spot, or dividend effects — treat as a flow/positioning signal, and
  combine with OI (Section 6) before drawing a directional conclusion.
- If market price deviates significantly from fair value (mispricing beyond normal cost/tax
  frictions), that gap is itself the trade — see Cash & Carry Arbitrage below.

### 4.3 Cash & Carry Arbitrage (spot-futures mispricing)

Rule: **buy the cheap side, sell the expensive side**, relative to fair value; the position is
market-neutral because convergence at expiry is guaranteed.

Worked example: Wipro spot ₹653, fair value of current-month future ≈ ₹658 (rf 8.35%, x=30,
d=0), but market trades the future at ₹700 (way rich to fair value).
```
Buy Wipro spot @ 653
Sell Wipro futures @ 700
Locked spread = 700 − 653 = 47 points, realized regardless of where spot/futures converge by expiry
```
Verify: at convergence values of 675 / 645 / 715, net P&L is +47 in every case (spot leg + futures leg cancel the direction, only the captured spread survives). Unwind both legs just before expiry.

## 5. Calendar spreads

A calendar spread trades the **basis between two expiries of the same underlying** rather than
a spot-vs-future basis. Mechanically: go long the contract trading cheap to its fair value,
short the contract trading rich to its fair value (or richer relative to the other leg).

Worked example: Wipro spot 653; current-month fair value 658 but trading at 700 (rich); mid-month fair value 663, trading at 665 (fair).
```
Sell current-month future @ 700
Buy mid-month future @ 665
Spread captured = 700 − 665 = 35 points
```
At three arbitrary convergence scenarios (660 / 690 / 725) net P&L is flat at +35 in every case
— the position is hedged against outright direction; the risk is basis/liquidity/execution
risk, not directional risk.

**Margin implication**: because the position is long one expiry and short another of the same
underlying, net directional risk is near zero, so **margin required is drastically lower** than
the sum of the two legs' standalone margins (worked example: ₹37,362 + ₹37,629 = ₹74,991
standalone vs ₹7,213 combined — over 90% margin relief). Only put on a calendar spread when a
genuine mispricing/basis opportunity exists — don't manufacture one for the margin benefit alone.

## 6. Hedging playbook

Two distinct risk types:
- **Unsystematic (company-specific) risk** — reduced by *diversification* (adding uncorrelated
  names). Research cited: diversification benefit largely exhausted beyond ~21 stocks.
- **Systematic (market-wide/macro) risk** — GDP growth, rates, inflation, fiscal deficit,
  geopolitics. Cannot be diversified away. This is what **hedging** (via futures) addresses.
  Diversify for unsystematic risk, hedge for systematic risk — they solve different problems.

### 6.1 Hedging a single stock position

If the futures contract for the exact stock exists, hedge by taking the exact opposite futures
position for the **same quantity as your spot holding**, rounded to lot size:
```
Long spot Qty shares  ⇄  Short futures, same Qty (in lot-size multiples), same underlying
```
This freezes P&L — net position becomes indifferent to price direction (worked example:
long 250 Infosys spot @ 2284, short 250 Infosys futures @ 2285 → net P&L stays ≈ +1 regardless
of whether Infosys goes to 2200, 2290, or 2500). Only works cleanly when:
1. The stock has a listed futures contract, and
2. Your spot position size is large enough to map to whole lots (a mismatch between spot qty
   and lot-size multiples breaks the hedge — you're left over/under-hedged on the remainder).

If either condition fails (no futures contract on the name, or position too small for even
1 lot), you cannot construct a clean single-stock futures hedge — that requires options instead
(out of scope here).

### 6.2 Beta — computing and interpreting

Beta (β) measures a stock's expected % move for a 1% move in the market index. Market index
beta is always exactly +1.

| Beta value | Interpretation |
|---|---|
| < 0 (e.g. −0.4) | Moves opposite to market; market +1% → stock ≈ −0.4% |
| = 0 | Independent of market (rare in practice) |
| 0 < β < 1 (e.g. 0.6) | "Low beta" — same direction, dampened move |
| β > 1 (e.g. 1.2) | "High beta" — same direction, amplified move |

**Computing beta in Excel/code**: regress daily stock returns (`y`) on daily index returns (`x`)
over a lookback window (source uses ~6 months of daily closes):
```
daily_return_t = (Close_t / Close_(t-1)) − 1
beta = SLOPE(known_y = stock_daily_returns, known_x = index_daily_returns)
```
This is just the OLS slope coefficient — for an agent, equivalent to
`beta = Cov(stock_returns, index_returns) / Var(index_returns)`.

### 6.3 Hedging a portfolio with index futures — full procedure

Use the index future (e.g. Nifty) because a diversified portfolio has already stripped out
unsystematic risk; systematic risk is best offset with an instrument that *is* the market.

**Step 1 — Portfolio beta** (weighted average of constituent betas):
```
weight_i        = investment_i / total_portfolio_value
weighted_beta_i = weight_i × beta_i
Portfolio Beta  = Σ weighted_beta_i
```

**Step 2 — Hedge value**:
```
Hedge Value = Portfolio Beta × Total Portfolio Value
```

**Step 3 — Number of lots to short**:
```
Contract Value per lot = Index Futures Price × Lot Size
Lots to short           = Hedge Value / Contract Value per lot
```
Round to the nearest whole lot — this is unavoidable, so a portfolio is essentially always
either **slightly under-hedged** (rounding down) or **slightly over-hedged** (rounding up); a
perfect hedge is generally not achievable. State which rounding direction was used when
reporting a hedge.

**Worked example**: 8-stock portfolio, total ₹800,000, Portfolio Beta = 1.223.
```
Hedge Value = 1.223 × 800,000 = ₹978,400
Nifty future @ 9025, lot 25 → Contract Value/lot = 225,625
Lots to short = 978,400 / 225,625 = 4.33 → short 4 or 5 lots
```
Verify effectiveness: if Nifty falls 5.5%, expected portfolio decline ≈ 5.5% × 1.223 = 6.78%
of ₹800,000 ≈ ₹54,240 loss; short futures position (4.33 lots) gains 4.33×25×(0.055×9025) ≈
₹54,125 — the two nearly cancel, confirming the hedge ratio is correctly sized.

**Hedging a stock with no listed futures contract**: compute hedge value the same way
(stock beta × investment value), then convert that hedge value into index-future lots exactly
as in Step 3 — you don't need the stock's own futures contract, just its beta.

**Limitation**: positions too small to map to even one index-future lot (e.g., ₹50,000–100,000
against a lot size worth several lakh) cannot be hedged with futures at all — that requires
options.

## 7. Open Interest (OI) analysis

**Definition**: OI = number of futures (or options) contracts currently outstanding (open) in
the market. Every contract has exactly one long and one short side; summed with sign (+1 long,
−1 short) across all participants, it always nets to zero — this is why derivatives are a
zero-sum market.

**Mechanics that move OI**:
- OI **increases** when a new contract is created (a new buyer and a new seller both enter fresh).
- OI **decreases** when an existing contract is closed out (an existing long and existing short
  both square off against each other).
- OI is **unchanged** when an open position is merely transferred from one party to another
  (e.g., A sells their long to B — no new contract created).
- Unlike Volume, OI is **not** discrete/reset daily — it's a running stock, not a daily flow.
  Volume resets to zero each day and only increases through the session; OI carries forward.
- Higher OI ⇒ more liquid market ⇒ easier entry/exit at competitive bid-ask.

### 7.1 Price + Volume interpretation table

| Price | Volume | Interpretation |
|---|---|---|
| Up | Up | Bullish (fresh buying driving move) |
| Down | Down | Bearish trend likely ending — expect reversal (longs quietly disengaging, not fresh selling) |
| Down | Up | Bearish (fresh selling driving move) |
| Up | Down | Bullish trend likely ending — expect reversal (buying interest fading) |

### 7.2 Price + OI interpretation table (core signal table)

| Price | OI | Interpretation |
|---|---|---|
| Increase | Increase | **Bullish** — new longs entering, trend has fresh conviction behind it |
| Decrease | Decrease | Bearish trend could be ending — expect reversal (**long unwinding**: longs exiting, not new shorts) |
| Decrease | Increase | **Bearish** — new shorts entering, fresh conviction behind the down-move |
| Increase | Decrease | Bullish trend could be ending — expect reversal (**short covering**: shorts buying back to exit, not new longs) |

Use this table as the primary OI heuristic: rising price + rising OI or falling price + rising
OI both indicate *fresh, convicted* positioning (continuation likely); falling OI in either
direction indicates unwinding/covering of existing positions (potential exhaustion/reversal),
not fresh conviction.

**Caution flag**: abnormally high OI accompanied by a rapid price move in either direction
signals excess leverage/euphoria has built up in the system — flag this as an elevated-risk /
crowded-trade condition. A small trigger in such conditions can cause outsized, fast unwinds
(cascading margin calls / forced liquidations). Treat "extreme OI + extreme recent price move"
as a volatility/reversal-risk warning, not as confirmation to add to the trade.

## Opinion protocol

Whenever this agent expresses a view that could be traded via NSE futures, structure the
opinion as follows — every field is mandatory, not optional color:

1. **Underlying & directional view** — instrument, bullish/bearish/neutral (e.g., spread), and
   the one-line thesis driving it.
2. **Instrument choice rationale — future vs. option**:
   - Prefer a **future** when: the view is a clean directional or relative-value (spread) call,
     the position needs to be held with linear, symmetric payoff, there's no need to cap
     downside via premium-paid-only structures, and the underlying's futures liquidity
     (impact cost) is acceptable.
   - Prefer an **option** instead when: max loss must be capped to a known premium, the view
     needs asymmetric payoff, the position is a hedge for a sub-lot-size exposure, or the
     name's futures margin/impact cost is prohibitive. If futures is chosen over options,
     state explicitly why the linear/unbounded-loss tradeoff is acceptable here.
   - Prefer a **calendar spread** when the view is specifically about the futures basis
     (mispricing between expiries) rather than the underlying's direction.
3. **Margin required** — SPAN + Exposure at current contract value, and which product type
   (NRML/MIS/CO/BO) the holding period implies, with the resulting margin figure.
4. **Max loss** — defined either by (a) a hard stop-loss level converted to ₹ via
   Lots × Lot Size × |Entry − Stop|, or (b) if unhedged/no stop, explicitly flag "unbounded
   downside — position must be actively monitored for margin calls," and give the price move
   (%) that would wipe the posted margin (`1/Leverage`).
5. **Invalidation** — the specific price level, OI/basis pattern, or event (e.g., basis flips
   from premium to discount, OI rises sharply against the position, expiry approaching without
   thesis playing out) that would make the agent exit or reverse the view, independent of the
   stop-loss level itself.
6. **Confidence (0–100)** — calibrated to: strength of the directional/OI/basis evidence,
   liquidity of the contract (impact cost), and how much of the thesis depends on assumptions
   (e.g., dividend estimate, rollover behavior) that could be wrong. State the number and the
   one or two biggest drivers of uncertainty behind it.
