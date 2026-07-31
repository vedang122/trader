# Fundamental Analysis Playbook (Zerodha Varsity Module 3)

Distilled operating manual for an AI trading agent evaluating NSE-listed companies for
long-term (3-5 year+) investment decisions. This is a decision playbook, not a summary —
use it as a checklist and formula reference while researching a stock.

---

## 1. Operating philosophy

- FA is for long-term (3-5 year) investment decisions, not short-term timing. Use TA to
  time entries/exits; use FA to decide *what* to own for the long haul.
- Core-Satellite capital allocation heuristic: ~60% of capital in a "core" of
  fundamentally strong long-term holdings (expect 12-15% CAGR), ~40% "satellite" for
  active/tactical trading (expect 10-12% absolute return/year).
- Compounding reward: at 20% CAGR capital doubles in ~3.5 years. The longer the holding
  period, the faster wealth accelerates (non-linear) — bias toward patience over churn.
- Every stock must be evaluated on two axes: **Qualitative** (management, moat, ethics)
  and **Quantitative** (ratios, growth, cash flow). Qualitative red flags override good
  numbers — do not recommend a stock with great margins but poor governance.
- Realistic return expectation for a well-run long-term portfolio: 15-18% CAGR. Treat
  any thesis promising 50-100%+ short-term returns as unsustainable / suspect.

---

## 2. Qualitative checklist (moat, management, governance)

Score every candidate against these before touching a spreadsheet. Any single item
failing badly is a potential veto, regardless of ratios:

1. **Management background** — credentials, experience, education, any criminal cases
2. **Business ethics** — history of scams, bribery, unfair practices
3. **Corporate governance** — director appointments, org structure, transparency
4. **Minority shareholder treatment** — are minority interests respected in corporate actions
5. **Promoter share transactions** — clandestine buying/selling via related entities
6. **Related-party transactions** — favors to promoter relatives/friends/vendors at
   shareholders' expense (major red flag even with great margins)
7. **Promoter salaries** — outsized pay as % of profits
8. **Operator activity** — unusual stock price behavior around promoter transactions
9. **Significant shareholders** — who holds >1%; presence of reputable institutional/value investors is a positive signal
10. **Political affiliation** — dependence on political patronage
11. **Promoter lifestyle** — excessive flamboyance/display of wealth is a soft red flag

**The Moat (economic moat, term via Warren Buffett):** a durable competitive advantage
(brand, pricing power, market share, licensing, distribution, labor arbitrage, niche
scale) that protects long-term profits from competitors. Examples from the module:
Eicher Motors/Royal Enfield (brand loyalty), Infosys (US-India labor arbitrage), Page
Industries (Jockey license), TTK Prestige (pressure cookers), Gruh Finance (niche
small-ticket credit). No moat = profits are vulnerable to erosion; prefer companies
with wide, sustainable moats.

**Business understanding Q&A** (answer from annual report + company website, not
generic web search): What does the company do, and who are the promoters (background,
red flags)? What do they manufacture, how many plants/where, and are plants at full
capacity (capacity constraints unexplained by funding/access issues are a red flag)?
What raw material is needed — regulated (e.g. coal) or imported (supply risk)? Who are
the clients/end users and the competitors (monopoly/duopoly/oligopoly supports margins;
crowded field = margin pressure)? Who are the major (>1%) shareholders — reputable
institutional/value investors present is a positive signal. New product or geographic
expansion plans (ambition signal, but drift far outside the core business is a red
flag)? What's the revenue mix by product/segment? Is the industry heavily regulated
(barrier to entry, but limits innovation flexibility)? Who are the bankers/auditors
(rule out association with scandal-linked firms)? Employee count/labor issues? Entry
barriers for new competitors? Can the product be easily replicated by cheap-labor
competitors (hardware, garments, handsets — flag as a long-term moat risk)? Are there
too many subsidiaries (possible fund-siphoning vehicle — cross-check related-party
transactions)?

