# Groww Trade API — Python SDK Integration Reference

Source: https://groww.in/trade-api/docs/python-sdk (+ instruments, orders, smart-orders,
portfolio, margin, live-data, historical-data, backtesting, feed, annexures, exceptions
sub-pages). Fetched 2026-07-24. This is a decision-oriented reference for the autonomous
trading desk, not a full API dump — it covers exactly what's needed to quote, place,
confirm, and account for CNC equity swing trades on NSE, plus short notes on adjacent
capabilities. Where the docs were ambiguous, incomplete, or a claim could not be
verified verbatim from a fetched page, it is flagged explicitly rather than guessed.

---

## 1. Install + Auth

### Package

```
pip install growwapi
```

- Package name: **`growwapi`**
- Requires Python 3.9+
- Upgrade: `pip install --upgrade growwapi`

### Auth flow A — API key + secret

Key pair generated on Groww's "Cloud API Keys" page; per the docs **requires daily
approval** (verbatim wording from the overview page) — implying re-approval/regeneration
on a daily cadence. No exact hour-based expiry is stated anywhere in the fetched docs.

```python
from growwapi import GrowwAPI
import pyotp

api_key = "YOUR_API_KEY"
secret = "YOUR_API_SECRET"

access_token = GrowwAPI.get_access_token(api_key=api_key, secret=secret)
groww = GrowwAPI(access_token)
```

### Auth flow B — TOTP (preferred for an unattended desk)

Uses a TOTP token + a `pyotp`-generated one-time code. The docs state this flow has
**"No Expiry"** (verbatim) — explicit contrast to flow A's daily-approval requirement.

```
pip install pyotp
```

```python
from growwapi import GrowwAPI
import pyotp

api_key = "YOUR_TOTP_TOKEN"
totp_gen = pyotp.TOTP('YOUR_TOTP_SECRET')
totp = totp_gen.now()

access_token = GrowwAPI.get_access_token(api_key=api_key, totp=totp)
groww = GrowwAPI(access_token)
```

### AMBIGUITY FLAG — token validity/expiry

Fetched pages do **not** state an explicit access-token lifetime (no "valid for N hours").
Only documented facts: API-key/secret flow "requires daily approval"; TOTP flow "No
Expiry." Do not assume a specific TTL for the API-key/secret token. Treat it as needing
regeneration at least once per calendar day and verify with a live call before trusting a
cached token across days; TOTP is the safer choice for autonomous, unattended use.

---

## 2. Minimal method subset for a swing-trading desk

All calls below hang off a single authenticated client:

```python
groww = GrowwAPI(access_token)
```

Enum values are accessed as attributes on the `groww` instance (e.g. `groww.EXCHANGE_NSE`)
per every code sample in the docs — the Annexures page also shows a
`GrowwAPI.PRODUCT_CNC`-style class-constant form. Use the instance-attribute form to match
the Orders/Live Data/Portfolio samples exactly.

### 2.1 Trading-symbol / instrument format — READ THIS FIRST

Groww uses **three different symbol formats** depending on which API you call. Getting
this wrong is the single most likely integration bug:

| Context | Format | Example |
|---|---|---|
| `place_order` / `modify_order` / order APIs | plain trading symbol, **no exchange prefix** (`trading_symbol=` param, paired with a separate `exchange=` param) | `"RELIANCE"` |
| `get_quote` (Live Data) | plain trading symbol + separate `exchange=` param | `"RELIANCE"` |
| `get_ltp` (Live Data) | exchange-prefixed string, underscore-joined | `"NSE_RELIANCE"` |
| `get_instrument_by_groww_symbol` (Instruments) | exchange-prefixed, hyphen-joined "Groww symbol" | `"NSE-RELIANCE"` |
| Backtesting `groww_symbol` (derivatives) | exchange + symbol + expiry (`DDMmmYY`) + strike + CE/PE/FUT, hyphen-joined | `"NSE-NIFTY-30Sep25-FUT"`, `"NSE-NIFTY-30Sep25-24650-CE"` |

So: for **placing orders and quoting a single equity symbol**, pass the *plain*
`trading_symbol` (e.g. `"RELIANCE"`, `"WIPRO"`) plus a separate `exchange=groww.EXCHANGE_NSE`
— no instrument-token needed. The hyphenated `"NSE-RELIANCE"` Groww-symbol format is only
for the lookup-by-symbol convenience method and backtesting/derivatives symbol
construction. `get_ltp` is the one outlier wanting an underscore-joined `"NSE_RELIANCE"`
string instead of two separate params.

