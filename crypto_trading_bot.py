# === Forex + Crypto Strategy Bot with Telegram Alert + Render Keep-Alive ===

import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests
from flask import Flask
from threading import Thread

# ========== TELEGRAM CONFIG ==========
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.post(url, data=data)
    except Exception as e:
        print("Telegram Error:", e)

# ========== STRATEGY SETTINGS ==========
crypto_pairs = ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD", "ADA-USD", "DOGE-USD", "AVAX-USD", "DOT-USD", "LTC-USD"]
forex_pairs = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "USDCHF=X", "NZDUSD=X", "EURJPY=X", "GBPJPY=X", "AUDJPY=X"]

# ========== STRATEGY FUNCTION ==========
def get_signal(ticker):
    try:
        # --- Fetch data ---
        daily = yf.download(ticker, period="90d", interval="1d", auto_adjust=True, progress=False)
        hourly = yf.download(ticker, period="7d", interval="1h", auto_adjust=True, progress=False)

        if daily.empty or hourly.empty:
            print(f"⚠️ Data missing for {ticker}")
            return None

        # --- Moving Averages ---
        daily["EMA8"] = daily["Close"].ewm(span=8, adjust=False).mean()
        daily["EMA16"] = daily["Close"].ewm(span=16, adjust=False).mean()

        # --- Trend direction ---
        trend = "UP" if daily["EMA8"].iloc[-1] > daily["EMA16"].iloc[-1] else "DOWN"

        # --- RSI ---
        delta = hourly["Close"].diff()
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = pd.Series(gain).rolling(window=14).mean()
        avg_loss = pd.Series(loss).rolling(window=14).mean()
        rs = avg_gain / avg_loss
        hourly["RSI"] = 100 - (100 / (1 + rs))

        # --- ADX ---
        df = daily.copy()
        df["TR"] = np.maximum(df["High"] - df["Low"], np.maximum(abs(df["High"] - df["Close"].shift()), abs(df["Low"] - df["Close"].shift())))
        df["+DM"] = np.where((df["High"] - df["High"].shift()) > (df["Low"].shift() - df["Low"]), np.maximum(df["High"] - df["High"].shift(), 0), 0)
        df["-DM"] = np.where((df["Low"].shift() - df["Low"]) > (df["High"] - df["High"].shift()), np.maximum(df["Low"].shift() - df["Low"], 0), 0)
        df["+DI"] = 100 * (df["+DM"].ewm(alpha=1/14).mean() / df["TR"].ewm(alpha=1/14).mean())
        df["-DI"] = 100 * (df["-DM"].ewm(alpha=1/14).mean() / df["TR"].ewm(alpha=1/14).mean())
        df["DX"] = (abs(df["+DI"] - df["-DI"]) / abs(df["+DI"] + df["-DI"])) * 100
        adx = df["DX"].ewm(alpha=1/14).mean().iloc[-1]

        # --- Signal logic ---
        rsi = hourly["RSI"].iloc[-1]
        signal = None

        if adx < 20:
            signal = f"{ticker}: Sideways (ADX={adx:.2f})"
        else:
            if trend == "UP" and 30 <= rsi <= 35:
                signal = f"🚀 BUY Signal on {ticker}\nTrend: {trend}\nRSI: {rsi:.2f}\nADX: {adx:.2f}"
            elif trend == "DOWN" and 65 <= rsi <= 75:
                signal = f"⚠️ SELL Signal on {ticker}\nTrend: {trend}\nRSI: {rsi:.2f}\nADX: {adx:.2f}"
            else:
                signal = f"{ticker}: No signal"

        print(signal)
        return signal

    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None


# ========== MAIN LOOP ==========
def main():
    print("🚀 Starting Forex + Crypto Strategy Scanner...")
    while True:
        for ticker in crypto_pairs + forex_pairs:
            signal = get_signal(ticker)
            if signal and ("BUY" in signal or "SELL" in signal):
                send_telegram_message(signal)
            time.sleep(2)
        print("🔁 Cycle complete. Waiting 15 minutes...")
        time.sleep(900)  # 15 min delay between scans


# ========== KEEP-ALIVE SERVER ==========
app = Flask('')

@app.route('/')
def home():
    return "✅ Trading Bot is running 24/7 on Render!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()


# ========== START ==========
if __name__ == "__main__":
    keep_alive()
    main()
