# Risk & Psychology Playbook — Risk Officer Rulebook

Source: Zerodha Varsity Module 9 (Risk Management & Trading Psychology). This is not a
summary — it is an operating manual for the RISK OFFICER agent. Every number, formula,
and threshold below is either lifted directly from the source module or is a direct
mechanical derivation of it. Where the module gives a "thumb rule" instead of a hard
number, that rule is stated as the enforceable default. The Risk Officer's job is to apply
these rules mechanically to every proposed trade and to every state of the book — not to
re-derive first principles each time.

Core doctrine (Mark Douglas, cited in the source): **trading success is ~80% money
management, 20% strategy.** The Risk Officer therefore outranks the Strategy/Signal agent
on any conflict. A great setup with broken risk parameters is a VETO. A mediocre setup with
clean risk parameters is a PASS (subject to strategy sign-off).

---

## 1. Risk taxonomy — what you're actually managing

- **Unsystematic (specific) risk** — risk specific to one company (earnings, management
  fraud, competitive loss, margin compression). Evidence: Satyam dropped >90% in days while
  peers and the index barely moved — proof this risk is company-local.
  - **Mitigated by diversification.** Cannot be hedged away meaningfully; must be diluted
    by spreading capital across uncorrelated names.
- **Systematic (market) risk** — common macro/market factors: GDP de-growth, rate
  tightening, inflation, fiscal deficit, geopolitical shocks. Affects all holdings
  simultaneously regardless of diversification.
  - **Mitigated by hedging, not diversification.** Diversification and hedging are
    NOT interchangeable — do not let a diversified book substitute for a hedge, and do not
    treat a hedge as a substitute for proper diversification.
  - **No hedge is ever perfect.** Every position, hedged or not, retains a residual risk
    tail. Never report a "fully hedged" book as zero-risk.

### Diversification math (hard numbers)
- Unsystematic risk drops steeply as names are added and **flattens out by ~20–21
  stocks**; beyond ~21 names, additional diversification benefit is negligible.
  - **Rule: target book size 10–21 stocks.** A "well-diversified, high-conviction" book
    per the module is **10–15 stocks**. Below ~10, unsystematic risk is materially
    under-diversified. Above ~21, you are adding operational complexity for near-zero
    risk reduction — flag for consolidation.
- **Covariance selection rule:** portfolio managers actively prefer stocks with **negative
  or low covariance** to each other. Positive covariance among holdings means they fall
  together — this concentrates, not diversifies, risk. When screening a new candidate
  against the existing book, a high positive covariance/correlation with existing large
  positions is a diversification failure even if the book has 15+ names (correlated
  clusters behave like one position).

---

## 2. Portfolio math toolkit (formulas to preserve exactly)

### 2.1 Expected return
Single asset: expected return is the trader's own probabilistic forecast, not a guarantee.

Portfolio (weights sum to 100%):
```
E(Rp) = W1*R1 + W2*R2 + W3*R3 + ... + Wn*Rn
```
Annualized version used for planning: `Rt(annual, stock i) = avg(daily return_i) * 252`,
then weight and sum as above.

### 2.2 Variance (single stock, risk measure)
```
σ² = Σ (X - μ)² / N
```
Where X = daily return, μ = average daily return, N = number of observations.
`Standard Deviation = sqrt(Variance)`. Higher variance = higher risk. This is always
computed on a daily basis first, then annualized (see 2.6).

### 2.3 Covariance (two stocks)
```
Cov(S1,S2) = Σ [(Rt_S1 - AvgRt_S1) * (Rt_S2 - AvgRt_S2)] / (n - 1)
```
- Positive covariance → returns move together (bad for diversification).
- Negative covariance → returns move oppositely (good — counterbalances the book).
- Covariance of a stock with itself = its variance.

### 2.4 Correlation (normalizes covariance to −1..+1)
```
Correlation(x,y) = Cov(x,y) / (σx * σy)
```
Use correlation, not raw covariance, to judge "how tightly" two names move together —
covariance's magnitude alone is not interpretable.

### 2.5 Variance-Covariance matrix (k stocks, n observations)
```
VCV = (Xᵀ · X) / n
```
Where X is the n×k **excess return matrix** (daily return minus that stock's own average
return, for every stock, every day). Result is a k×k matrix; the diagonal holds each
stock's variance, off-diagonal cells hold pairwise covariances. Divide element-wise by the
outer product of the standard-deviation vector (`SD · SDᵀ`) to get the **Correlation
Matrix** (diagonal = 1, symmetric about the diagonal).

