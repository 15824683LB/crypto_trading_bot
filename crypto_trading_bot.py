
from keep_alive import keep_alive
from flask import Flask
import ccxt
import pandas as pd
import requests
from ta.trend import MACD
from ta.trend import supertrend_indicator
keep_alive()

app = Flask(__name__)

# Telegram Config
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"

def send_alert(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# Coins to scan
SYMBOLS = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT", 
           "ADA/USDT", "DOGE/USDT", "MATIC/USDT", "AVAX/USDT", "LINK/USDT"]

exchange = ccxt.binance()

def fetch_data(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, '5m', limit=150)
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df

def analyze(symbol):
    df = fetch_data(symbol)
    df["macd"] = MACD(df["close"]).macd()
    df["macd_signal"] = MACD(df["close"]).macd_signal()
    df["supertrend"] = supertrend_indicator(df["high"], df["low"], df["close"], 10, 3)
    df["vwap"] = (df["volume"] * (df["high"] + df["low"] + df["close"]) / 3).cumsum() / df["volume"].cumsum()

    latest = df.iloc[-1]
    price = latest["close"]
    name = symbol.replace("/USDT", "")

    if price > latest["vwap"] and latest["macd"] > latest["macd_signal"] and price > latest["supertrend"]:
        tp = round(price * 1.02, 2)
        sl = round(price * 0.99, 2)
        msg = f"Buy Signal - {name}\nEntry: {price}\nTarget: {tp}\nStop-Loss: {sl}"
        send_alert(msg)

    elif price < latest["vwap"] and latest["macd"] < latest["macd_signal"] and price < latest["supertrend"]:
        tp = round(price * 0.98, 2)
        sl = round(price * 1.01, 2)
        msg = f"Sell Signal - {name}\nEntry: {price}\nTarget: {tp}\nStop-Loss: {sl}"
        send_alert(msg)

@app.route('/')
def run_bot():
    for sym in SYMBOLS:
        try:
            analyze(sym)
        except Exception as e:
            print(f"Error on {sym}: {e}")
    return "Crypto alerts checked!"

if __name__ == "__main__":
    app.run()