Rule: if a red flag surfaces at this qualitative stage, **stop researching further** —
do not proceed to ratio analysis no matter how attractive the numbers look.

---

## 3. How to read the Annual Report (AR)

- AR is the single most reliable source (audited, dated, sealed) — prefer it over media
  summaries, which can reorder/recategorize data non-maliciously but confusingly.
- Read at least the **last 5 years** of ARs to see how the company evolves across cycles.
- Typical AR sections and what to extract: **Financial Highlights** (skim only — you'll
  compute your own ratios); **Management Statement/Chairman's message** — assess
  realism, cross-check claimed growth rates against actual historical revenue trend (a
  chairman quoting growth inconsistent with reported numbers is a credibility red flag);
  **Management Discussion & Analysis (MD&A)** — the most important qualitative section:
  macro view, industry trends, competitive positioning, segment performance, forward
  strategy — compare against a direct competitor's MD&A; **HR/R&D/Technology reports** —
  check labor-unrest risk (manufacturing) or innovation pipeline (tech/pharma);
  **Financial statements** — P&L, Balance Sheet, Cash Flow (see below).
- **Standalone vs Consolidated**: standalone = parent company only; consolidated =
  parent + subsidiaries. **Prefer consolidated** — it better represents the group's true
  financial position.
- Every line item has an associated **Note/Schedule** — always drill into notes for
  material line items (e.g. "Other Income", "Other Expenses", debt terms).
- **Other Income red flag**: Other income should be a small fraction of total revenue.
  A large "Other Income" relative to operating revenue demands investigation — it can
  mask a weak core business.

---

## 4. Reading the P&L statement

Structure (top to bottom):
- **Revenue**: Sale of products − Excise duty = Net Sales; + Sale of services + Other
  operating revenue = **Net Revenue from Operations**; + Other Income = **Total Revenue**.
- **Expenses**: Cost of materials consumed, Purchases of stock-in-trade, Change in
  inventory, Employee benefit expense, Finance cost, Depreciation & Amortization, Other
  expenses.
- **PBT** = Total Revenue − Total Operating Expenses (− exceptional/extraordinary items
  if any).
- **PAT (Net Profit)** = PBT − Applicable taxes. This is the "bottom line."
- **EPS** = PAT / Total outstanding ordinary shares.

Checks while reading:
- Employee expense as % of revenue is typically small (single digits) outside IT/services.
- Depreciation/Amortization spreads asset cost over useful life (Net Block = Gross Block
  − Accumulated Depreciation); watch for companies under-depreciating to inflate PAT.
- Finance Cost tracks directly with debt level — rising finance cost + flat/rising debt
  is a leverage warning.

---

## 5. Reading the Balance Sheet

**Balance sheet equation**: Assets = Liabilities + Shareholders' Equity
(Shareholders' Equity = Assets − Liabilities; shown on the liabilities side because it
represents money the company "owes" back to its owners.)

**Liabilities side:**
- Shareholders' Funds = Share Capital (face value × shares outstanding) + Reserves &
  Surplus (capital reserve, securities premium, general reserve, and surplus/retained
  earnings carried forward year to year — dividends are paid out of surplus).
- Non-current liabilities: long-term borrowings, deferred tax liability, long-term
  provisions (settled beyond 12 months).
- Current liabilities: short-term borrowings, trade payables, other current liabilities,
  short-term provisions (settled within 12 months).
- **No debt is not automatically good** — ask why: refused credit, or genuinely no
  need/expansion appetite? Investigate before assuming zero debt = strength.

**Assets side:**
- Non-current (fixed) assets: tangible + intangible assets (Net Block = Gross Block −
  Accumulated Depreciation), Capital Work in Progress, non-current investments,
  long-term loans & advances.
- Current assets: Inventory, Trade Receivables, Cash & Cash Equivalents, short-term
  loans & advances, other current assets.

