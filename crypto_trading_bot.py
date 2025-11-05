import yfinance as yf
import pandas as pd
import datetime
import requests
import numpy as np
import json
import os
import time

# === Telegram Setup ===
TELEGRAM_TOKEN = "8537811183:AAF4DWeA5Sks86mBISJvS1iNvLRpkY_FgnA"
CHAT_ID = "8191014589"

# === File to store sent signals ===
sent_file = "sent_signals.json"
if os.path.exists(sent_file):
    with open(sent_file, "r") as f:
        sent_signals = json.load(f)
else:
    sent_signals = {}

def send_telegram_message(message):
    """Send message to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=data)
        print("✅ Telegram Alert Sent!")
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

print(f"📈 Buy-the-Dip Scanner Started - {datetime.datetime.utcnow():%Y-%m-%d %H:%M UTC}\n")

def check_signals():
    global sent_signals
    summary = []

    for name, ticker in pairs.items():
        try:
            data = yf.download(ticker, period="30d", interval="1d", progress=False)

            if data.empty:
                print(f"⚠️ No data for {name}")
                continue

            close = data["Close"]
            high = data["High"]
            low = data["Low"]

            # Calculate drop %
            swing_high = float(high.max())
            current_price = float(close.iloc[-1])
            drop_pc = ((swing_high - current_price) / swing_high) * 100

            # === RSI ===
            delta = close.diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            avg_gain = gain.rolling(window=14, min_periods=1).mean()
            avg_loss = loss.rolling(window=14, min_periods=1).mean()
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = float(round(rsi.iloc[-1], 2))

            # === Signal Logic ===
            signal = None
            if drop_pc >= 3.5 and current_rsi <= 30:
                signal = "STRONG BUY 💎"
            elif 2 <= drop_pc < 3.5 and 30 < current_rsi <= 45:
                signal = "MODERATE BUY ✅"

            # === Avoid duplicate alerts ===
            if signal:
                key = f"{name}_{datetime.date.today()}"
                if sent_signals.get(key) != signal:
                    msg = (f"Omstrading:\n📊 *{signal} ALERT!* {name}\n"
                           f"Drop: {drop_pc:.2f}% | RSI: {current_rsi}\n"
                           f"Price: {current_price:.5f}")
                    send_telegram_message(msg)
                    sent_signals[key] = signal

            summary.append([
                name, round(current_price, 5), round(drop_pc, 2),
                current_rsi, signal or "WAIT ⚠️"
            ])

        except Exception as e:
            print(f"❌ Error fetching {name}: {e}")

    # Save updated sent signals
    with open(sent_file, "w") as f:
        json.dump(sent_signals, f)

    if summary:
        df = pd.DataFrame(summary, columns=["Pair", "Price", "Drop %", "RSI", "Signal"])
        print(df.to_string(index=False))
    else:
        print("⚠️ No valid data received.")

# === Run once ===
check_signals()

# === Optional auto loop (uncomment for 24/7) ===
# while True:
#     check_signals()
#     print("\n⏳ Waiting 30 minutes before next scan...\n")
#     time.sleep(1800)
