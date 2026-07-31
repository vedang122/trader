# Currency & Commodity Playbook — Macro Sentinel Reference

Source: Zerodha Varsity Module 8 (Currency & Commodity Futures). This is a decision-oriented
playbook for the **Macro Sentinel** role — the agent function that reads currency, crude, gold,
and global-cue data and turns it into a regime verdict (risk-on / neutral / risk-off) that gates
how much gross exposure the rest of the trading system is allowed to run.

---

## 1. How Indian currency futures work

- Currencies trade as **pairs**: `Base Currency / Quotation Currency = Value`. Base is always
  fixed to 1 unit. Buying a pair = long base currency + short quote currency; selling = the
  reverse. Buying USDINR = bullish USD, bearish INR.
- **RBI Reference Rate**: RBI polls a panel of "contributing banks" for a two-way USDINR quote
  between 11:30 AM–12:30 PM every trading day (no weekends/bank holidays) and averages the
  bid/ask to set the official USDINR reference rate. This rate is the basis for all currency
  futures/options **settlement**.
- RBI does **not** poll EURINR, GBPINR, or JPYINR directly. These are derived by **crossing**:
  take the international EUR/USD (or GBP/USD, USD/JPY) quote and multiply through the USDINR
  reference rate, using USD as the common pivot.
- A **pip/tick** for INR crosses is the 4th decimal place (0.0025 for USDINR). This is the
  smallest price move a currency pair can register.
- Retail spot-future arbitrage does not exist in INR currencies (no accessible USDINR spot
  market) — the only clean arbitrage/spread trade is the **calendar spread** between two
  futures expiries:
  - **Future Bull Spread**: long near-month, short far-month (bet the spread narrows/widens per view).
  - **Future Bear Spread**: short near-month, long far-month.
  - Spread contracts can be traded directly as a single instrument on the exchange (CDS →
    FUTCUR → pair → expiry-pair spread).
- **Interest Rate Parity / forward premia**: `F = S × (1 + Roc×N) / (1 + Rbc×N)` ≈
  `S × (1 + interest rate differential)`. A currency with the higher interest rate trades at a
  **forward discount** — this is why INR futures normally sit at a premium to spot (India's
  rates > US rates historically).
- **No seasonality**: Varsity ran a Holt-Winters test on 8 years of USDINR spot data — no
  statistically significant weekly or monthly seasonality exists. Treat "USDINR always falls in
  December"-style claims as noise.
- **Volatility**: USDINR annualized daily-return SD ≈ 4.94% (2015) vs Nifty 50's ≈ 15.71% —
  currency is a low-vol asset relative to equity, which is precisely why it can carry high
  leverage (~2.25–2.5% margin) without being reckless.
- **Correlation to equities**: USDINR vs Nifty 50 daily-return correlation = **‑0.12267** (2015
  data) — negative but weak. Rupee weakness is a real headwind for equities (FII money leaving
  → sell INR — sell equities) but it is not a tight, reliable single-factor signal on its own.

## 2. Currency contract specifications

| Pair | Underlying | Lot size | Tick/pip | P&L per tick | Margin (approx.) | Expiry |
|---|---|---|---|---|---|---|
| USDINR | 1 USD in INR | $1,000 | 0.0025 | Rs 2.5 | ~2.25–2.5% (SPAN+exposure) | 2 working days before last working day of month, tradeable till 12:30 PM |
| EURINR | 1 EUR in INR | €1,000 | 0.0025 | Rs 2.5 | ~2.5% (slightly > USDINR) | Same cycle as USDINR |
| GBPINR | 1 GBP in INR | £1,000 | 0.0025 | Rs 2.5 | Slightly higher than EUR/USD | Same cycle as USDINR |
| JPYINR | 100 JPY in INR | ¥100,000 | 0.0025 | Rs 2.5 | ~4.2% (**highest** in the currency segment — thin liquidity) | Same cycle as USDINR |

- P&L per tick formula (works for any futures/options contract): `(Lot Size / Price Quotation
  unit) × Tick Size`.