The three statements are interconnected: P&L's PAT flows into Balance Sheet surplus;
depreciation appears in both P&L and accumulated depreciation on the Balance Sheet;
Cash & Cash Equivalents on the Balance Sheet reconciles to the Cash Flow Statement's
closing balance.

---

## 6. Reading the Cash Flow Statement

Three activity buckets, each can be a net source or use of cash:
- **Operating Activities (OA)** — core business: sales, manufacturing, hiring, etc.
- **Investing Activities (IA)** — capex, investments in securities/subsidiaries/property.
- **Financing Activities (FA)** — debt raised/repaid, equity issued, dividends paid.

`Total Cash Flow = CF(Operating) + CF(Investing) + CF(Financing)`

Rules of thumb: increase in liabilities → cash increases; increase in assets → cash
decreases (and vice versa). **Cash Flow from Operations must be positive** — one of the
most important checks in the entire framework. A company reporting rising PAT but
negative or declining operating cash flow is a major red flag (earnings-quality problem
— check if profits are just receivables/inventory, not real cash). Volatile-but-positive
CFO across years (e.g. ₹214cr, ₹86cr, ₹298cr, ₹335cr, ₹279cr in the module's ARBL
example) is acceptable; consistently negative is not. Healthy Investing-Activities cash
consumption (negative IA from capex) signals genuine business expansion, not inherently
bad. Cash & Cash Equivalents (closing balance) reconciles into the Balance Sheet's
current assets.

---

## 7. Financial Ratios — formulas and interpretation thresholds

General rule: **a ratio in isolation is nearly meaningless.** Always evaluate a ratio
(a) against the same company's own historical trend and (b) against direct competitors
in the same industry.

### 7.1 Profitability Ratios