### 2.6 Portfolio variance (the number that actually matters)
```
Portfolio Variance = sqrt( Transpose(Wt·SD) · CorrelationMatrix · (Wt·SD) )
```
Where `Wt·SD` is the vector of each stock's (weight × its own standard deviation). This is
a 3-step matrix operation: (1) transpose(Wt·SD) × CorrelationMatrix → row vector; (2) that
row vector × Wt·SD → scalar; (3) sqrt of the scalar = portfolio variance (= portfolio
1-standard-deviation risk).
- **Sanity check the module validates:** compute the portfolio's own daily return time
  series (weight-blended), take `STDEV()` of that series directly — it must equal the
  matrix-derived portfolio variance. If a portfolio-risk number can't be reproduced this
  simpler way, distrust the matrix computation.

### 2.7 Annualizing
```
Annual portfolio variance = daily portfolio variance * sqrt(252)
Annual portfolio return   = Σ (Wi * daily_avg_return_i * 252)
```

### 2.8 Return range by confidence (normal-distribution assumption)
Annualized portfolio variance = **1 standard deviation** of return. Build the expected
range as `Expected Return ± k * Annual Variance`:

| Level | k (SD) | Confidence | Range formula |
|---|---|---|---|
| 1 | ×1 | 68% | E(Rp) ± 1·σ_annual |
| 2 | ×2 | 95% | E(Rp) ± 2·σ_annual |
| 3 | ×3 | 99% | E(Rp) ± 3·σ_annual |

Worked numbers from the module's 5-stock example (σ_annual = 17.64%, E(Rp)=55.15%):
1SD range 37.51%–72.79% (68%); 2SD range 19.87%–90.43% (95%); 3SD range 2.23%–108.07%
(99%). **Higher confidence always means a wider range, never a narrower one** — an agent
that reports a tighter range at higher confidence has a bug.
- Caveat the module states explicitly: a range computed off a short bull-market sample is
  positively biased. Never certify a range off less than ~1 year of daily data.

### 2.9 Portfolio optimization concepts
- **Minimum Variance Portfolio (MVP):** the weight combination that minimizes portfolio
  variance for a fixed set of names — this is the least risk achievable for that
  universe, full stop; it cannot be engineered lower without changing the constituents.
- **Maximum Return Portfolio:** the weight combination maximizing return for the same
  universe — carries the most risk.
- **Efficient Frontier:** for any fixed risk level, there exists a max-return and a
  min-return portfolio; only the max-return point at each risk level is "efficient." A
  proposed rebalancing that moves the book to a lower-return point at the same (or
  higher) risk is inefficient by definition — flag it.
- Practical takeaway for an automated desk: don't just size positions — periodically
  re-solve weights against the existing correlation matrix to stay near the frontier.

---

## 3. Value at Risk (VaR) — exact estimation procedure

VaR answers: "if a black-swan event hits tomorrow, what's the worst-case loss, and at what
confidence?" Procedure exactly as taught (a "quick and dirty" but validated method for a
buy-and-hold equity book):

1. **Build the portfolio's daily return series** (use the normalized equity-curve returns —
   blended, weight-adjusted daily returns of the whole book, not any single stock).
2. **Test for normality.** Compute bin width = `(max return − min return) / 25`, bucket the
   returns into a frequency histogram, plot it. Confirm it visually approximates a bell
   curve before proceeding — if it doesn't, the VaR/CVaR numbers below are not valid and
   must not be reported as such.
3. **Sort the return series** descending (best to worst).
4. **Take the last 95% of observations** (i.e., drop the worst 5% tail).
5. **Portfolio VaR (95% confidence) = the lowest value within that retained 95%.**
   Worked example: n=126 obs → 95% = 120 obs; VaR = −1.48%.
6. **CVaR (Conditional/Cumulative VaR) = average of the excluded worst 5%** (the tail
   beyond VaR). Worked example: average of the worst 6 of 126 obs = −2.39%.

Interpretation rules an agent must follow:
- VaR of −1.48% means: on 95% of days, the loss will not exceed 1.48% of book value. It
  is **not** a hard ceiling — losses beyond VaR happen ~5% of the time.
