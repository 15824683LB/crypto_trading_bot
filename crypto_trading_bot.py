import os
import yfinance as yf
import pandas as pd
import datetime
import requests
import time

# === Telegram Setup ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram_message(message):
    """Send message to Telegram"""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram not configured; skipping send.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, data=data, timeout=10)
        if r.status_code == 200:
            print("✅ Telegram Alert Sent!")
        else:
            print("⚠️ Telegram Error:", r.text)
    except Exception as e:
        print("⚠️ Telegram Send Failed:", e)

# === Forex Pairs ===
pairs = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "USDCAD=X",
    "NZD/USD": "NZDUSD=X",
    "XAU/USD": "GC=F",
    "XAG/USD": "SI=F",
    "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X"
}

def run_scanner():
    print(f"\n🕒 Running Buy-the-Dip Scanner at {datetime.datetime.utcnow():%Y-%m-%d %H:%M UTC}\n")
    summary = []

    for name, ticker in pairs.items():
        try:
            print(f"Fetching {name}...", end=" ")
            data = yf.download(ticker, period="30d", interval="1d", progress=False)
            if data.empty:
                print("No data ❌")
                continue

            close = data["Close"].dropna()
            high = data["High"].dropna()
            low = data["Low"].dropna()

            current_price = close.iloc[-1]
            swing_high = high.max()
            drop_pc = ((swing_high - current_price) / swing_high) * 100

            # --- RSI Calculation ---
            delta = close.diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            avg_gain = gain.rolling(14).mean()
            avg_loss = loss.rolling(14).mean()
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = round(rsi.iloc[-1], 2) if not pd.isna(rsi.iloc[-1]) else 50.0

            # --- ATR Calculation ---
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]

            # --- Signal Logic ---
            signal = "WAIT ⚠️"
            if drop_pc >= 2 and current_rsi <= 45:
                signal = "BUY ZONE ✅"
                msg = f"📊 *BUY ALERT!* {name}\nDrop: {drop_pc:.2f}% | RSI: {current_rsi}\nPrice: {current_price:.5f}"
                send_telegram_message(msg)

            summary.append([
                name, ticker, round(current_price, 5), round(swing_high, 5),
                round(drop_pc, 2), current_rsi, round(atr, 5), signal
            ])
            print("OK ✅")

        except Exception as e:
            print(f"ERR: {e}")

    if summary:
        df = pd.DataFrame(summary, columns=["pair", "ticker", "price", "swing_high", "drop_pc", "rsi", "atr", "signal"])
        print("\nSummary:\n", df.to_string(index=False))
    else:
        print("\n⚠️ No valid data found for any pair.")

# === Auto-run every 1 hour ===
while True:
    run_scanner()
    print("\n⏳ Waiting 1 hour before next scan...\n")
    time.sleep(3600)
