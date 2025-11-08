import pandas as pd
import numpy as np
import yfinance as yf
import time
import requests

# ============= USER SETTINGS =============
TELEGRAM_TOKEN = "8537811183:AAF4DWeA5Sks86mBISJvS1iNvLRpkY_FgnA"
CHAT_ID = "8191014589"

CRYPTO_PAIRS = ["BTC-USD","ETH-USD","BNB-USD","SOL-USD","XRP-USD","ADA-USD","DOGE-USD","AVAX-USD","DOT-USD","LTC-USD"]
FOREX_PAIRS  = ["EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X","USDCAD=X","USDCHF=X","NZDUSD=X","EURJPY=X","GBPJPY=X","AUDJPY=X"]

# =========================================

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        params = {"chat_id": CHAT_ID, "text": msg}
        requests.get(url, params=params)
    except:
        print("⚠️ Telegram Error")

def get_data(ticker, period="90d", interval="1h"):
    try:
        df = yf.download(ticker, period=period, interval=interval)
        df = df[["Close","High","Low"]].dropna()
        df["Close"] = df["Close"].astype(float)
        return df
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

# --- Indicators ---
def EMA(series, period):
    return series.ewm(span=period, adjust=False).mean()

def RSI(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta>0,0)).rolling(period).mean()
    loss = (-delta.where(delta<0,0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1+rs))

def ADX(df, n=14):
    df["TR"] = np.maximum((df["High"] - df["Low"]),
                   np.maximum(abs(df["High"] - df["Close"].shift(1)),
                              abs(df["Low"] - df["Close"].shift(1))))
    df["+DM"] = np.where((df["High"] - df["High"].shift(1)) > (df["Low"].shift(1) - df["Low"]),
                          df["High"] - df["High"].shift(1), 0)
    df["-DM"] = np.where((df["Low"].shift(1) - df["Low"]) > (df["High"] - df["High"].shift(1)),
                          df["Low"].shift(1) - df["Low"], 0)
    df["+DI"] = 100 * (df["+DM"].ewm(alpha=1/n).mean() / df["TR"].ewm(alpha=1/n).mean())
    df["-DI"] = 100 * (df["-DM"].ewm(alpha=1/n).mean() / df["TR"].ewm(alpha=1/n).mean())
    df["ADX"] = 100 * abs((df["+DI"] - df["-DI"]) / (df["+DI"] + df["-DI"])).ewm(alpha=1/n).mean()
    return df["ADX"]

print("🚀 Starting Forex + Crypto Strategy Scanner...")

while True:
    for ticker in CRYPTO_PAIRS + FOREX_PAIRS:
        df_daily = get_data(ticker, period="200d", interval="1d")
        df_hourly = get_data(ticker, period="90d", interval="1h")

        if df_daily is None or df_hourly is None:
            continue

        # Flatten any 2D arrays
        df_daily["Close"] = df_daily["Close"].squeeze()
        df_hourly["Close"] = df_hourly["Close"].squeeze()

        # --- Daily Trend ---
        df_daily["EMA8"] = EMA(df_daily["Close"], 8)
        df_daily["EMA16"] = EMA(df_daily["Close"], 16)
        trend = "UP" if df_daily["EMA8"].iloc[-1] > df_daily["EMA16"].iloc[-1] else "DOWN"

        # --- Hourly Indicators ---
        df_hourly["RSI"] = RSI(df_hourly["Close"], 14)
        df_hourly["ADX"] = ADX(df_hourly)

        adx_latest = df_hourly["ADX"].iloc[-1]
        rsi_latest = df_hourly["RSI"].iloc[-1]

        # --- Avoid Sideways Market ---
        if adx_latest < 20:
            print(f"{ticker}: Sideways (ADX={adx_latest:.2f})")
            continue

        # --- Generate Signals ---
        if trend == "UP" and rsi_latest <= 35:
            msg = f"💹 BUY Signal ({ticker})\nTrend: {trend}\nRSI: {rsi_latest:.2f}\nADX: {adx_latest:.2f}"
            print(msg)
            send_telegram(msg)

        elif trend == "DOWN" and rsi_latest >= 65:
            msg = f"🔻 SELL Signal ({ticker})\nTrend: {trend}\nRSI: {rsi_latest:.2f}\nADX: {adx_latest:.2f}"
            print(msg)
            send_telegram(msg)

        else:
            print(f"{ticker}: No signal")

    print("⏳ Waiting 30 minutes before next scan...")
    time.sleep(1800)