- CVaR is the expected loss *given* you're already in that worst 5% tail — this is the
  number to use for stress/circuit-breaker thresholds, not VaR itself, because VaR
  understates tail severity by construction.
- Recompute VaR/CVaR on a rolling basis (module recommends ≥1 year of data; the 126-day
  example is explicitly flagged as too short to be a production estimate) — never certify
  on <6 months of daily data, and prefer ≥252 observations.

---

## 4. Equity curve, drawdown & recovery math

- Normalize the book to a base of 100 for equity-curve tracking; daily portfolio change =
  sum of each stock's weight-scaled daily P&L compounding on itself (not on the original
  weight amount — each day's move compounds on the prior day's value per stock).
- **Recovery math (the loss-asymmetry rule):** a loss of `L%` requires a subsequent gain of
  `L / (1 - L)` to breakeven — not `L%`. This gap compounds violently:

| Loss taken | Gain required to recover |
|---|---|
| 5% | 5.3% |
| 10% | 11.1% |
| 20% | 25% |
| 33% | 50% |
| 50% | 100% |
| 60% | 150% |

- **"Recovery trauma" veto logic:** the deeper the drawdown, the more disproportionately
  hard the comeback — and the more a losing trader/agent is tempted to oversize the next
  trade to "catch up." This is precisely backwards. **A drawdown must trigger a
  size-DOWN, never a size-up.** Any thesis or sizing request that references "making back"
  a prior loss is an automatic bias-scan flag (see §6, Gambler's Fallacy / Recovery
  Trauma).
- Small accounts are most exposed to recovery trauma because the "boring" compounding
  path (e.g., 20%/year) feels unsatisfying, tempting outsized bets. Enforce sizing rules
  *more* strictly, not less, on smaller books.

---

## 5. Position sizing toolkit

Two independent choices compound together: (A) how you define available "equity capital,"
and (B) how you convert that equity into a trade size. Pick ONE equity model and at most
ONE-OR-TWO sizing techniques as standing policy — do not let the system silently mix
models trade-to-trade (module explicitly warns: 3 equity models × 3+ sizing techniques
produces materially different P&L paths for the identical signal).

### 5.1 Equity capital models (pick one, apply consistently)
- **Core Equity Model:** `New Equity = Old Equity − Capital deployed to the new trade.`
  Sequentially shrinks the base as positions stack. Conservative; simple; recommended
  default for a systematic desk because of its simplicity and because it can't
  double-count capital.
- **Total Equity Model:** `Equity = Free cash + Σ(margin blocked per open position) +
  Σ(P&L per open position, realized AND unrealized)`. Aggressive — counts floating,
  unrealized gains as usable capital ("counting chickens before they hatch"). **Not
  recommended** as the standing model; unrealized P&L can evaporate before it's ever
  spent.
- **Reduced Total Equity Model (recommended default):** `Equity = Free cash (after
  margin deductions for open positions) + only the LOCKED-IN profit on open positions`
  (i.e., profit protected by a trailing stop having been raised — never floating/mark-to-
  market P&L). This is the module's preferred model precisely because it *forces* the
  discipline of moving stops to lock in gains before that capital can be reused.

### 5.2 Sizing techniques
1. **Unit per fixed amount** (e.g., "1 lot per ₹100,000 of capital"). Simple but **ignores
   risk/volatility differences between instruments** — treats a 14%-annualized-vol index
   future identically to a 40%-vol single stock future. Also caps scalability (doubling
   position count requires doubling capital). Not recommended as sole method — acceptable
   only as a hard ceiling layered under a risk-based method.
2. **Percentage margin:** cap margin deployed per trade at X% of equity capital (e.g., 20%
   of ₹500,000 = ₹100,000 margin ceiling per trade). Equalizes capital-at-work per trade
   but **still ignores volatility** — two trades with the same margin can have very
   different risk.
3. **Percentage volatility (ATR-based):**
   ```
   Volatility budget (₹) = Volatility% * Equity Capital
   Shares = Volatility budget / ATR(14-day, or chosen lookback)
   ```
   Worked example: Equity ₹500,000, volatility cap 2% → budget ₹10,000; ATR=76 →
   shares = 10,000/76 ≈ 131 shares (~₹353,700 exposure at ₹2,700/share).
   - Also set a **portfolio-level volatility ceiling** (sum of ATR-based ₹-volatility
     across all open positions), e.g., 15% of capital. On ₹500,000 that is ₹75,000 of
     single-day adverse-move exposure if every position moves against you simultaneously
     — this number must be sized so it is emotionally/financially tolerable *before* it is
     adopted, not discovered after a bad day.
