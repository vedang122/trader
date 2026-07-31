"""Market data via yfinance (NSE symbols get a .NS suffix) plus indicator math."""
import sys

import pandas as pd
import yfinance as yf

INDEX_MAP = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "INDIAVIX": "^INDIAVIX",
             "USDINR": "USDINR=X", "GOLD": "GC=F", "CRUDE": "CL=F", "DXY": "DX-Y.NYB"}


def yf_symbol(symbol: str) -> str:
    s = symbol.upper()
    if s in INDEX_MAP:
        return INDEX_MAP[s]
    if s.startswith("^") or "=" in s or s.endswith(".NS"):
        return s
    return s + ".NS"


def get_ohlcv(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    df = yf.download(yf_symbol(symbol), period=period, interval=interval,
                     progress=False, auto_adjust=True, multi_level_index=False)
    if df is not None and not df.empty:
        df = df.dropna(subset=["Close"])  # yfinance emits NaN rows pre-open
    if df is None or df.empty:
        raise RuntimeError(f"no data for {symbol}")
    return df


def last_price(symbol: str) -> float:
    df = get_ohlcv(symbol, period="5d", interval="1d")
    return float(df["Close"].iloc[-1])


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-9)
    return 100 - 100 / (1 + rs)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift()).abs(),
        (df["Low"] - df["Close"].shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def snapshot(symbol: str) -> dict:
    """One-symbol technical snapshot: everything the desk needs to triage a chart."""
    df = get_ohlcv(symbol, period="1y", interval="1d")
    c = df["Close"]
    last, prev = float(c.iloc[-1]), float(c.iloc[-2])
    sma20, sma50 = c.rolling(20).mean(), c.rolling(50).mean()
    sma200 = c.rolling(200).mean()
    ema12, ema26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_sig = macd.ewm(span=9, adjust=False).mean()
    vol = df["Volume"]
    a = atr(df)
    high52, low52 = float(df["High"].max()), float(df["Low"].min())
    return {
        "symbol": symbol.upper(),
        "last": round(last, 2),
        "change_pct": round((last / prev - 1) * 100, 2),
        "rsi14": round(float(rsi(c).iloc[-1]), 1),
        "sma20": round(float(sma20.iloc[-1]), 2),
        "sma50": round(float(sma50.iloc[-1]), 2),
        "sma200": round(float(sma200.iloc[-1]), 2) if not pd.isna(sma200.iloc[-1]) else None,
        "macd_hist": round(float((macd - macd_sig).iloc[-1]), 2),
        "macd_cross": "bullish" if macd.iloc[-1] > macd_sig.iloc[-1] else "bearish",
        "atr14": round(float(a.iloc[-1]), 2),
        "vol_ratio_20d": round(float(vol.iloc[-1] / max(vol.rolling(20).mean().iloc[-1], 1)), 2),
        "pos_52w_pct": round((last - low52) / max(high52 - low52, 1e-9) * 100, 1),
        "high_52w": round(high52, 2),
        "low_52w": round(low52, 2),
        "trend": ("up" if last > sma50.iloc[-1] > (sma200.iloc[-1] if not pd.isna(sma200.iloc[-1]) else 0)
                  else "down" if last < sma50.iloc[-1] else "sideways"),
    }


if __name__ == "__main__":
    import json
    cmd = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    sym = sys.argv[2] if len(sys.argv) > 2 else "NIFTY"
    if cmd == "quote":
        print(json.dumps({"symbol": sym, "last": last_price(sym)}))
    elif cmd == "snapshot":
        print(json.dumps(snapshot(sym), indent=2))
    elif cmd == "ohlcv":
        print(get_ohlcv(sym, period=sys.argv[3] if len(sys.argv) > 3 else "3mo").tail(60).to_string())
