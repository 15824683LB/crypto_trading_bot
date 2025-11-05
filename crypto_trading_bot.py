import yfinance as yf
import pandas as pd
import datetime
import requests
import numpy as np
import json
import os
import time
from flask import Flask
import threading

# === Telegram Setup ===
TELEGRAM_TOKEN = "8537811183:AAF4DWeA5Sks86mBISJvS1iNvLRpkY_FgnA"
CHAT_ID = "8191014589"

# === File to store sent signals ===
SENT_FILE = "sent_signals.json"
if os.path.exists(SENT_FILE):
    with open(SENT_FILE, "r") as f:
        sent_signals = json.load(f)
else:
    sent_signals = {}

def send_telegram_message(message: str):
    """Send message to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print("✅ Telegram Alert Sent!")
        else:
            print(f"⚠️ Telegram Error {response.status_code}: {response.text}")
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

print(f"\n📊 High Accuracy Swing Trading Scanner Started - {datetime.datetime.utcnow():%Y-%m-%d %H:%M UTC}\n")

def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(close):
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal

def check_signals():
    global sent_signals
    summary = []

    for name, ticker in pairs.items():
        try:
            data = yf.download(ticker, period="120d", interval="1d", progress=False)
            if data.empty or len(data) < 30:
                print(f"⚠️ Not enough data for {name}")
                continue

            close = data["Close"]
            high = data["High"]
            low = data["Low"]

            # === Indicators ===
            rsi = calculate_rsi(close)
            ema50 = close.ewm(span=50, adjust=False).mean()
            macd, macd_signal = calculate_macd(close)

            current_price = close.iloc[-1]
            swing_high = high.max()
            drop_pc = ((swing_high - current_price) / swing_high) * 100
            current_rsi = rsi.iloc[-1]
            current_ema50 = ema50.iloc[-1]

            # === MACD confirmation ===
            prev_macd = macd.iloc[-2]
            prev_signal = macd_signal.iloc[-2]
            curr_macd = macd.iloc[-1]
            curr_signal = macd_signal.iloc[-1]

            macd_cross_up = prev_macd < prev_signal and curr_macd > curr_signal

            # === Signal Logic ===
            signal = None
            if (
                drop_pc >= 3
                and current_rsi <= 35
                and current_price > current_ema50
                and macd_cross_up
            ):
                signal = "💎 STRONG BUY (RSI+EMA+MACD Confirmed)"
            elif (
                1.5 <= drop_pc < 3
                and 35 < current_rsi <= 45
                and current_price > current_ema50
                and macd_cross_up
            ):
                signal = "✅ MODERATE BUY (Trend Positive)"

            # === Avoid duplicate alerts ===
            key = f"{name}_{datetime.date.today()}"
            if signal and sent_signals.get(key) != signal:
                msg = (f"*Omstrading Swing Alert 📈*\n\n"
                       f"Pair: {name}\n"
                       f"Signal: *{signal}*\n"
                       f"Price: {current_price:.5f}\n"
                       f"Drop: {drop_pc:.2f}%\n"
                       f"RSI: {current_rsi:.2f}\n"
                       f"EMA(50): {current_ema50:.5f}\n"
                       f"MACD Cross: {'✅ Yes' if macd_cross_up else '❌ No'}\n\n"
                       f"📆 {datetime.date.today()}")
                send_telegram_message(msg)
                sent_signals[key] = signal

            summary.append([
                name,
                round(current_price, 5),
                round(drop_pc, 2),
                round(current_rsi, 2),
                "UP" if macd_cross_up else "DOWN",
                signal or "WAIT ⚠️"
            ])

        except Exception as e:
            print(f"❌ Error fetching {name}: {e}")

    # Save updated signals
    with open(SENT_FILE, "w") as f:
        json.dump(sent_signals, f)

    if summary:
        df = pd.DataFrame(summary, columns=["Pair", "Price", "Drop%", "RSI", "MACD", "Signal"])
        print(df.to_string(index=False))
    else:
        print("⚠️ No valid data received.")

# === Keep Alive Flask Server ===
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Swing Trading Bot is Running!"

def run_keep_alive():
    app.run(host='0.0.0.0', port=10000)

# === Start Keep Alive Thread ===
threading.Thread(target=run_keep_alive).start()

# === Auto Loop (Every 1 Hour) ===
while True:
    check_signals()
    print("\n⏳ Waiting 1 hour before next scan...\n")
    time.sleep(3600)