- All currency futures **settle in INR** at the RBI reference rate on expiry day.
- **USDINR options** (the only currency pair with listed options): European exercise, premium
  quoted in INR, 3-month forward contract cycle, ~25 strikes (12 ITM + 12 OTM + 1 ATM) at
  0.25-paisa intervals, cash-settled in INR against the RBI reference rate on expiry.
- **Liquidity ranking** (trade in this order of preference): USDINR Futures > USDINR ATM
  Options > GBPINR Futures > EURINR Futures > JPYINR Futures. Spread contracts on non-USDINR
  crosses are largely illiquid — avoid them.

## 3. Key USDINR drivers — the event checklist

| Driver | Mechanism | Directional read |
|---|---|---|
| Trade deficit / Current Account Deficit (CAD) | Imports (oil, bullion) require selling INR to buy USD; exports (software, rice) require selling USD for INR | Narrowing CAD → INR strengthens. Widening CAD → INR weakens |
| Interest rate differential (carry trade) | Capital flows to the higher-yielding currency | RBI hiking / Fed on hold → INR carry more attractive → INR strengthens. Fed hiking faster than RBI → carry unwind → INR weakens |
| RBI / Fed / ECB policy stance | "Hawkish" = leaning toward hiking rates; "Dovish" = leaning toward cutting | Hawkish RBI → INR strengthens. Dovish RBI → INR weakens. Hawkish Fed (relative to RBI) → USD strengthens, INR weakens |
| Inflation (CPI/WPI) | High inflation → central bank expected to turn hawkish to cool spending | Rising domestic inflation → expect hawkish RBI → INR strengthens (indirectly, via rate expectations) |
| GDP growth rate | Signals investor confidence, FDI/FII appetite | Higher growth → stronger currency |
| Geopolitical/referendum shocks | Removes clarity on future policy path; markets hate uncertainty | Shock event (Brexit-class) → sharp, fast moves in the affected currency and knock-on risk-off in global risk assets |