### 2.2 Instrument lookup (Instruments API)

```python
groww.get_instrument_by_groww_symbol(groww_symbol="NSE-RELIANCE")

groww.get_instrument_by_exchange_and_trading_symbol(
    exchange=groww.EXCHANGE_NSE,
    trading_symbol="RELIANCE"
)

groww.get_instrument_by_exchange_token(exchange_token="2885")

instruments_df = groww.get_all_instruments()
```

`get_all_instruments()` pulls the full instrument master (also downloadable directly as
CSV from `https://growwapi-assets.groww.in/instruments/instrument.csv`). Relevant columns:
`exchange_token`, `trading_symbol` ("the trading symbol ... to place orders with"),
`groww_symbol`, `segment`, `lot_size`.

For a swing desk trading known NSE tickers, `get_instrument_by_exchange_and_trading_symbol`
is the one to call before first trading a new symbol, to confirm it exists and pull its
`exchange_token` / `lot_size` / `segment`.

### 2.3 Quote / LTP (single symbol)

Two distinct calls — pick based on whether you need OHLC/depth or just a price:

```python
# Full quote (OHLC, bid/offer, volume, day change, etc.)
quote_response = groww.get_quote(
    exchange=groww.EXCHANGE_NSE,
    segment=groww.SEGMENT_CASH,
    trading_symbol="RELIANCE"
)
```
Signature: `get_quote(exchange, segment, trading_symbol)` — all required.
Key response fields: `last_price`, `day_change`, `day_change_perc`, `ohlc`,
`bid_price`/`bid_quantity`, `offer_price`/`offer_quantity`, `volume`, `open_interest`,
`market_cap`.

```python
# Lightweight LTP-only call, supports up to 50 symbols at once
ltp_response = groww.get_ltp(
    segment=groww.SEGMENT_CASH,
    exchange_trading_symbols="NSE_RELIANCE"
)
```
Signature: `get_ltp(segment, exchange_trading_symbols)` — `exchange_trading_symbols` is
documented as a tuple capable of holding up to 50 entries, each in `"EXCHANGE_SYMBOL"`
form (e.g. `"NSE_RELIANCE"`); a single string also works for one symbol per the sample.
Returns a dict mapping symbol → float price.

For a fill-execution quote before placing an order, `get_quote` is the better call (it
gives you bid/offer, not just last price) — `get_ltp` is cheaper for a fast last-price
check across many symbols at once.

### 2.4 Place order — market and limit, CNC equity, NSE

Full signature, verbatim from docs:

```python
place_order(
    trading_symbol,      # string, required
    quantity,            # int, required
    validity,            # string, required
    exchange,            # string, required
    segment,             # string, required
    product,             # string, required
    order_type,          # string, required
    transaction_type,    # string, required
    price=None,          # float, optional (required for LIMIT orders)
    trigger_price=None,  # float, optional (for SL / SL_M orders)
    order_reference_id=None  # string, optional — 8-20 chars, max 2 hyphens
)
```

Limit-order example from the docs (verbatim, WIPRO):

```python
place_order_response = groww.place_order(
    trading_symbol="WIPRO",
    quantity=1,
    validity=groww.VALIDITY_DAY,
    exchange=groww.EXCHANGE_NSE,
    segment=groww.SEGMENT_CASH,
    product=groww.PRODUCT_CNC,
    order_type=groww.ORDER_TYPE_LIMIT,
    transaction_type=groww.TRANSACTION_TYPE_BUY,
    price=250,
    trigger_price=245,
    order_reference_id="Ab-654321234-1628190"
)
```

Market-order form (CNC delivery buy on NSE) — same call, `order_type` swapped, `price`/
`trigger_price` omitted. Note: the docs only show `groww.ORDER_TYPE_MARKET` used in the
`modify_order` sample, not in a fresh `place_order` sample — the snippet below is a
direct, low-risk extrapolation from the documented `place_order` signature plus the
documented `ORDER_TYPE_MARKET` constant, not a verbatim docs snippet:

```python
place_order_response = groww.place_order(
    trading_symbol="RELIANCE",
    quantity=1,
    validity=groww.VALIDITY_DAY,
    exchange=groww.EXCHANGE_NSE,
    segment=groww.SEGMENT_CASH,
    product=groww.PRODUCT_CNC,
    order_type=groww.ORDER_TYPE_MARKET,
    transaction_type=groww.TRANSACTION_TYPE_BUY,
)
```