| Ratio | Formula | Good / Bad Signal |
|---|---|---|
| **EBITDA Margin** | EBITDA / [Total Revenue − Other Income]; EBITDA = [Total Revenue − Other Income] − [Total Expense − Finance Cost − D&A] | Compare to peers and own trend; rising trend = improving operational efficiency. No fixed universal threshold — sector-dependent. |
| **PAT Margin** | PAT / Total Revenue | Track the trend; expanding PAT margin over years is a strong positive signal (e.g. 8.4%→10.5% over 4 yrs in the module's example). |
| **Return on Equity (ROE)** | Net Profit / Avg Shareholders' Equity × 100 | Indian large-cap average ~14-16%. **Author's personal cut-off: invest only in companies with ROE ≥ 18%; checklist threshold used later is >25%.** High ROE fueled mainly by high leverage (not efficiency) is a red flag — always decompose via DuPont. |
| **Return on Assets (ROA)** | [Net Income + Interest×(1−tax rate)] / Total Average Assets | Higher = more efficient use of assets. Add back after-tax interest because debt-holders' capital also funds the assets. |
| **Return on Capital Employed (ROCE)** | PBIT / Overall Capital Employed; Capital Employed = Short-term Debt + Long-term Debt + Equity | Higher is better; measures return on *all* capital (debt + equity), not just equity. |

**DuPont decomposition of ROE** (use this instead of the naive ROE formula to judge
*quality* of the return, not just magnitude):

```
ROE = Net Profit Margin × Asset Turnover × Financial Leverage
    = (Net Profit/Net Sales) × (Net Sales/Avg Total Assets) × (Avg Total Assets/Avg Shareholders' Equity)
```

- **Net Profit Margin** — profit-generating ability; low margin = high costs/competition.
- **Asset Turnover** — efficiency of asset use to generate revenue; higher is better;
  low value may signal management/production problems.
- **Financial Leverage** — assets supported per unit of equity; higher leverage +
  rising debt = exercise caution. A high ROE driven mostly by the leverage term (not
  margin or turnover) is a warning sign, not a compliment.

### 7.2 Leverage (Solvency) Ratios

| Ratio | Formula | Good / Bad Signal |
|---|---|---|
| **Interest Coverage Ratio** | EBIT / Interest (Finance Cost); EBIT = EBITDA − D&A | Higher = safer. A ratio near/below 1.0x-1.2x means the company barely covers its interest burden — high default/bankruptcy risk (module example: JISL at 1.209x is a caution flag). |
| **Debt to Equity (D/E)** | Total Debt (short + long term) / Total Equity | D/E = 1 → equal debt and equity. **>1 = higher leverage, be careful. <1 = equity-heavy, generally safer.** |
| **Debt to Asset Ratio** | Total Debt / Total Assets | Indicates % of assets financed by creditors. Higher % (e.g. ~45% in the JISL example) = higher leverage/risk. |
| **Financial Leverage Ratio** | Avg Total Assets / Avg Total Equity | Higher = more assets supported per unit of equity = more risk if earnings falter. |

### 7.3 Operating (Activity/Management) Ratios

| Ratio | Formula | Good / Bad Signal |
|---|---|---|
| **Fixed Asset Turnover** | Operating Revenue / Avg Net Fixed Assets (incl. CWIP) | Higher = more efficient use of plant/equipment. Useful mainly for capital-intensive industries. |
| **Working Capital Turnover** | Revenue / Avg Working Capital; Working Capital = Current Assets − Current Liabilities | Higher = more revenue generated per unit of working capital = better. Negative working capital = deficit, may require a working-capital loan. |
| **Total Asset Turnover** | Operating Revenue / Avg Total Assets | Higher (vs. history/peers) = assets used well to generate sales. |
| **Inventory Turnover** | Cost of Goods Sold / Avg Inventory | Higher = faster inventory replenishment (good, generally). |
| **Inventory Number of Days** | 365 / Inventory Turnover | **Lower = better** (fast-moving products, efficient conversion to cash). **Caveat:** a very low inventory-days figure paired with low production capacity can indicate a *scalability problem*, not efficiency — investigate why production isn't being increased (funding constraints, raw material access, bank refusal to lend). |
| **Accounts Receivable Turnover** | Revenue / Avg Trade Receivables | Higher = collects cash from customers more frequently = better. |
| **Days Sales Outstanding (DSO)** | 365 / Receivable Turnover | Lower = faster cash collection cycle = better working-capital efficiency. |

### 7.4 Valuation Ratios

| Ratio | Formula | Good / Bad Signal |
|---|---|---|
| **Price to Sales (P/S)** | Current Share Price / (Total Revenue / Shares Outstanding) | Higher = market pricing sales more richly. Must be read alongside PAT margin — a company with a higher profit margin justifies a higher P/S than a lower-margin peer at the same P/S. |
| **Price to Book Value (P/BV)** | Current Share Price / Book Value per Share; BV = (Share Capital + Reserves excl. revaluation reserves) / Shares Outstanding | High P/BV → potentially overvalued relative to net asset backing; low P/BV → potentially undervalued. Compare to peers. |
| **Price to Earnings (P/E)** | Current Share Price / EPS | Higher = market paying more per unit of profit = more expensive. **Personal rule of thumb from the module: avoid stocks trading beyond 25x, at most 30x, earnings — irrespective of sector.** Watch for earnings manipulation: frequent accounting-policy changes, under-provisioning depreciation, or earnings growth that isn't matched by cash flow/sales growth are red flags that make P/E unreliable. |

**Index-level valuation (Nifty 50 P/E) as a market-timing gauge:**
- Historical range roughly 16x-20x, long-run average ~18x.
- **Below ~16x → historically the best entry environment (attractive valuations).**
- **Above ~22x → exercise caution; historically preceded market corrections** (e.g. 28x
  in early 2008 preceded a major crash; troughed near 11x in late 2008/early 2009).
- Check current Nifty/Sensex P,E,B/Div Yield data via NSE's published index valuation
  data before sizing new long-term buys — being a net buyer near/above 22x is a
  higher-risk decision even if a specific stock passes its own checklist.

---

## 8. The Investment Due Diligence Checklist (10-point)

Apply this after the qualitative stage (Section 2) passes. This is the module's own
curated checklist — treat it as a strong default, adaptable with experience:

| # | Variable | Threshold / Rule | What it signifies |
|---|---|---|---|
| 1 | Gross Profit Margin (GPM) | **> 20%** | Higher margin = evidence of a sustainable moat |
| 2 | Revenue Growth | In line with (or ahead of) profit growth | Growth in revenue should track growth in profit — divergence needs explaining |
| 3 | EPS growth | Should track PAT growth | If EPS lags PAT growth, the company is diluting equity — bad for existing shareholders |
| 4 | Debt Level | Not highly leveraged | High debt → high finance cost eating into earnings, elevated leverage risk |
| 5 | Inventory | Growing inventory alongside growing PAT margin is healthy (manufacturing companies) | Check Inventory Number of Days for stability/decline |
| 6 | Sales vs Receivables | Sales should **not** be predominantly backed by rising receivables | Rising receivables-to-sales suggests channel-stuffing / unsustainable credit push |
| 7 | Cash Flow from Operations | **Must be positive** | Negative CFO = operating stress even if PAT looks good |
| 8 | Return on Equity | **> 25%** (checklist threshold; note Section 7.1 also cites the author's personal >18% minimum) | Higher ROE better, but must be checked against debt level (DuPont) |
| 9 | Business Diversity | Prefer 1-2 core business lines | Too many unrelated segments = lost focus, harder to underwrite |
| 10 | Subsidiary Count | Not many | Excess subsidiaries can be a vehicle for siphoning funds — investigate related-party transactions |

Growth heuristics used alongside the checklist:
- Preferred revenue/PAT CAGR: **> 15%** (module author's personal cutoff).
- Evaluate growth both **year-on-year** (accounting for cyclicality — flat growth is OK
  if industry-wide) and as **multi-year CAGR** (captures resilience across cycles).
- Debt/EBIT ratio trending down over time (module example: 35% → 15.6% over 5 years)
  is a positive signal of improving balance-sheet discipline.

**Idea-generation methods** (how to build the initial watchlist before checklist
screening): general observation of everyday consumption patterns (Peter Lynch style),
stock screeners (e.g. filter for ROE ≥ 25% + PAT margin ≥ 20%), macro trend-following
(e.g. infra push → cement sector), sector-specific trend spotting, special-situation
triggers (management/board changes, corporate actions), and circle of competence
(leverage the analyst's own professional domain expertise).

**Sequencing discipline**: Stage 1 (understand business/qualitative) → Stage 2 (apply
10-point checklist) → Stage 3 (valuation/DCF). Never skip to valuation on a stock that
hasn't cleared Stages 1 and 2. A red flag at any stage halts the process — do not
override with an attractive valuation.

---

## 9. DCF Valuation — step-by-step procedure

The DCF estimates **intrinsic value** by discounting the company's future Free Cash
Flow (FCF) back to the present.

**Step 0 — Free Cash Flow (FCF) formula:**
```
FCF = Cash from Operating Activities (post-tax) − Capital Expenditures
```

**Step 1 — Estimate average historical FCF.**
Take the average FCF of the **last 3 years** (smooths cyclicality/one-off swings; a
single bad year shouldn't dominate the base).

**Step 2 — Choose FCF growth rate assumptions (conservative, two-stage).**
- Stage 1 (years 1-5): growth rate — module used 18% for a high-growth mid-cap example;
  for a mature/large-cap company, use ~15%.
- Stage 2 (years 6-10): a lower growth rate — module used 10% in both cases.
- **Hard ceiling: no company deserves an assumed FCF growth rate above ~20%.** Bias
  toward the conservative end of any plausible range.

**Step 3 — Project FCF for 10 years** by compounding the base-year average FCF at the
Stage 1 rate for years 1-5, then the Stage 2 rate for years 6-10.

**Step 4 — Terminal Value** (value of all cash flows beyond year 10, to infinity):
```
Terminal Value = FCF(year 10) × (1 + Terminal Growth Rate) / (Discount Rate − Terminal Growth Rate)
```
- **Terminal Growth Rate: keep below 5%, module author prefers 3-4% and never beyond.**
  The model is *highly sensitive* to this input — e.g., moving from 3.5% to 4.0%
  (50bps) changed the sample per-share value from ₹368 to ₹394. Always sanity-check
  this input and stress-test ±0.5%.

**Step 5 — Discount everything to present value (NPV).**
- Choose a discount rate (opportunity cost of capital / risk-free-adjusted rate —
  module used 9% in its worked example).
- Discount each year's projected FCF: `PV = FCF / (1 + discount rate)^n`.
- Discount the Terminal Value the same way (using year-10 exponent).
- `NPV of company = Σ PV(FCF years 1-10) + PV(Terminal Value)`

**Step 6 — Adjust for Net Debt.**
```
Net Debt = Total Debt (current year) − Cash & Cash Equivalents (current year)
Equity Value = NPV of Company − Net Debt
```
(If Net Debt is negative — more cash than debt — this *adds* to equity value.)

**Step 7 — Per-share intrinsic value.**
```
Intrinsic Value per Share = Equity Value / Total Shares Outstanding
```

**Step 8 — Build an intrinsic value band (modeling-error buffer).**
Apply **±10%** around the point estimate to account for assumption/modeling error:
```
Lower band = Intrinsic Value × 0.90
Upper band = Intrinsic Value × 1.10
```

**Step 9 — Compare current market price to the band:**
- Price **below** lower band → undervalued → candidate to buy.
- Price **within** the band → fairly valued → hold existing position, no fresh buying.
- Price **above** upper band → overvalued → book profits or hold, **do not buy**.

**DCF caveats to flag in any output:** requires forecasting (inherently uncertain, even
for company management); highly sensitive to the terminal growth rate assumption
(stress test it); must be refreshed as new quarterly/annual data arrives — treat any
DCF as perishable, not a one-time output; best suited to long-term investors, offers
little for <1 year horizons; rigid assumptions can cause the model to miss unusual
special-situation opportunities.

---

## 10. Margin of Safety rule

After computing the intrinsic value band (Section 9, Step 8), apply a further
**discount of at least 30%** to the *lower* band value before treating a price as a
genuine buying opportunity (Benjamin Graham's principle, via "The Intelligent
Investor"):

```
Margin-of-Safety Buy Price ≈ Lower Intrinsic Band × (1 − 30%)
```

Worked example from the module: intrinsic value ₹368 → lower band (−10% modeling
error) ₹331 → margin-of-safety price (further −30%) ≈ ₹230. Only at/below that level
does the module's author commit with high conviction.

Rationale: this buffers against bad assumptions and bad luck simultaneously — if a
stock looks attractive at ₹100, it's a far safer bet at ₹70. Margin-of-safety
opportunities in genuinely good businesses appear most often during bear markets /
broad pessimism — keep cash available to act on them (the module notes such windows
can persist for months, e.g. ~5 months in its ARBL example, so there's no need to
chase).

---

## 11. When to sell / portfolio construction

- **Sell trigger = disruption of investible-grade attributes**, not a price target or
  percentage gain. Do not sell purely because a stock is up (e.g. +192%) if the
  underlying checklist (Section 8) and moat (Section 2) remain intact. Conversely, sell
  when the attributes that justified the buy deteriorate — margin compression, rising
  leverage, governance red flags, moat erosion, etc.
- **Portfolio concentration** — reference points from well-known investors (context, not
  a hard rule): Seth Klarman 10-15 stocks, Warren Buffett 5-10, Ben Graham 10-30, John
  Maynard Keynes 2-3. Module author's own practice: ~13 stocks, comfort ceiling ~15,
  generally avoid **more than ~20** holdings (over-diversification dilutes conviction).
- **Avoid IPOs** as a rule — typically overpriced. If evaluating one anyway, apply the
  identical 3-stage framework rather than buying on hype/allotment excitement.
- Expect realistic long-run CAGR of **15-18%**; treat pitches implying 50-100%+ returns
  as unsustainable.

---

## Opinion protocol

When the fundamental-analyst agent expresses a view on an NSE-listed company, it must
package the conclusion in this structured form:

1. **Quality Grade (A / B / C)**
   - **A** — Clears the qualitative checklist (Section 2) with no material red flags and
     most/all of the 10-point due-diligence checklist (Section 8): GPM > 20%, revenue/PAT
     growth > 15% CAGR, ROE > 18-25% without excessive leverage (D/E < 1, interest
     coverage comfortably > 3-4x), consistently positive CFO, stable/declining inventory
     & receivable days, EPS tracking PAT (no dilution), 1-2 focused business lines, few
     subsidiaries.
   - **B** — Passes most checklist items but has 1-2 moderate concerns (leverage creeping
     up, GPM in the mid-teens, receivables outgrowing sales, related-party transactions
     worth monitoring, moat present but narrowing).
   - **C** — Fails multiple checklist items and/or has a qualitative red flag (governance
     concern, negative/volatile CFO, high leverage with weak interest coverage, heavy
     dependence on related parties or political patronage, no discernible moat). Grade C
     should generally preclude a long-term buy recommendation regardless of price.

2. **Valuation Verdict (Cheap / Fair / Expensive)**
   - Derived from comparing current market price against the DCF intrinsic value band
     (Section 9) and, where a full DCF isn't feasible, against P/E, P/BV, and P/S versus
     history and peers, plus the Nifty index P/E regime (< 16x supportive, > 22x
     cautionary) as market-level context.
   - **Cheap** — price at or below the margin-of-safety price (Section 10) or clearly
     below the lower DCF band; relative multiples (P/E, P/BV) below own 5-yr history and
     peer set.
   - **Fair** — price within the ±10% intrinsic value band; multiples roughly in line
     with history/peers.
   - **Expensive** — price above the upper intrinsic value band, and/or P/E > 25-30x, or
     materially above peer/historical multiples without margin justification.

3. **Long-Term Bias (Bullish / Neutral / Bearish)**
   - A synthesis, not a mechanical average, of Quality Grade and Valuation Verdict.
   - Example mapping: Grade A + Cheap/Fair → Bullish. Grade A + Expensive → Neutral
     (good business, wait for a better price / add on dips toward the band). Grade B →
     Neutral, contingent on watch-list monitoring of the specific concern. Grade C →
     Bearish / avoid, regardless of valuation.

4. **Key Risks** — bullet the specific, named risks uncovered during the review (e.g.
   "promoter pledging shares," "customer concentration in top 3 accounts," "raw material
   import dependency," "DCF highly sensitive to assumed 18% FCF growth — a 500bps miss
   materially changes the intrinsic value," "sector facing new entrants eroding
   oligopoly pricing power"). Always include DCF/model sensitivity as a risk when a DCF
   was used.

5. **Confidence (0-100)** — reflects data completeness and internal consistency, not
   just conviction in the bull/bear case. Lower confidence when: fewer than 5 years of
   annual report history reviewed, consolidated financials unavailable, qualitative
   checks (promoter background, related-party transactions) could not be verified, or
   DCF assumptions rely on thin/volatile historical FCF data (e.g. only 1-2 profitable
   years). Calibration: 80-100 = full 3-stage due diligence with clean, consistent
   multi-year data; 50-79 = most checks done but at least one material gap; below 50 =
   preliminary/screening-level view only — state this explicitly and recommend further
   research before acting.

Every opinion issued by the agent should explicitly state all five elements above,
even when the overall recommendation is "no action" or "insufficient data."
