"""
Buy-The-Dip Swing Tracker (Replit-ready)
---------------------------------------
Fetches daily OHLC data for 10 forex/metal pairs using Yahoo Finance.
Computes % drop from recent swing high, RSI(14), ATR(14), and emits signals.

Signals:
- BUY ZONE ✅   : 2.5% <= drop <= 3.5%  AND RSI < 35
- OVERSOLD ⚡   : drop > 3.5%           AND RSI < 30
- WAIT ⚠️       : drop < 2.5%
"""

import os, math, time
from datetime import datetime, timedelta
import pandas as pd, numpy as np

try:
    import yfinance as yf
except:
    print("Install with: pip install yfinance")
    raise

# ----- CONFIG -----
PAIRS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "USDCAD=X",
    "NZD/USD": "NZDUSD=X",
    "XAU/USD": "GC=F",     # Gold futures
    "XAG/USD": "SI=F",     # Silver futures
    "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X",
}

LOOKBACK_HIGH_DAYS = 20
RSI_PERIOD = 14
ATR_PERIOD = 14
MIN_DROP_PC = 2.5
MAX_DROP_PC = 3.5
RSI_BUY_THRESHOLD = 35
RSI_OVERSOLD_THRESHOLD = 30
SLEEP_BETWEEN = 0.5

# Optional Telegram alerts
TELEGRAM_TOKEN = os.getenv("7615583534:AAHaKfWLN7NP83LdmR32i6BfNWqq73nBsAE", "")
TELEGRAM_CHAT_ID = os.getenv("1002689167916", "")

# ----- UTILITIES -----
def compute_rsi(series, period=14):
    delta = series.diff()
    up, down = delta.clip(lower=0), -delta.clip(upper=0)
    ma_up, ma_down = up.rolling(period).mean(), down.rolling(period).mean()
    rs = ma_up / ma_down
    return 100 - (100 / (1 + rs))

def compute_atr(df, period=14):
    tr = pd.concat([
        df['High'] - df['Low'],
        (df['High'] - df['Close'].shift()).abs(),
        (df['Low'] - df['Close'].shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def fetch_ohlc(ticker, days=60):
    end, start = datetime.utcnow(), datetime.utcnow() - timedelta(days=days)
    df = yf.download(ticker, start=start.strftime("%Y-%m-%d"),
                     end=end.strftime("%Y-%m-%d"), progress=False)
    if df.empty:
        raise RuntimeError(f"No data for {ticker}")
    return df[['Open','High','Low','Close','Volume']].dropna()

def analyze_pair(name, ticker):
    df = fetch_ohlc(ticker, LOOKBACK_HIGH_DAYS + 30)
    df['RSI'] = compute_rsi(df['Close'], RSI_PERIOD)
    df['ATR'] = compute_atr(df, ATR_PERIOD)
    latest = df.iloc[-1]
    swing_high = df['High'].rolling(LOOKBACK_HIGH_DAYS).max().iloc[-1]
    drop_pc = ((swing_high - latest['Close']) / swing_high) * 100
    rsi = round(latest['RSI'], 2)
    signal = "NO SIGNAL"
    if MIN_DROP_PC <= drop_pc <= MAX_DROP_PC and rsi < RSI_BUY_THRESHOLD:
        signal = "BUY ZONE ✅"
    elif drop_pc > MAX_DROP_PC and rsi < RSI_OVERSOLD_THRESHOLD:
        signal = "OVERSOLD ⚡"
    elif drop_pc < MIN_DROP_PC:
        signal = "WAIT ⚠️"
    return {
        "pair": name, "ticker": ticker, "price": round(latest['Close'], 4),
        "swing_high": round(swing_high, 4), "drop_pc": round(drop_pc, 2),
        "rsi": rsi, "atr": round(latest['ATR'], 5),
        "signal": signal, "date": str(latest.name.date())
    }

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try:
        requests.post(url, json=data, timeout=10)
        return True
    except Exception as e:
        print("Telegram error:", e)
        return False

# ----- MAIN -----
def main():
    print("Buy-the-Dip Scanner running at", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))
    results = []
    for n, t in PAIRS.items():
        print(f"Fetching {n}...", end=" ")
        try:
            res = analyze_pair(n, t)
            results.append(res)
            print("OK")
        except Exception as e:
            results.append({"pair": n, "error": str(e)})
            print("ERR:", e)
        time.sleep(SLEEP_BETWEEN)

    df = pd.DataFrame(results)
    print("\nSummary:\n", df[['pair','price','drop_pc','rsi','signal']].to_string(index=False))
    alerts = [r for r in results if r.get("signal") in ("BUY ZONE ✅", "OVERSOLD ⚡")]
    if alerts:
        msg = "\n\n".join([f"<b>{r['pair']}</b> {r['signal']} | Drop {r['drop_pc']}% | RSI {r['rsi']}" for r in alerts])
        send_telegram(msg)

if __name__ == "__main__":
    main()