**Enum values (verbatim from the Annexures page):**

- `transaction_type`: `TRANSACTION_TYPE_BUY`, `TRANSACTION_TYPE_SELL`
- `order_type`: `ORDER_TYPE_LIMIT` (`LIMIT`), `ORDER_TYPE_MARKET` (`MARKET`),
  `ORDER_TYPE_STOP_LOSS` (`SL`), `ORDER_TYPE_STOP_LOSS_MARKET` (`SL_M`)
- `product`: `PRODUCT_CNC` (`CNC`), `PRODUCT_MIS` (`MIS`), `PRODUCT_NRML` (`NRML`)
- `validity`: `VALIDITY_DAY` (`DAY`) — this is the **only** validity value the fetched
  pages surfaced; no IOC/GTC values were found, flag as possibly incomplete.
- `exchange`: `EXCHANGE_NSE` (`NSE`), `EXCHANGE_BSE` (`BSE`), `EXCHANGE_MCX` (`MCX`)
- `segment`: `SEGMENT_CASH` (`CASH`), `SEGMENT_FNO` (`FNO`), `SEGMENT_COMMODITY` (`COMMODITY`)

For the desk's default equity swing trade: `exchange=groww.EXCHANGE_NSE`,
`segment=groww.SEGMENT_CASH`, `product=groww.PRODUCT_CNC`.

### 2.5 Order status / detail

```python
get_order_status(groww_order_id, segment)          # lightweight status only
get_order_status_by_reference(order_reference_id, segment)  # lookup by your own ref id
get_order_detail(groww_order_id, segment)           # full order detail
get_order_list(segment=None, page=0, page_size=100) # page_size max 100
get_trade_list_for_order(groww_order_id, segment, page=0, page_size=50)  # page_size max 50
```

`get_order_status` is the cheap poll to confirm a fill; `get_order_detail` is the fuller
record if you need average fill price / remaining quantity / rejection reason.
`order_reference_id` (set at placement time) lets you look up an order without having
stored the Groww-assigned `groww_order_id` — useful if the placement call itself times
out and you need to reconcile afterward.

### 2.6 Cancel order

```python
cancel_order_response = groww.cancel_order(
    segment=groww.SEGMENT_CASH,
    groww_order_id="GMK39038RDT490CCVRO",
)
```
Signature: `cancel_order(segment, groww_order_id)` — both required.

(Modify, for completeness: `modify_order(quantity, order_type, segment, groww_order_id,
price=None, trigger_price=None)`.)

### 2.7 Holdings

```python
groww.get_holdings_for_user(timeout=5)
```
`timeout` optional (seconds). Response fields include `isin`, `trading_symbol`,
`quantity`, `average_price`, `demat_free_quantity` (available to sell/trade),
plus `pledge_quantity`, `demat_locked_quantity`, `groww_locked_quantity` for
restricted quantity accounting.

### 2.8 Positions

```python
groww.get_positions_for_user(segment=None)
groww.get_position_for_trading_symbol(trading_symbol, segment)
```
`segment` filter accepts `SEGMENT_CASH` / `SEGMENT_FNO` / `SEGMENT_COMMODITY`. Response
includes `quantity`, `credit_quantity`/`debit_quantity`, `credit_price`/`debit_price`,
`net_price`, `carry_forward_credit_quantity`, `realised_pnl`.

### 2.9 Available margin

```python
available_margin_details_response = groww.get_available_margin_details()
```
No parameters. Key fields (all in rupees): `clear_cash`, `net_margin_used`,
`brokerage_and_charges`, `collateral_used`, `adhoc_margin`; equity-specific:
`net_equity_margin_used`, `cnc_margin_used`, `cnc_balance_available` (the field the
desk should check before sizing a new CNC buy), `mis_margin_used`,
`mis_balance_available`; F&O-specific: `net_fno_margin_used`, `span_margin_used`,
`exposure_margin_used`, `future_balance_available`, `option_buy_balance_available`,
`option_sell_balance_available`.

---

## 3. Adjacent capabilities (brief notes)

### 3.1 Smart orders — GTT / stop-loss, server-side

**Yes** — the docs confirm server-side triggered orders exist, in two forms:
- **GTT (Good Till Triggered)**: "Triggers a single order when price crosses your
  trigger" (verbatim).
- **OCO (One Cancels the Other)**: "Places target and stop-loss together" (verbatim) —
  i.e. a bracket where hitting either the target or the stop cancels the other leg.