4. **Percentage risk (stop-loss based — this is the primary method the Risk Officer
   should enforce; see §7 Sizing formula).** Defines risk directly off the stop-loss
   distance rather than off margin or ATR.
5. **Kelly Criterion (edge-based sizing overlay, not a standalone method):**
   ```
   Kelly% = W - [(1 - W) / R]
   W = winning trades / total trades
   R = average gain of winners / average loss of losers
   ```
   Worked example: W=0.6, R=1.384 → Kelly% = 0.6 − (0.4/1.384) = 0.31 (31%).
   - **Full Kelly is too aggressive to deploy directly** — a system with a high Kelly% (say
     70%) still carries the corresponding probability of losing that much capital in one
     shot. **Rule: use fractional/scaled Kelly.** Set a hard ceiling for the technique
     (e.g., 5% of capital max exposure per trade), then scale actual exposure as
     `Ceiling * Kelly%`. Example: ceiling 5%, Kelly 31% → deploy 5% × 0.31/1.0... per the
     module's own worked logic: Kelly 30% → expose 1.5% (30% of the 5% ceiling); Kelly 70%
     → expose 3.5% (70% of the 5% ceiling). **Never accept a raw, unscaled Kelly% as the
     position size.**
   - Kelly requires a real trade-history sample (win rate + win/loss ratio) — do not
     apply it to a strategy with no live or backtested track record; fall back to
     percentage-risk sizing until a statistically meaningful sample exists.

---

## 6. Stop-loss, R:R and per-trade risk discipline

- **A trade without a predefined stop-loss is not a trade — it is speculation. Non-
  negotiable precondition.**
- **Hard cap: never risk more than 1–3% of capital on a single trade** (module's explicit
  professional-trader thumb rule). Treat 1.5% as the sane default; 3% as the absolute
  ceiling for a high-conviction setup; anything above 3% is an automatic VETO regardless
  of conviction.
- **Reward:Risk (R:R):** compute as `(Target − Entry) / (Entry − Stop)` for longs (invert
  for shorts). Module's own reference trade used R:R = 1.7 and called it "great for an
  intraday trade." **Minimum acceptable R:R threshold: 1.5:1**; treat anything below 1:1
  as an automatic VETO, and 1:1–1.5:1 as sub-par (allow only with an explicit override and
  a documented reason).
- Recompute the max-loss threshold and available lots **after every fill**, not once at
  the start of the day (module's own worked example: after the first Tata Motors lot, the
  next trade's max-loss threshold shrinks from ₹7,500 to ₹6,397.5 because capital
  deployed is deducted first). Sizing is sequential, not static.

---

## 7. Hedging decision rules

