# Technical Analysis Playbook (NSE Equities)

Source: Zerodha Varsity Module 2. This is a decision playbook for an AI trading
agent, not a tutorial. Every rule below is stated so it can be evaluated
programmatically against OHLCV data. Where the source gives a numeric
threshold, it is preserved verbatim; where the source says "be flexible,
quantify and verify," a concrete tolerance is given.

## 0. Core assumptions (apply before anything else)

TA assumptions (violate none silently — they gate whether a signal is valid):
1. **Markets discount everything** — price already reflects all known/unknown info.
2. **How > why** — react to price action, don't wait to understand causes.
3. **Price moves in trends** — only trade with an established trend context.
4. **History repeats** — pattern → outcome mapping is reusable *only if the
   same factor-set recurs* (don't pattern-match blindly).

Candlestick-specific rules (apply to every pattern check below):
1. **Buy strength, sell weakness** — only buy on a blue/bullish confirmation
   candle; only sell/short on a red/bearish confirmation candle.
2. **Be flexible — quantify and verify** — allow minor deviation from
   textbook OHLC equalities, but bound it numerically (tolerances given per
   pattern below). Never accept "roughly looks like" without a number.
3. **Require a prior trend** — bullish reversal patterns need a prior
   **downtrend**; bearish reversal patterns need a prior **uptrend**. The
   **Marubozu is the sole exception** — it is valid regardless of prior trend.

Candle anatomy: body = |open − close|; upper shadow = high − max(open,close);
lower shadow = min(open,close) − low. Range = high − low.
**Reject any candle with range < 1% or > 10% of price** (too subdued to
signal, or too extended to place a sane stop).

## 1. Single-candle patterns

| Pattern | Structure test | Bias | Entry (risk-taker / same close) | Stop |
|---|---|---|---|---|
| Bullish Marubozu | open ≈ low, close ≈ high (no material shadows) | Bullish, any prior trend | ~close of the Marubozu | low of Marubozu |
| Bearish Marubozu | open ≈ high, close ≈ low | Bearish, any prior trend | ~close of the Marubozu | high of Marubozu |
| Spinning top | small real body; upper shadow ≈ lower shadow | Indecision (context-dependent) | No direct entry — see §1.1 | n/a |
| Doji | open ≈ close (near-zero body), shadows any length | Indecision (like spinning top) | Same as spinning top | n/a |
| Hammer (paper umbrella, bottom of downtrend) | lower shadow ≥ 2× body; small/no upper shadow; open≈close within 1–2% | Bullish | ~close of hammer day | low of hammer |
| Hanging man (paper umbrella, top of uptrend) | lower shadow ≥ 2× body; small/no upper shadow | Bearish | ~close of hanging-man day | high of hanging man |
| Shooting star (top of uptrend) | upper shadow ≥ 2× body; small/no lower shadow | Bearish | ~close of shooting-star day | high of shooting star |

Tolerance rule of thumb (from worked examples in the source): OHLC
deviations up to roughly **0.2–0.5% of price** are acceptable "bald" bodies
for a Marubozu; open/close difference within **1–2% of price** still counts
as "equal" for hammer/hanging-man qualification.

**Entry timing (both single- and multi-candle patterns):**
- *Risk-taker*: validate the pattern intraday near the close (the source uses
  3:20 PM, 10 min before NSE's 3:30 PM close) and enter same-day at/near
  close. Must still respect "buy strength/sell weakness" (candle color must
  match direction), except for Marubozu where the color of the pattern candle
  itself already satisfies this.
- *Risk-averse*: wait for the pattern to complete, then require the **next
  day** to close as a confirming color (blue to go long, red to go short)
  before entering near that day's close. If the confirmation candle is the
  wrong color, **skip the trade entirely.**
- Rule of thumb: the more days a pattern takes to form, the more it's worth
  acting as the risk-taker (don't wait for extra confirmation on 2–3 day
  patterns).

### 1.1 Spinning top / Doji — indecision protocol
No entry/stop is generated directly. Treat as a **position-sizing modifier**:
- In a prior trend (up or down), a spinning top/doji signals the trend may
  pause-and-continue or reverse — each ~50% probability, no edge either way.
- If already in a position: consider trimming ~50% of size to de-risk while
  keeping optionality.
- If flat and want to establish exposure ahead of a suspected reversal: enter
  with **half of intended size**, add the other half only on confirmation in
  your favor.
- Clusters of dojis/spinning tops = amplified indecision; a strong candle
  breaking out of the cluster (especially a doji right after a recognized
  reversal pattern) is a **higher-conviction** signal than the pattern alone.

## 2. Multi-candle patterns (P1 = day 1, P2 = day 2, P3 = day 3)

| Pattern | Prior trend | P1 | P2 | P3 | Bias | Stop |
|---|---|---|---|---|---|---|
| Bullish engulfing | down | red candle | blue candle, body fully engulfs P1 body | — | Bullish | lowest low of P1–P2 |
| Bearish engulfing | up | blue candle | red candle, body fully engulfs P1 body | — | Bearish | highest high of P1–P2 |
| Piercing pattern | down | red candle | blue candle engulfing **50%–<100%** of P1 body | — | Bullish (weaker than engulfing) | low of pattern |
| Dark cloud cover | up | blue candle | red candle engulfing **50%–<100%** of P1 body | — | Bearish (weaker than engulfing) | high of pattern |
| Bullish harami | down | long red candle | small blue candle *inside* P1's body (P2 open > P1 close, P2 close < P1 open) | — | Bullish | lowest low of P1–P2 |
| Bearish harami | up | long blue candle | small red candle *inside* P1's body (P2 open < P1 close, P2 close > P1 open) | — | Bearish | highest high of P1–P2 |
| Morning star | down | long red candle | gap-down open; doji or spinning top | gap-up open, blue candle closing above P1's open | Bullish | lowest low of P1–P3 |
| Evening star | up | long blue candle | gap-up open; doji or spinning top | gap-down open, red candle closing below P1's open | Bearish | highest high of P1–P3 |

Ranking when choosing between competing patterns of similar strength:
**engulfing > piercing/dark-cloud-cover** (full engulf = stronger
conviction than partial). But checklist-point count (§7) can override this
ranking — take the setup with more confirming checklist items even if its
candlestick pattern is "weaker."

Entry timing for multi-day patterns: enter at/near close of the final
pattern day (P2 or P3) — both risk-taker and risk-averse traders are advised
to act on completion day for 3-day (star) patterns; for 2-day patterns
prefer risk-taker behavior (don't wait an extra day).

**A doji appearing right after an engulfing pattern (on the day after P2)
amplifies the signal** — treat as a bonus confidence boost, not a new
pattern.

### Gaps
- **Gap up** (today's open > yesterday's close, no trading between): bullish
  sentiment signal, buyer enthusiasm.
- **Gap down** (today's open < yesterday's close): bearish sentiment signal,
  seller enthusiasm.
- Gaps are structural components of morning/evening star patterns (see
  above) and of Dow-theory breakout/breakdown moves (§5).

## 3. Support & Resistance (S&R) — construction algorithm

Definition: identification method is identical for both; if current market
price (CMP) is **above** the level → it's support, if **below** → it's
resistance.

**4-step construction:**
1. **Load data**: 3–6 months of candles for short-term S&R (intraday/BTST
   use); 12–18 months for long-term S&R (swing-trade use). Widen to **2
   years** when specifically plotting S&R for a swing-trade target.
2. **Identify price-action zones**: points where price (a) hesitated after
   an up-move, (b) hesitated after a down-move, or (c) sharply reversed.
3. **Align ≥ 3 zones** at the same approximate price level, and require they
   be **well spaced in time** (e.g., don't accept two touches a week apart —
   space them by weeks/months). More zones + wider time-spacing = stronger,
   more reliable level.
4. **Fit a horizontal line** through the aligned zones. Treat it as a
   **zone/range**, not a single price — the source's own example pads a
   level by roughly ±3 points around the identified price as a margin of
   error.

**Trade rule**: use resistance as the target for long trades, support as the
target for short trades. Entry + stop from a candlestick pattern + target
from S&R = a fully specified trade (Entry / Stop / Target).

**Reliability filter for the checklist (hard gate)**: if the nearest
qualifying S&R level sits **more than 4% away** from the pattern's stop-loss
price, reject this evaluation path and move to the next opportunity — the
confluence is too weak to trust.

## 4. Volume interpretation

Reference volume = **10-day average volume** (draw a moving average over the
volume bars). High volume = today's volume > 10-day average; Low volume =
today's volume < 10-day average.

| Price | Volume | Read | Action |
|---|---|---|---|
| Up | Up | Bullish — smart money buying | Confirms long |
| Up | Down | Caution — weak-hands/retail rally, possible **bull trap** | Don't chase; discount signal |
| Down | Up | Bearish — smart money selling | Confirms short |
| Down | Down | Caution — weak-hands/retail sell-off, possible **bear trap** | Don't chase; discount signal |

Checklist rule: require **above-average volume on the pattern's signal
day(s)**. Low volume on the signal day is a soft negative (reduce
confidence / hesitate), not necessarily a hard veto — but combined with an
already-weak setup it should tip the decision to no-trade.

## 5. Dow Theory

**9 tenets** (condensed):
1. Index/price discounts everything.
2. Three trend classes exist: **Primary** (year(s)-long), **Secondary**
   (weeks–months counter-trend correction), **Minor/daily** (noise).
3–5. (folded into #2 above — Primary/Secondary/Minor definitions.)
6. All indices/instruments must confirm each other — don't call a broad
   trend from one index/stock alone.
7. Volume must confirm price (see §4).
8. A sideways range can substitute for a secondary trend.
9. **Close is the most sacred price** of the OHLC set.

**3 repeating market phases** (a full cycle spans multiple years, but can
compress to months): **Accumulation** (smart money quietly buys after a
capitulation sell-off — this is how support levels get built) →
**Mark-up** (fast, sharp rally once short-term traders/public notice) →
**Distribution** (smart money quietly sells into public enthusiasm at highs —
this is how resistance levels get built) → **Mark-down** (final sell-off) →
cycle repeats into fresh accumulation.

**Dow patterns:**
| Pattern | Rule | Bias |
|---|---|---|
| Double bottom | Price hits a low, rebounds, holds elevated ≥ ~2 weeks, retests the same low and rebounds again | Bullish reversal |
| Double top | Mirror of double bottom, tested twice with ≥ ~2 weeks spacing | Bearish reversal |
| Triple top/bottom | Same as double, tested a 3rd time — **more powerful** than double (more touches = more sacred level) | Same direction, higher conviction |
| Range / trading range | Price oscillates between a repeated high and repeated low for weeks–years | Buy near range low, sell/short near range high |
| Range breakout | Price closes decisively outside the range | Long above resistance / short below support — **only if "true"** (see below) |
| Flag | Steep rally → 5–15 session shallow pullback in a parallel channel → resumption | Bullish continuation; 2nd chance to enter a missed rally |

**True vs false breakout**: a **true breakout** requires (1) high volume and
(2) high momentum (fast rate of price change) after the break. A **false
breakout** shows low volume — expect price to fall back inside the range;
do not chase it.

**Breakout trade construction**: enter at the breakout price with stop at
the broken range boundary; minimum target = **entry price + range width**
(width = range high − range low), projected in the breakout direction.

## 6. Moving averages

- **SMA** (simple moving average): equal weight to all N points in the
  look-back window; recalculated by dropping the oldest point and adding the
  newest.
- **EMA** (exponential moving average): weights recent data more heavily;
  reacts faster to price. **Prefer EMA over SMA** for trading decisions.

**Single-MA trend system**: Buy when CMP > 50-day EMA, hold; exit when CMP <
50-day EMA. Works well in a trend, generates frequent small-loss whipsaws in
a sideways market — but take *every* signal anyway, because the rare
large-trend trade compensates for many small losses. Do not cherry-pick
signals.

**Crossover system** (reduces sideways-market whipsaws): buy when the
shorter/faster EMA crosses **above** the longer/slower EMA; exit/reverse
when it crosses back below.

| Combo | Use case |
|---|---|
| 9 EMA × 21 EMA | Short-term trades (few sessions) |
| 25 EMA × 50 EMA | Medium-term trades (few weeks) |
| 50 EMA × 100 EMA | Trades lasting a few months |
| 100 EMA × 200 EMA | Long-term/investment-style trades (year+) |
| 5 min × 10 min or 15 min × 30 min | Intraday crossover variants |

Longer time frame chosen → fewer but more reliable signals.

## 7. Indicators

### 7.1 RSI (Relative Strength Index)
`RS = avg(gain over N) / avg(loss over N)`; `RSI = 100 − [100 / (1 + RS)]`.
Default look-back **N = 14** periods (days on daily chart, hours on hourly).
- **RSI < 30** → oversold → look to buy.
- **RSI > 70** → overbought → look to sell/short.
- Personal-preference tightened bands used in the source: **20 / 80**.
- **If RSI stays pinned in overbought/oversold for a long stretch**, that
  signals sustained momentum — trade **with** the trend, not against it
  (don't fade a strong trend just because RSI is "overbought").
- **Reversal tell**: RSI breaking back below 70 (from above) after a
  prolonged overbought stretch, or back above 30 (from below) after a
  prolonged oversold stretch, suggests the move has topped/bottomed —
  now look to trade the reversal.
- RSI gives its strongest signals in sideways/non-trending markets; use as
  confirmation, not standalone.

### 7.2 MACD (Moving Average Convergence Divergence)
Standard settings: **12-day EMA − 26-day EMA = MACD line**; **9-day EMA of
the MACD line = signal line**.
- **Center-line cross**: MACD line crossing from negative → positive =
  rising bullish momentum (buy signal); positive → negative = rising bearish
  momentum (sell signal).
- **Signal-line cross** (faster, preferred over waiting for center-line
  cross): MACD line crossing **above** signal line = bullish; crossing
  **below** = bearish.
- MACD is trend-following at its core (built on EMAs) — works well in
  trending markets, weak in sideways/choppy markets.

### 7.3 Bollinger Bands (BB)
- Middle band = **20-day SMA** of closing price.
- Upper band = middle + **2 standard deviations**.
- Lower band = middle − **2 standard deviations**.
- Mean-reversion trade: **sell/short near the upper band** (target = middle
  band); **buy near the lower band** (target = middle band).
- **Failure mode — envelope expansion**: in a strongly trending move the
  bands widen and price rides the band instead of reverting; if a BB signal
  doesn't work almost immediately, check for expansion and stand down. BB
  works in sideways markets, fails in trending markets (opposite of
  MA/MACD).

### 7.4 Supplementary indicators (secondary confirmation only)
| Indicator | Key numbers | Signal |
|---|---|---|
| ADX (+DI/−DI) | Look-back 14; ADX>25 = strong trend, <20 = weak/no trend, 20–25 = grey zone | Buy: ADX>25 & +DI crosses above −DI. Sell: ADX>25 & −DI crosses above +DI. Stop = low/high of signal candle |
| ATR | Look-back 14 (unbounded value, stock-specific) | Use for **volatility-sized stops**: stop ≥ entry ± ATR. If that stop breaks your RRR budget, skip the trade |
| Aroon / Aroon Oscillator | Look-back 25 (Kite default 14); bounded 0–100 (oscillator −100 to +100) | Buy: Aroon-Up>50 & Aroon-Down<30. Sell: Aroon-Down>50 & Aroon-Up<30. Oscillator >+50 = strong up, <−50 = strong down |
| Supertrend | ATR period default 7, multiplier 3–4 | Long when price crosses above line (line flips green, acts as trailing stop); short when price crosses below (line flips red) |
| VWAP | Intraday only, resets each session | Price>VWAP = intraday bullish bias, price<VWAP = bearish bias. Efficient short fill = above VWAP; efficient long fill = below VWAP |

**Indicators as a class are a sizing multiplier, never a gate**: if
indicators confirm the trade thesis, scale position size up; if they don't
confirm, take the trade at normal/reduced size anyway on the strength of
pattern + S&R + volume. Never let an indicator veto an otherwise-qualified
setup, and never let it single-handedly create one.

## 8. Fibonacci retracements

Key ratios: **23.6%, 38.2%, 61.8%** (derived from the Fibonacci sequence;
61.8%/38.2% relate to the golden ratio 1.618).

**Construction**: identify the most recent significant swing (peak-to-trough
or trough-to-peak) as the 100% move; anchor the retracement tool on the
trough and drag to the peak (or vice versa for a down-move). The tool plots
23.6/38.2/61.8% levels between the two anchors automatically.

**Use**: after a sharp directional move, expect a retracement to stall near
one of these levels before the primary move resumes. Use these levels as
potential entries in the direction of the original move — **but treat as a
confirmation layer only**: don't buy/sell purely because price touched a
Fib level; require it to coincide with pattern + S&R + volume confirmation
first.

## 9. Reward-to-Risk Ratio (RRR) — hard gate

`Risk = |Entry − Stop|`; `Reward = |Target − Entry|`; `RRR = Reward / Risk`.

| Trader profile | Minimum RRR |
|---|---|
| Beginner | As high as possible; be conservative |
| Active/swing trader (source author's own threshold) | **≥ 1.5** |
| Aggressive trader | ≥ 1.0 (accepts breakeven-odds trades) |
| Ultra-cautious | ≥ 2.0 |
| Scalper (exception case) | 0.5–0.75 acceptable |

**A trade that fails your RRR threshold must be dropped regardless of how
good the setup otherwise looks.** This is a hard veto, not a soft
confidence adjustment.

## 10. The Grand Checklist (module's final trade filter)

A trade must satisfy **at least 3–4 of these 6 points** to be considered
"qualified." Points are not equally weighted — pattern quality and S&R
confluence matter more than indicator confirmation.

1. **Recognizable candlestick pattern** present (§1–§2), with prior-trend
   rule respected (except Marubozu).
2. **S&R confirms the trade** — the pattern's stop-loss sits at/near a
   constructed support (long) or resistance (short) level (§3; reject if
   >4% away).
3. **Volume confirms** — above-10-day-average volume on the signal day(s)
   (§4).
4. **Dow Theory perspective aligns** — primary/secondary trend direction
   matches the trade, and/or a Dow pattern (double/triple top-bottom, range,
   flag, breakout) reinforces it (§5).
5. **Indicators confirm** (RSI/MACD/BB alignment, §7) — sizing multiplier
   only, never a gate: confirm → scale size up; don't confirm → take at
   base size.
6. **RRR is satisfactory** for the trader's threshold (§9) — hard gate.

**Operational shortlist process** (for scanning a universe daily):
1. Scan opportunity universe (Nifty 50 is a reasonable default — pre-vetted
   for liquidity, EQ segment, and low operator-manipulation risk) for a
   recognizable candlestick pattern in the last 3–4 candles.
2. For each shortlisted name: verify prior trend, then volume, then S&R
   confluence (reject if stop is >4% from S&R), then Dow-theory context,
   then RRR (reject if below threshold), then check indicators last
   (sizing only).
3. Expect only 1–2 qualifying trades out of ~50 scanned names on a typical
   day. **No qualifying setup = no trade** — this is a valid and disciplined
   outcome, not a failure to find something.
4. Once a trade is live: do nothing until stop or target is hit, except
   trailing the stop. Do not manage the position on discretion mid-trade.

**Universe/liquidity filters** for candidate selection: adequate liquidity
(tight bid-ask spread, or minimum ~5,00,000 shares/day traded), stock must
be in the **EQ** (deliverable, day-tradeable) segment, and avoid suspected
operator-driven counters (qualitative judgment).

**Timeframe defaults**: EOD (end-of-day) candles for swing/positional
trading; look-back 6–12 months for pattern context, extended to 2 years
specifically for S&R construction. Higher timeframe = more reliable signal
(a pattern on a 15-min chart is more trustworthy than the same pattern on a
5-min chart).

---

## Opinion protocol

Every view the technical-analyst agent expresses on an NSE equity **must**
be emitted in this structured form. No free-form "I think this looks
bullish" output is acceptable — always populate all six fields.

### Required output fields
1. **Bias**: `Bullish` / `Bearish` / `Neutral`.
2. **Entry zone**: a price or narrow band (allow the same tolerance as the
   pattern's own quantify-and-verify rule, e.g. ±0.2–0.5% around the
   pattern's completion price).
3. **Stop (invalidation)**: the exact price derived from the pattern rule in
   §1/§2 (never a rounded/guessed number).
4. **Target**: nearest qualifying S&R level (§3), Dow range-width projection
   (§5), Fibonacci confluence level (§8), or BB mean-reversion midline (§7.3)
   — whichever is nearest to entry in the trade direction. State which
   method produced it.
5. **Confidence (0–100)**: computed per the rubric below.
6. **Checklist table**: explicit pass/fail against all 6 Grand Checklist
   items (§10), with the observed value that drove each verdict (e.g.
   "Volume: PASS — 1.4× 10-day avg").

### Decision tree
1. No recognizable pattern (§1/§2) found → **Bias = Neutral**, confidence
   ≤ 10, entry/stop/target = "n/a — no setup," checklist item 1 = FAIL and
   all downstream items marked N/A.
2. Pattern found but prior-trend rule violated (and pattern ≠ Marubozu) →
   discard this pattern, treat as no-setup (go to step 1's output).
3. Pattern is a **spinning top or doji** → **Bias = Neutral**, apply the
   indecision protocol (§1.1): output the half-size-entry/half-size-trim
   recommendation instead of a directional entry/stop/target; confidence
   reflects trend context strength only (max ~50, since there's no
   directional edge).
4. Otherwise, derive Entry/Stop from the pattern (§1/§2), then Target from
   the best available S&R/Fibonacci/Dow/BB method (§3/§5/§7.3/§8).
5. Compute RRR (§9). **If RRR fails the applicable threshold, hard-veto**:
   output the fully-specified setup for transparency but set
   **Bias = Neutral**, cap confidence at 15, and state "RRR veto" as the
   reason — do not present this as an actionable trade.
6. If S&R confluence fails the >4% distance rule (§3), same hard-veto
   treatment, reason "S&R confluence veto."
7. Otherwise compute confidence (rubric below) and emit the directional
   Bias with full entry/stop/target.

### Confidence rubric (0–100, only reached if steps 5–6 don't veto)
| Checklist item | Points if PASS | Notes |
|---|---|---|
| 1. Candlestick pattern + prior trend | 25 | Gate — 0 if fails (routed to step 1/2 above) |
| 2. S&R confluence (stop within 4% of level) | 20 | Gate — routed to veto in step 6 if fails |
| 3. Volume above 10-day average | 15 | Soft — 0 if fails, no veto |
| 4. Dow Theory alignment (trend + pattern) | 15 | Soft — 0 if fails, no veto |
| 5. Indicator confirmation (RSI/MACD/BB) | 10 | Soft, sizing-only — also emit a size-multiplier note (1.0× base if fail, up to 1.5× base if pass) |
| 6. RRR meets threshold | 15 | Gate — routed to veto in step 5 if fails |

Sum passing items' points for the confidence score. Report the checklist
table with each item's PASS/FAIL and the point contribution, so the score is
fully auditable. A score built from only the two hard-gate-adjacent items
plus pattern (25+20+15 = 60 max with volume/Dow/indicator all failing) is a
legitimate but low-conviction trade — say so explicitly in prose alongside
the number (e.g. "60/100 — pattern and S&R only, volume and trend context
did not confirm").

### Presentation rules
- Always state which of risk-taker vs risk-averse entry logic was used, and
  why (default to risk-taker/same-close entry for multi-day patterns per
  §2; allow a risk-averse/next-day-confirmation mode if explicitly
  configured for a more conservative operating profile).
- Never output a bias without an accompanying invalidation price — "bullish,
  no stop given" is not a valid opinion under this protocol.
- If two candidate setups conflict (e.g. one stock shows a stronger
  candlestick pattern but fewer checklist confirmations than another), state
  the checklist-point comparison explicitly and prefer the higher
  checklist-point count over the "textbook-prettier" pattern, per §2's
  ranking-override rule.
- Re-run the full decision tree on every new candle close; do not carry
  forward a stale bias once the underlying candle data has moved past the
  pattern's validity window.