```python
groww.create_smart_order(
    smart_order_type,   # "GTT" or "OCO"
    reference_id,       # 8-20 char alphanumeric, max 2 hyphens
    segment,            # "CASH" or "FNO"
    trading_symbol,
    quantity,
    product_type,
    exchange,
    duration
)
groww.modify_smart_order(smart_order_id, smart_order_type, segment, ...)
groww.cancel_smart_order(segment, smart_order_type, smart_order_id)
groww.get_smart_order(segment, smart_order_type, smart_order_id)
groww.get_smart_order_list(segment, smart_order_type, status, page, page_size,
                            start_date_time, end_date_time)
```
Status constants: `SMART_ORDER_STATUS_ACTIVE`, `_TRIGGERED`, `_CANCELLED`, `_EXPIRED`,
`_FAILED`, `_COMPLETED`. **`COMMODITY` segment is explicitly not supported for Smart
Orders** (verbatim from docs). This means the desk *can* offload stop-loss management to
Groww's server instead of polling and firing its own market-sell on breach — worth
evaluating as a follow-up once the plain order flow is proven, since it removes desk
uptime as a dependency for stop execution.

### 3.2 Historical data (candles)

`get_historical_candle_data` is flagged in the docs as **"deprecated and will be removed
in future releases," replaced by `get_historical_candles`** — but its exact
signature/parameters were not shown on the historical-data page; only the backtesting
page shows a `get_historical_candles` signature, in the context of backtesting/FNO data.
AMBIGUITY FLAG: unclear whether that's the same general-purpose replacement or
backtesting-specific — verify before relying on it. Interval-vs-lookback table (from the
deprecated method):

| Interval | Max query span | History available |
|---|---|---|
| 1 min | 7 days | last 3 months |
| 5 min | 15 days | last 3 months |
| 10 min | 30 days | last 3 months |
| 1 hour (60 min) | 150 days | last 3 months |
| 4 hour (240 min) | 365 days | last 3 months |
| 1 day (1440 min) | ~3 years | full history |
| 1 week (10080 min) | no limit | full history |

Old (deprecated) signature: `get_historical_candle_data(trading_symbol, exchange,
segment, start_time, end_time, interval_in_minutes)`; candle rows are
`[epoch_second, open, high, low, close, volume]`. `start_time`/`end_time` accept
`"YYYY-MM-DD HH:mm:ss"` strings or epoch milliseconds.

### 3.3 Live feed (websocket) — note only, not used initially

`GrowwFeed` class wraps a websocket-style feed, built on a `GrowwAPI` instance. Supports
up to 1000 concurrent instrument subscriptions. Subscribe/poll pairs exist for LTP
(`subscribe_ltp`/`get_ltp`), index values, market depth (5-level `buyBook`/`sellBook`),
and — notably — **order and position update streams**
(`subscribe_equity_order_updates`/`get_equity_order_update`,
`subscribe_fno_order_updates`, `subscribe_fno_position_updates`), which return `qty`,
`filledQty`, `avgFillPrice`, `orderStatus`, `exchangeOrderId`. Two consumption patterns:
blocking `feed.consume()` with callbacks, or manual polling of `get_*()` methods. Not
needed for the desk's current polling-based swing cadence; worth reconsidering only if
fill-confirmation latency becomes a problem.

### 3.4 Backtesting module — note only

Purpose per docs: "Fetch historical candle data and instrument information for
backtesting trading strategies using Groww APIs." Supports CASH and FNO segments only.
Uses the hyphenated Groww-symbol format (`NSE-WIPRO`, `NSE-NIFTY-30Sep25-FUT`,
`NSE-NIFTY-30Sep25-24650-CE`). Key methods: `get_expiries(exchange, underlying_symbol,
year=None, month=None)`, `get_contracts(exchange, underlying_symbol, expiry_date)`,
`get_historical_candles(exchange, segment, groww_symbol, start_time, end_time,
candle_interval)` → rows of `[timestamp, open, high, low, close, volume, open_interest]`.
Data-span limits: 1-5 min bars → 30 days max per query; 10-30 min → 90 days; hourly+ →
180 days. Not needed for live execution; useful later for strategy validation against
FNO instruments specifically.

### 3.5 Rate limits and exceptions

Rate limits (verbatim from the SDK overview page): **Orders** 10 req/s, 250/min;
**Live Data** 10 req/s, 300/min; **Non-Trading** (holdings/positions/margin/instruments)
20 req/s, 500/min.

