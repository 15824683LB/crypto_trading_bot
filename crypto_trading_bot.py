import yfinance as yf
import pandas as pd
import ta
import time
import requests
from flask import Flask
import threading

# ===================================================
# 🔹 Telegram Setup (Replace with your real values)
# ===================================================
TELEGRAM_TOKEN = "8537811183:AAF4DWeA5Sks86mBISJvS1iNvLRpkY_FgnA"  # <-- এখানে তোমার Telegram Bot Token দাও
CHAT_ID = "8191014589"                    # <-- এখানে তোমার Telegram Chat ID দাও

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Telegram Error:", e)

# ===================================================
# 🔹 Keep Alive Server (Render Port Alive)
# ===================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Crypto Bot is Running Successfully!"

def run_server():
    app.run(host="0.0.0.0", port=10000)

threading.Thread(target=run_server).start()

# ===================================================
# 🔹 Trading Logic: 16 EMA, 8 EMA, RSI, ADX
# ===================================================

crypto_pairs = ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD", "ADA-USD", "DOGE-USD", "AVAX-USD", "MATIC-USD", "DOT-USD"]
forex_pairs = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "USDCHF=X", "NZDUSD=X", "EURJPY=X", "GBPJPY=X", "EURGBP=X"]

def analyze_symbol(symbol):
    try:
        # Daily data for trend direction
        df_daily = yf.download(symbol, period="6mo", interval="1d", progress=False)
        df_daily["EMA8"] = ta.trend.ema_indicator(df_daily["Close"], window=8)
        df_daily["EMA16"] = ta.trend.ema_indicator(df_daily["Close"], window=16)

        trend = "UP" if df_daily["EMA8"].iloc[-1] > df_daily["EMA16"].iloc[-1] else "DOWN"

        # Hourly data for entry signal
        df_h1 = yf.download(symbol, period="1mo", interval="1h", progress=False)
        df_h1["RSI"] = ta.momentum.rsi(df_h1["Close"], window=14)
        df_h1["ADX"] = ta.trend.adx(df_h1["High"], df_h1["Low"], df_h1["Close"], window=14)

        latest_rsi = df_h1["RSI"].iloc[-1]
        latest_adx = df_h1["ADX"].iloc[-1]

        # Avoid sideways if ADX < 20
        if latest_adx < 20:
            return None

        if trend == "UP" and 30 <= latest_rsi <= 35:
            return f"🟢 Strong BUY Signal: {symbol}\nTrend: {trend}\nRSI: {latest_rsi:.2f}\nADX: {latest_adx:.2f}"
        elif trend == "DOWN" and 65 <= latest_rsi <= 75:
            return f"🔴 Strong SELL Signal: {symbol}\nTrend: {trend}\nRSI: {latest_rsi:.2f}\nADX: {latest_adx:.2f}"
        else:
            return None
    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        return None

# ===================================================
# 🔹 Main Bot Loop
# ===================================================
send_telegram_message("🚀 Your Crypto-Forex Bot is now RUNNING successfully!")

while True:
    try:
        all_pairs = crypto_pairs + forex_pairs
        for symbol in all_pairs:
            signal = analyze_symbol(symbol)
            if signal:
                send_telegram_message(signal)
                print("Signal Sent:", signal)
            time.sleep(2)

        print("Cycle complete ✅ Waiting 30 minutes...")
        time.sleep(1800)

    except Exception as e:
        send_telegram_message(f"⚠️ Bot Error: {e}")
        print("Error:", e)
        time.sleep(60)
