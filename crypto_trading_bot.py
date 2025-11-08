import time
import requests
import pandas as pd
import ta  # pip install ta
import yfinance as yf
from datetime import datetime

# ========== USER CONFIG ==========
TELEGRAM_TOKEN = "8537811183:AAF4DWeA5Sks86mBISJvS1iNvLRpkY_FgnA"
TELEGRAM_CHAT_ID = "8191014589"

CRYPTO_PAIRS = ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD",
                "DOGE-USD", "ADA-USD", "AVAX-USD", "DOT-USD", "MATIC-USD"]
FOREX_PAIRS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X",
               "NZDUSD=X", "USDCHF=X", "EURJPY=X", "GBPJPY=X", "EURAUD=X"]

ADX_THRESHOLD = 20   # Below 20 means sideways → avoid
RSI_BUY_ZONE = (30, 35)
RSI_SELL_ZONE = (65, 75)

# ========== TELEGRAM ALERT ==========
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Telegram Error:", e)

# ========== KEEP ALIVE ==========
def keep_alive():
    while True:
        try:
            requests.get("https://example.com")  # dummy ping to keep alive
            time.sleep(600)  # every 10 min
        except:
            pass

# ========== STRATEGY LOGIC ==========
def check_signals(symbol, is_crypto=True):
    try:
        # --- Daily data for trend ---
        df_daily = yf.download(symbol, period="6mo", interval="1d", progress=False)
        df_daily["MA8"] = df_daily["Close"].rolling(8).mean()
        df_daily["MA16"] = df_daily["Close"].rolling(16).mean()

        # --- Identify trend ---
        trend = "UP" if df_daily["MA8"].iloc[-1] > df_daily["MA16"].iloc[-1] else "DOWN"

        # --- 1-hour data for entry signal ---
        df_h1 = yf.download(symbol, period="1mo", interval="1h", progress=False)
        df_h1["RSI"] = ta.momentum.RSIIndicator(df_h1["Close"], window=14).rsi()
        df_h1["ADX"] = ta.trend.ADXIndicator(df_h1["High"], df_h1["Low"], df_h1["Close"]).adx()

        latest = df_h1.iloc[-1]
        adx = latest["ADX"]
        rsi = latest["RSI"]

        # --- Avoid Sideways Market ---
        if adx < ADX_THRESHOLD:
            return None

        # --- Signal Generation ---
        if trend == "UP" and RSI_BUY_ZONE[0] <= rsi <= RSI_BUY_ZONE[1]:
            return f"✅ STRONG BUY: {symbol}\nTrend: {trend}\nRSI: {rsi:.2f}\nADX: {adx:.2f}"
        elif trend == "DOWN" and RSI_SELL_ZONE[0] <= rsi <= RSI_SELL_ZONE[1]:
            return f"🔻 STRONG SELL: {symbol}\nTrend: {trend}\nRSI: {rsi:.2f}\nADX: {adx:.2f}"
        else:
            return None

    except Exception as e:
        print(f"Error for {symbol}: {e}")
        return None

# ========== MAIN LOOP ==========
def main():
    send_telegram_alert("🤖 Your code is running! Trend Alert Bot started successfully ✅")

    while True:
        print(f"\n⏰ Checking signals... {datetime.now()}")
        for symbol in CRYPTO_PAIRS + FOREX_PAIRS:
            signal = check_signals(symbol)
            if signal:
                send_telegram_alert(signal)
                print(signal)
        time.sleep(3600)  # every 1 hour check

# ========== RUN BOT ==========
if __name__ == "__main__":
    import threading
    threading.Thread(target=keep_alive, daemon=True).start()
    main()