**Brexit case study (module's worked example)**: on the 23 June 2016 referendum outcome, GBP
fell **8.64%** in a single session — a reminder that referendum/election-style binary events can
move a G10 currency by multiples of its normal daily range. Rule of thumb carried from this
chapter: **"when in confusion, do nothing"** — not taking a position ahead of an unresolved
binary macro event is itself a valid trade.

## 4. Correlation cheat sheet (what actually holds up)

| Pair | Relationship | Strength / caveat |
|---|---|---|
| USDINR vs Nifty 50 | Inverse | Weak: r ≈ ‑0.12 (2015). Directionally correct, not a strong standalone signal |
| Gold vs US Dollar Index (DXY) | Inverse | Qualitatively reliable, but can decouple (e.g., a regional crisis can push both gold AND USD up simultaneously as competing safe havens) |
| Gold vs US Fed funds rate | Inverse (theoretically) | Weak in practice: r < 0.3. Don't over-weight Fed-rate moves alone as a gold driver |
| Gold vs Silver | Positive ("Bullion Twins") | Strong: r ≈ 0.7 intraday (30-min bars), ≈ 0.8 on a quarterly/EOD basis. Treat gold+silver as one "precious metals / safe-haven" vote, not two independent votes |
| Silver vs Crude Oil | Erratic | Explicitly called out as unreliable — do not use |
| Crude Oil vs US Dollar Index | Inverse | Reasonably reliable over long windows — driven by oil being dollar-denominated globally (stronger dollar buys more oil per unit → drains inventory slower → bearish oil, and vice versa). Magnitude is not proportional (10% DXY move ≠ 10% oil move) |
| Natural Gas (MCX) vs Natural Gas (NYMEX) | Positive, tight | MCX gas is essentially a mirror of NYMEX gas — trade NYMEX cues directly |
| Crude Oil vs Natural Gas | Historically positive | Correlation has been weakening in recent periods — treat as a soft signal only |
| Gold vs general risk sentiment | Inverse to risk appetite | Gold is the module's primary "safe haven" asset — rallies hard around uncertainty (Brexit rally documented in source), and is also treated as a long-run inflation hedge (~8% CAGR 1970–2016 vs ~5–6% average global inflation) |

## 5. Commodity market structure (India)

- Two commodity exchanges: **MCX** (metals + energy, the dominant venue for the contracts in
  this playbook) and **NCDEX** (agri commodities).
- Unlike equities, commodity futures are **physically settled by default** — there is no cash
  settlement unless the specific contract explicitly allows it (see per-commodity tables below).
  To take delivery, intent must be declared by **4 days before expiry**. Zerodha does not support
  physical delivery — positions must be squared off before the delivery-intent window opens.
  This is an operational constraint, not a trading signal, but it matters for any automated
  position-management logic touching commodity futures.
- **Liquidity rule of thumb**: the nearest-month (current) contract carries almost all the
  volume; far-dated contracts sit nearly dead until they become the front month. Always
  reference/trade the current-month contract; roll a few sessions before expiry.
- Each commodity is mapped to one **designated physical delivery market** (e.g., gold →
  Mumbai/Ahmedabad, pepper/rubber → Kochi) — on expiry the futures price converges to that
  specific spot, not a generic "India spot" price.

## 6. Gold — contract specs and drivers

| Contract | Price quote | Lot size | Tick | P&L/tick | Expiry | Delivery |
|---|---|---|---|---|---|---|
| Gold ("Big Gold") | per 10 g | 1 kg | Re 1 | Rs 100 | 5th day of contract month | Compulsory, 1 kg |
| Gold Mini | per 10 g | 100 g | Re 1 | Rs 10 | 5th day of contract month | Compulsory, 100 g |
| Gold Guinea | per 8 g | 8 g | Re 1 | Re 1 | Last day | Compulsory, 8 g |
| Gold Petal | per 1 g | 1 g | Re 1 | Re 1 | Last day | Compulsory, 8 g |

- Margin ≈ 4% (Big Gold) to ~5% (Mini); all-in price includes import duty/taxes already.
- New contracts introduced every 2 months, each stays live for a year (6 concurrent contracts at
  any time); front-month (nearest expiry) has the volume — Big Gold ~12–13K lots/day, Gold Mini
  ~14–15K lots/day; Guinea and Petal are comparatively illiquid despite headline lot counts.
- **London Fix**: gold priced twice daily by ~10–11 major bullion banks (AM fix 10:30, PM fix
  15:00). India's own "fix" is set by the Indian Bullion Association off dealer bids, which
  themselves reference the MCX futures price — some circularity by design.
- **MCX vs CME price gap**: India is a net gold importer; landed cost = international spot +
  CIF + customs duty + cess + bank cost, so Indian spot (and hence MCX futures) is structurally
  higher than CME/international spot. This is **not** an arbitrage opportunity — it's a real cost
  wedge. (1 troy ounce ≈ 31.1035 grams, used to convert international $/oz quotes to Rs/10g.)
- **Drivers**: (1) safe-haven demand — every major uncertainty event (Brexit, Lehman, Middle
  East crises, Euro crisis) drove gold up; (2) inverse relationship with the US Dollar Index
  (weak dollar → gold demand up); (3) long-run inflation hedge; (4) weak/unreliable link to Fed
  funds rate moves directly (r<0.3) despite intuition suggesting otherwise — don't treat "Fed
  hiked" as an automatic gold-bearish trigger.

## 7. Silver — contract specs and drivers

| Contract | Price quote | Lot size | Tick | P&L/tick | Expiry | Delivery |
|---|---|---|---|---|---|---|
| Silver | per kg | 30 kg | Re 1 | Rs 30 | 5th day of expiry month | Compulsory, 30 kg |
| Silver Mini | per kg | 5 kg | Re 1 | Rs 5 | Last day of expiry month | Cash or physical, 30 kg |
| Silver Micro | per kg | 1 kg | Re 1 | Re 1 | Last day of expiry month | Cash or physical, 30 kg |
| Silver 1000 | per kg | 1 kg | Re 1 | Re 1 | Last day of expiry month | Physical only, 1 kg |

- Margin ~5–6% across variants. Silver (30 kg) is compulsory-delivery only — no cash-settlement
  opt-out; Mini/Micro allow cash settlement.
- Global demand ~1,170.5 million oz (growing ~2.5%/yr, driven by industrial fabrication —
  electronics, photography); supply (mining + scrap + sovereign sales) ~1,040.6 million oz
  (growing only ~1.4%/yr) — a persistent supply deficit.
- Because industrial demand is a major component, silver is more geared to global manufacturing
  growth (China, India) than gold is — use it as a cyclical-growth-cum-safe-haven hybrid signal.

## 8. Crude Oil — contract specs and drivers

| Contract | Price quote | Lot size | Tick | P&L/tick | Expiry | Delivery |
|---|---|---|---|---|---|---|
| Crude Oil ("Big") | per barrel | 100 barrels | Re 1 | Rs 100 | 19th/20th of month | 50,000 barrels, Mumbai/JNPT |
| Crude Oil Mini | per barrel | 10 barrels | Re 1 | Rs 10 | 19th/20th of month | 50,000 barrels, Mumbai/JNPT |

- Margin: ~9% NRML (overnight) / ~4.5% MIS (intraday) for Big Crude; ~9.5% NRML / ~4.8% MIS for
  Mini — one of the higher-margin MCX contracts, reflecting crude's volatility.
- New contract introduced every month with a 6-month-forward expiry; roll to the new front month
  a few sessions before current expiry (liquidity migrates ahead of the roll).
- **MCX crude tracks Brent**, not WTI, as its benchmark. WTI (API gravity 39.6, sulfur 0.26% —
  "super light, very sweet") trades differently from Brent (API gravity 38.06, sulfur 0.37% —
  "light, sweet" but blended from 15+ fields); Brent normally prices at a premium to WTI.
- **Industry map** (relevant for how a crude move should be read into equities):
  - **Upstream** (exploration/production — ONGC, Cairn, Reliance, Oil India in India; Shell/BP/
    Chevron internationally): margins improve when oil prices **rise**; hurt when prices fall.
  - **Downstream** (refining/marketing — BPCL, HPCL, IOC in India; Exxon Mobil as an integrated
    "Super Major"): benefit when oil prices **fall** (cheaper feedstock, lower subsidy/working
    capital stress); hurt when prices rise.
  - **Midstream** (transport/pipelines — TransCanada, Spectra, Williams): prefer **stability**,
    hurt by big moves in either direction.
  - Rule: don't blanket-short/long all "oil stocks" on a crude move — check whether the company
    is upstream or downstream first.
- **Inventory data** (the primary weekly event risk for crude): **US EIA** publishes crude
  inventory levels **weekly**; a build is bearish (demand weak / oversupply), a draw is bullish.
  **OECD** also publishes crude inventory data, at lower frequency.
- **OPEC / Non-OPEC supply dynamics**: OPEC (Saudi, Qatar, Kuwait, UAE, etc.) vs Non-OPEC
  (Russia, Brazil, Canada, Mexico, Norway) collectively pump ~90 million barrels/day (historical
  reference point). OPEC production-cut/hold decisions are a standing catalyst; watch for
  coordinated-cut headlines vs failure-to-agree headlines (member breakeven prices — e.g. Russia
  needing ~$105–107/barrel to balance its budget in the module's era — explain why some members
  push harder for cuts than others).
- **USD–Crude relationship**: inverse, mediated through the **Dollar Index (DXY)**, not USDINR
  spot — because crude is a dollar-denominated global commodity regardless of the buyer's local
  currency.
- **India macro transmission**: India imports ~2/3 of its oil needs. A crude spike widens
  India's import bill, pressures CAD and INR, and raises inflation (fuel-linked); a crude crash
  eases subsidy/fiscal stress for OMCs but also crimps export demand from oil-economy trading
  partners (UAE, Saudi, Kuwait, Iran). **Documented equity-market transmission**: on 6 Jan 2015,
  fear around continued oil-price collapse dropped the Nifty **~3% (255 points)** in a single
  session — crude-driven risk-off can hit Indian equities directly, not just via slow
  macro-fundamentals channels.
- **Big vs Mini arbitrage**: the two contracts should trade at an identical per-barrel price
  (same underlying). A gap is a risk-free arb — buy the cheaper, sell the pricier, sized to
  match contract **value** (not lot count) since lot sizes differ 10:1.

## 9. Natural Gas — contract specs and drivers

| Contract | Price quote | Lot size | Tick | P&L/tick | Expiry | Delivery |
|---|---|---|---|---|---|---|
| Natural Gas | per mmBtu | 1,250 mmBtu | Rs 0.10 | Rs 125 | 25th of month | 10,000 mmBtu |

- Margin ~15% NRML / ~7% MIS — the **highest margin percentage of any contract in this
  playbook**, reflecting how sharply natural gas can gap (the module's cautionary tale: the 2006
  Amaranth Advisors hedge-fund blowup, a $6B loss from an over-leveraged, weather-driven bet gone
  wrong).
- New contract every 4 months. MCX natural gas closely mirrors **NYMEX** natural gas — treat
  NYMEX price action as the leading signal for MCX.
- **Drivers**: (1) **US EIA weekly inventory data** — build = bearish, draw = bullish; (2) **US
  weather** — harsh winters spike heating demand and draw down inventory fast (bullish); (3)
  **hurricanes** — disrupt Gulf supply infrastructure (bullish bias, be reluctant to hold shorts
  into a hurricane track); (4) **crude oil price** — historically positively correlated as a
  substitute/complementary fuel, though this correlation has been weakening recently — treat as
  a secondary, not primary, signal.

## 10. Base metals (MCX) — contract specs

| Metal | Contract | Lot size | Tick | P&L/tick | Margin (NRML, approx.) |
|---|---|---|---|---|---|
| Copper | Big | 1 metric ton | Rs 0.05 | Rs 50 | ~7.8% |
| Copper | Mini | 250 kg | Rs 0.05 | Rs 12.5 | similar % |
| Aluminium | Big | 5 metric tons | Rs 0.05 | Rs 250 | ~5.6% |
| Aluminium | Mini | 1 metric ton | Rs 0.05 | Rs 50 | ~5.7% (MIS ~2.8%) |
| Lead | Big | 5 metric tons | Rs 0.05 | Rs 250 | ~11.7% (MIS ~5.9%) — highest of the base metals |
| Lead | Mini | 1 metric ton | Rs 0.05 | Rs 50 | ~11.7% (MIS ~5.9%) |
| Nickel | Big | 250 kg | Rs 0.10 | Rs 25 | ~10% (MIS ~5%) |
| Nickel | Mini | 100 kg | Rs 0.10 | Rs 10 | ~10% (MIS ~5%) |

- All expire on the **last day of the month**; all price-quoted per kilogram; delivery unit
  typically 10 MT (3 MT for Nickel).
- All four base metals take their reference cue from the **London Metal Exchange (LME)** — MCX
  prices closely track LME.
- **Common driver: Chinese demand.** Copper's 2015 global demand of ~24 million tons was half
  sourced by China+Japan; a supply glut (supply > demand) cooled prices. Aluminium's 2015 global
  production of ~56 million tonnes (up ~4% YoY, ~6% CAGR over 8 years) matched demand roughly
  1:1, but price still fell from a peak of ~$2,500/ton to ~$1,500/ton on the broader commodity
  glut — China is the single biggest swing factor across all base metals. Treat Chinese PMI/
  demand headlines as a base-metals-wide catalyst, not metal-specific.
- Copper and Aluminium have documented **corner/manipulation risk** precedent (1995 Sumitomo
  copper scandal, ~$5B loss) — a reminder that thin international futures markets can be
  squeezed; not a regular signal, but relevant context for any anomalous price/OI spike.

## 11. Agri commodities (MCX) — monsoon-driven, secondary priority

| Commodity | Price quote | Lot size | Tick | P&L/tick | Expiry | MIS available? |
|---|---|---|---|---|---|---|
| Cardamom | per kg | 100 kg | Rs 0.10 | Rs 10 | 15th of month | No |
| Mentha Oil | per kg | 360 kg | Rs 0.10 | Rs 36 | Last day | No |

- **No MIS (intraday) margin is offered on any agri commodity** — they hit circuit limits too
  often to safely unwind same-day, so NRML is used even for intraday trades.
- India runs two monsoon seasons: **Southwest monsoon** (Jun/Jul–Sep/Oct, principal rainfall,
  feeds **Kharif** crops — rice, pulses, cotton, cardamom) and **Northeast monsoon** (Dec–Mar,
  feeds **Rabi** crops — wheat, mustard, gram). Agriculture is only ~10% of Indian GDP but the
  largest employer, so monsoon shortfalls carry outsized political and food-inflation weight —
  a bad monsoon is a plausible upside risk to India CPI prints, which in turn feeds RBI's rate
  decisions and the INR view.
- Mentha oil is exported to the US, China, Singapore — it is directly USDINR-sensitive on top of
  its rainfall/crop-acreage drivers.
- Agri commodities trade until 5:00 PM (later than metals/energy).

## 12. Event calendar — what to watch, and why

| Event | Frequency | Primarily moves | Read |
|---|---|---|---|
| RBI Monetary Policy Committee (repo rate + stance) | ~Bi-monthly | USDINR, INR-rate curve | Hawkish hold/hike → INR supportive; dovish cut → INR headwind |
| US Federal Reserve FOMC | ~8x/year | DXY, USDINR, gold, global risk | Hawkish Fed (faster hikes than RBI) → USD up, INR down, gold down (all else equal) |
| India CPI / WPI inflation print | Monthly | RBI stance expectations, INR | High print → hawkish RBI odds up → INR supportive (lagged) |
| US CPI / PCE inflation print | Monthly | Fed stance expectations, DXY, gold | Hot US CPI → hawkish Fed odds up → USD up, gold down |
| India trade deficit / CAD data | Monthly/quarterly | USDINR | Widening deficit → INR pressure |
| India & US GDP prints | Quarterly | Currency, risk sentiment | Growth beats → currency + risk assets supported |
| US EIA crude inventory | Weekly | Crude, energy-linked equities | Build → bearish crude; draw → bullish crude |
| OECD crude inventory | Less frequent | Crude (slower-moving confirmation) | Same read as EIA, longer lag |
| OPEC (and OPEC+) meetings/output decisions | Scheduled + ad hoc | Crude, INR (via import bill), OMC/upstream equities | Coordinated cut → bullish crude; failure to agree → bearish crude |
| US EIA natural gas inventory | Weekly | Natural gas | Build → bearish; draw → bullish |
| US weather / hurricane advisories | Seasonal (winter, Jun–Nov hurricane season) | Natural gas | Harsh winter or storm risk → bullish bias, avoid shorts |
| IMD monsoon progress reports | Seasonal (Jun–Sep, Dec–Mar) | Agri commodities, India food-CPI, indirectly RBI stance | Deficient monsoon → bullish agri prices, upside inflation risk |
| Binary geopolitical/referendum events (Brexit-class) | Ad hoc | GBP/EUR crosses, gold, global risk indices | High-uncertainty, fast, large moves; default to reduced exposure until the outcome and market reaction are known |

## 13. How this feeds an equity-market regime view

- **Rupee weakness** (USDINR grinding higher) historically has a weak-but-real negative pull on
  Nifty (r ≈ ‑0.12) — read it as one input among several, not a standalone kill switch. Sharp,
  fast INR depreciation (vs. slow grind) is the more concerning pattern, since it usually signals
  FII outflows or a CAD/inflation shock rather than orderly drift.
- **Crude spikes** hit India on two channels simultaneously: (1) macro — wider CAD, INR pressure,
  higher inflation, tighter policy risk; (2) direct equity — OMC/downstream margins compress,
  and the market has shown it can react in a single session (the 3% Nifty drop on 6 Jan 2015 on
  crude-crash fears shows the linkage runs both ways, not just on spikes).
- **Gold rallies** are the module's cleanest "the market is scared" tell — gold strength
  alongside falling equities is a classic risk-off signature (see Brexit). Gold strength
  alongside rising equities is less common and should be flagged as a data-quality/regime-
  transition check rather than trusted blindly.
- **DXY strength** tends to coincide with EM currency (including INR) weakness and commodity
  softness (gold, crude both have inverse-DXY tendencies) — a strong, trending DXY is a
  broad-based EM/risk headwind, not just an INR-specific one.
- **Global index cues** (major overseas markets trading before/alongside Indian hours, given
  India's "sweet spot" time-zone overlap with both Asian and European sessions) are a direct
  read on global risk appetite and should be weighted heavily — currency/commodity signals are
  corroborating evidence, not a replacement for watching the tape itself.

---

## Regime assessment protocol

The Macro Sentinel's job is to convert the inputs above into one of three regime verdicts —
**risk-on / neutral / risk-off** — and translate that into a gross-exposure multiplier for the
rest of the trading system.

### Step 1 — Score each input as a vote

Each input casts a vote of **+1 (risk-on)**, **0 (neutral/unclear)**, or **‑1 (risk-off)**, based
on its recent trend (use a consistent lookback, e.g. 5–10 sessions, to judge trend direction and
avoid single-print noise):

| Input | Risk-on vote (+1) | Risk-off vote (‑1) | Weight |
|---|---|---|---|
| INR trend (USDINR) | INR stable/strengthening | INR depreciating sharply/fast | 1.0 |
| Crude oil trend + inventory | Range-bound or falling on demand strength; inventory draws | Spiking on supply-shock/geopolitics; repeated builds | 1.0 |
| Gold trend | Flat/falling (no safe-haven bid) | Rallying hard (safe-haven bid active) | 1.0 |
| DXY trend | Flat/weakening | Strong and trending up | 1.0 |
| Global indices (overseas cues) | Trending up / stable | Trending down, elevated volatility | 1.5 |
| Pending event-risk flag (binary override, see below) | No major event in next 24–48h | Major central bank decision, OPEC meeting, or referendum-class event pending/unresolved | override, not additive |

Rationale for weights: global index cues get the heaviest weight (1.5) because they are the
most direct read on risk appetite — currency and commodity signals are corroborating/leading
indicators, not substitutes for the market's own tape. INR, crude, gold, and DXY each get equal
standard weight (1.0) since none of them individually showed a strong, reliable correlation in
isolation (USDINR–Nifty r≈‑0.12; Gold–Fed r<0.3) — the protocol's strength comes from requiring
several of them to agree, not from trusting any single one.

### Step 2 — Compute the weighted score and apply the event-risk override

`score = Σ(vote × weight) / Σ(weight)`, bounded to [‑1, +1].

- If a **pending event-risk flag** is active (an RBI MPC or Fed FOMC decision due within the
  next session, an OPEC meeting outcome pending, or an unresolved binary geopolitical event in
  progress), **cap the verdict at Neutral** regardless of the computed score. This directly
  follows the module's Brexit lesson: uncertainty itself is a risk-off condition, and "when in
  confusion, do nothing" — don't commit to a full risk-on stance ahead of a binary resolution.

### Step 3 — Map score to verdict and gross-exposure multiplier

| Weighted score | Verdict | Gross-exposure multiplier |
|---|---|---|
| ≥ +0.5 (and no event override) | Risk-on | **1.0** — full sanctioned exposure |
| ‑0.5 to +0.5, or event-risk override active | Neutral | **0.7** — trim exposure, tighten stops, reduce new-position sizing |
| ≤ ‑0.5 | Risk-off | **0.4** — defensive stance: cut gross exposure sharply, prioritize capital preservation over new positions |

### Step 4 — Re-score on every material trigger, not just on a timer

Re-run the protocol whenever any single input moves sharply (e.g., USDINR gaps, crude jumps >2%
intraday, a central bank surprise) rather than waiting for a fixed schedule — several of this
module's worst-case examples (Brexit, the Amaranth natural-gas blowup, the Jan-2015 Nifty drop
on crude fears) were fast, single-session dislocations, not slow drifts. A regime verdict that
is stale by even one session can materially misstate the correct exposure multiplier.

### Step 5 — Document the dominant driver

Since currency/commodity events often conflict (e.g., INR strength from FDI inflows vs. USD
strength from a hawkish Fed, both happening at once), always log **which vote(s) drove the
verdict** and flag when the tally is close (e.g., 3 inputs risk-on vs. 2 risk-off) as
**low-conviction** — per the module's own framing, when two events pull in opposite directions,
the pair "invariably exhibits volatile behaviour" until the more dominant factor wins out, and
the Sentinel should reflect that ambiguity rather than force a confident verdict.