Exception classes (from the separate Exceptions page — not one of the 10 originally
listed, fetched as a direct follow-on since it's load-bearing for error handling):
`GrowwBaseException` (base), `GrowwAPIException` (client errors),
`GrowwAPIAuthenticationException`, `GrowwAPIAuthorisationException`,
`GrowwAPIBadRequestException`, `GrowwAPINotFoundException`, `GrowwAPIRateLimitException`,
`GrowwAPITimeoutException`, `GrowwFeedException` (base), `GrowwFeedConnectionException`,
`GrowwFeedNotSubscribedException`.

Adapter should catch `GrowwAPIRateLimitException` (back off, retry),
`GrowwAPITimeoutException` (retry idempotently via `order_reference_id`, reconcile via
`get_order_status_by_reference`), and `GrowwAPIAuthenticationException` (refresh token)
as distinct paths, not one catch-all.

---

## Adapter contract

Checklist mapping desk needs to Groww SDK calls. Build the adapter around these calls only
— everything else in this doc is optional/future.

- **Auth / session bring-up**
  - [ ] Generate `access_token` via `GrowwAPI.get_access_token(api_key=..., totp=...)`
        (TOTP flow preferred — "No Expiry" per docs, avoids a daily manual step that the
        API-key/secret flow requires).
  - [ ] Construct client: `groww = GrowwAPI(access_token)`.
  - [ ] **Daily token-refresh ritual**: since the docs do not state a hard TTL for either
        flow, the adapter should regenerate/validate the access token at the start of
        every wake cycle (not just once and cache indefinitely), and treat
        `GrowwAPIAuthenticationException` on any call as a signal to regenerate
        immediately and retry once.

- **Instrument resolution (once per new symbol, cache the result)**
  - [ ] `groww.get_instrument_by_exchange_and_trading_symbol(exchange=groww.EXCHANGE_NSE, trading_symbol=SYMBOL)`
        to confirm the symbol is tradeable and fetch `lot_size`/`segment`/`exchange_token`.

- **Fill-execution quote (pre-trade price check)**
  - [ ] `groww.get_quote(exchange=groww.EXCHANGE_NSE, segment=groww.SEGMENT_CASH, trading_symbol=SYMBOL)`
        → use `last_price`, `bid_price`, `offer_price` to sanity-check against the
        analyst-proposed entry before firing the order.

- **Place CNC market order (primary execution path)**
  - [ ] `groww.place_order(trading_symbol=SYMBOL, quantity=QTY, validity=groww.VALIDITY_DAY, exchange=groww.EXCHANGE_NSE, segment=groww.SEGMENT_CASH, product=groww.PRODUCT_CNC, order_type=groww.ORDER_TYPE_MARKET, transaction_type=groww.TRANSACTION_TYPE_BUY, order_reference_id=<desk-generated 8-20 char id>)`
  - [ ] Always set `order_reference_id` — it's the only way to reconcile a placement
        that times out (`GrowwAPITimeoutException`) without duplicating the order.
  - [ ] Limit-order variant: same call, `order_type=groww.ORDER_TYPE_LIMIT`, add `price=`.

- **Confirm fill status (post-trade)**
  - [ ] Poll `groww.get_order_status(groww_order_id, segment=groww.SEGMENT_CASH)` until a
        terminal state; fall back to
        `groww.get_order_status_by_reference(order_reference_id, segment=groww.SEGMENT_CASH)`
        if the `groww_order_id` from the placement response was never received (timeout
        case).
  - [ ] Pull `groww.get_order_detail(...)` for average fill price / rejection reason if
        the order didn't fill exactly as expected.
  - [ ] Cancel path if needed: `groww.cancel_order(segment=groww.SEGMENT_CASH, groww_order_id=...)`.

- **Read holdings (position truth for the book)**
  - [ ] `groww.get_holdings_for_user()` → reconcile `trading_symbol`, `quantity`,
        `average_price`, `demat_free_quantity` against the desk's internal ledger every
        cycle.

- **Read margin (sizing gate before every new order)**
  - [ ] `groww.get_available_margin_details()` → check `cnc_balance_available` /
        `clear_cash` before sizing a new CNC buy; never place an order that would exceed
        available margin.

- **Server-side protective orders (optional, evaluate before relying on)**
  - [ ] If/when the desk wants exchange-side stop-loss instead of self-managed polling
        exits: `groww.create_smart_order(smart_order_type="OCO", ...)` for a
        target+stop-loss bracket, or `smart_order_type="GTT"` for a single trigger order.
        Not wired into the adapter yet — flagged here as available, not adopted.