- Hedge to neutralize **systematic** risk exposure (market/macro beta), not to compensate
  for poor stock-picking (that's a diversification problem, not a hedging one).
- Diversification and hedging solve *different* problems — do not let a well-diversified
  book skip hedging discipline ahead of known macro/event risk (results, budget, Fed/RBI
  decisions, geopolitical flashpoints), and do not treat an options hedge as a reason to
  concentrate the book more aggressively.
- **No hedge is ever complete.** Any risk report that implies zero residual risk on a
  "hedged" position is wrong by definition — always carry a residual-risk line item.
- Practical trigger for the Risk Officer: when portfolio-level systematic exposure (beta-
  weighted net delta, or simply net directional exposure across correlated positions)
  exceeds the desk's risk budget ahead of a known event window, require a hedge
  (index futures/options) sized to offset the *systematic* component only — do not try to
  hedge away unsystematic/stock-specific risk with an index hedge; that is solved by
  trimming/diversifying the position itself.

---

## 8. Trading-psychology bias catalogue

Each bias below includes a one-line, mechanically-applicable detection test the Risk
Officer runs against the text of a proposed trade thesis (or the trader/agent's stated
reasoning). Any single hit is a flag; flags feed the Veto Protocol's bias-scan step.

| Bias | What it does | Detection test on the thesis text |
|---|---|---|
| **Gambler's Fallacy** | Believes a losing (or winning) streak is "due" to reverse on the next trade, independent of actual odds; drives size-up after losses ("recover my losses") or size-down after wins ("protect my streak"). | Flag if thesis references a prior win/loss **streak** as a reason to change size on *this* trade (e.g., "after N losses, due for a win," "let it ride since I'm up N in a row"). |
| **Illusion of Control** | Overloads charts with many indicators (Bollinger, Fibonacci, pivots, stochastic, ATR, etc.) to manufacture a false sense of mastery/certainty over outcome. | Flag if the thesis cites >3–4 technical indicators/tools as joint justification for a single directional call, or uses absolutist language ("will not go above X," "guaranteed to bounce"). |
| **Recency Bias** | Over-weights the most recent candle/news/event and discounts the broader/older, often more material, picture (e.g., one green candle overriding a corporate-governance red flag). | Flag if the thesis justifies a reversal/entry primarily by referencing only the **last 1–3 bars or the last news item**, while a material adverse fact from more than a few sessions back is absent from the reasoning. |
| **Anchoring Bias (Focalism)** | Fixates on the first price/number seen as "the right price," refusing to act as the market moves away from it, and missing the move entirely. | Flag if the thesis conditions entry on a specific historical reference price with no re-evaluation logic for why that level — versus the current level — remains valid ("waiting for it to come back to my price"). |
| **Functional Fixedness** | Assumes an object/resource (margin product type, capital bucket) can only be used the one conventional way, missing an available reconfiguration (e.g., NRML↔MIS margin conversion to free capital). | Flag if a trade is rejected purely for "insufficient margin" without checking whether existing positions' product type/margin allocation could be converted/freed first. |
| **Confirmation Bias** | Selectively seeks and assimilates only evidence that supports a pre-existing view; ignores or downplays contradicting news/data. | Flag if the thesis lists only supporting factors and contains **zero explicit contrary evidence or counter-argument** for a directional call. |
| **Attribution Bias** | Attributes losses to external factors (broker, system, "market manipulation") rather than to the trader's own analysis/decision. | Flag if a post-loss review attributes the loss to external/infrastructure causes without also stating what was wrong with the entry thesis or sizing itself. |
| **Recovery Trauma / Loss Aversion** (extension of §4) | After a drawdown, feels compelled to take a bigger, faster bet to "get back to even" rather than accept the slower, asymmetric math of recovery. | Flag if the sizing request for a trade is larger than the standing per-trade risk cap AND a recent drawdown/loss is referenced as part of the rationale. |
| **Overconfidence** (extension) | Assigns unjustifiably high conviction/probability to an outcome without a statistical/backtested basis, often used to justify oversized bets. | Flag if the thesis requests sizing above the standing risk cap (or invokes Kelly at more than the fractional ceiling) using conviction language ("sure thing," "can't lose") rather than a stated, sourced win-rate/edge. |
| **Hindsight Bias** (extension) | Retroactively treats a past outcome as if it had been obviously predictable, distorting the lessons drawn into the next thesis. | Flag if a post-trade note claims the outcome was "obvious in hindsight" without pointing to the specific ex-ante signal that was actually acted on at entry time. |
| **Bandwagon Effect** (extension) | Enters or sizes a trade because "everyone" (a WhatsApp group, social feed, crowd) is doing it, rather than the strategy's own criteria. | Flag if the thesis cites crowd/social sentiment ("everyone is buying," "trending on X") as a primary justification rather than the strategy's own entry criteria. |

Note on sourcing: Gambler's Fallacy, Illusion of Control, Recency Bias, Anchoring Bias,
Functional Fixedness, Confirmation Bias and Attribution Bias are worked through in detail
in the source module with named examples. Loss Aversion/Recovery Trauma is a direct
extension of the module's own "recovery trauma" section (§4). Overconfidence, Hindsight
Bias and Bandwagon Effect are named in the module's orientation chapter as topics to
watch for; they are included here with detection tests so the catalogue is operationally
complete for an automated scan.

---

## Veto protocol

Run this exact ordered checklist against every proposed trade before it may be sent to
execution. Each step has binary **PASS/VETO** semantics. **Stop at the first VETO** —
do not average, net, or "compensate" a VETO with strength elsewhere in the checklist.
A single VETO kills the trade (or forces a resize/re-submit); only a clean sweep of all
six steps authorizes execution.

1. **Position size vs. limits** — Compute proposed capital/margin exposure using the
   desk's standing equity model (§5.1) and sizing technique (§5.2/§7).
   - PASS if per-trade risk ≤ 3% of capital (default 1.5%) AND per-trade capital/margin
     exposure ≤ the standing percentage-margin or percentage-volatility ceiling.
   - VETO if either cap is breached. Resize down to the binding constraint and re-run
     the checklist from step 1.

2. **Stop defined?**
   - PASS only if an explicit stop-loss price (or, for options/derivatives, an explicit
     max-loss/exit condition) is stated before entry.
   - VETO — no exceptions — if no stop is defined. A trade cannot be sized (step 1
     depends on the stop distance) without one.

3. **R:R ≥ threshold**
   - Compute `(Target − Entry)/(Entry − Stop)` (invert sign convention for shorts).
   - PASS if R:R ≥ 1.5. Flag as sub-par (manual override required) if between 1.0 and
     1.5. VETO if R:R < 1.0.

4. **Correlation with existing book**
   - Check the candidate's correlation/covariance against current top holdings (§1, §2.4).
   - PASS if the position does not push any correlated cluster's combined weight past a
     concentration threshold (treat book names 10–21 target from §1 as the ceiling on
     total distinct exposures; treat >0.6–0.7 pairwise correlation with an existing
     large position as "effectively the same position" for concentration purposes).
   - VETO (or require resize/hedge) if adding the position raises correlated-cluster
     concentration beyond the desk's diversification limit.

5. **Daily-loss circuit breaker**
   - Track realized + mark-to-market P&L for the day against a pre-set daily loss limit
     (recommended default: 2–3× the standing per-trade risk cap, e.g. 3–5% of capital,
     or the CVaR from §3 if computed and fresher).
   - PASS if today's cumulative loss is still inside the limit.
   - VETO all new risk-adding trades for the remainder of the day if the limit is
     breached — closing/hedging trades are still permitted.

6. **Bias scan of thesis**
   - Run the proposed trade's written rationale against the bias catalogue (§8) detection
     tests.
   - PASS if zero biases are flagged.
   - VETO (or require the thesis be rewritten with the flagged bias explicitly
     countered/addressed) if one or more biases are flagged.

**Only a trade that PASSes all six steps in order may be forwarded to execution.**

---

## Sizing formula

Exact conversion from `(Capital, Risk% per trade, Entry, Stop)` to tradeable quantity —
this is the percentage-risk method (§5.2.4), the Risk Officer's default sizing formula.

```
Inputs:
  C       = available equity capital (per the standing equity model, §5.1)
  r       = risk % per trade (decimal, e.g. 0.015 for 1.5%; hard cap 0.03)
  Entry   = intended entry price
  Stop    = stop-loss price
  L       = lot size / multiplier (1 for cash equity; contract lot size for F&O)

Step 1 — Max loss threshold (₹):
  MaxLoss = r * C

Step 2 — Risk per unit (₹):
  RiskPerUnit = |Entry - Stop| * L

Step 3 — Quantity (lots/shares):
  Quantity = floor( MaxLoss / RiskPerUnit )

Step 4 — Cross-check against capital-exposure caps:
  CapitalCheckQty = floor( (MarginCeiling% * C) / (Margin-or-Price per unit) )
  FinalQuantity   = MIN( Quantity from Step 3, CapitalCheckQty )
```

Worked example (module's own trade): C = ₹500,000, r = 1.5%, Entry = 393.65, Stop = 390,
L = 1500 (lot size). MaxLoss = 0.015 × 500,000 = ₹7,500. RiskPerUnit = (393.65−390) ×
1500 = ₹5,475. Quantity = floor(7,500 / 5,475) = 1 lot (₹73,500 margin). After this fill,
re-derive `C` under the equity model (§5.1) before sizing the next trade — do not reuse
the original capital figure.

If a Kelly overlay is active (§5.2.5), apply it as a secondary scalar on top of the
percentage-risk result, never as a replacement:
```
KellyAdjustedRisk% = KellyCeiling% * Kelly%
```
and re-run Steps 1–4 using `KellyAdjustedRisk%` in place of `r`, still subject to the
hard 3% absolute cap.
