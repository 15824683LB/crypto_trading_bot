from keep_alive import keep_alive
from flask import Flask
import ccxt
import pandas as pd
import requests
from ta.trend import MACD

keep_alive()

app = Flask(__name__)

# Telegram Config
BOT_TOKEN = "8100205821:AAE0sGJhnA8ySkuSusEXSf9bYU5OU6sFzVg"
CHAT_ID = "@SwingTreadingSmartBot"

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

# Custom Supertrend implementation
def supertrend(df, period=10, multiplier=3):
    hl2 = (df['high'] + df['low']) / 2
    df['atr'] = df['high'].rolling(period).max() - df['low'].rolling(period).min()
    df['upperband'] = hl2 + (multiplier * df['atr'])
    df['lowerband'] = hl2 - (multiplier * df['atr'])
    df['supertrend'] = df['close']

    for i in range(1, len(df)):
        if df['close'][i] > df['upperband'][i-1]:
            df['supertrend'][i] = df['lowerband'][i]
        elif df['close'][i] < df['lowerband'][i-1]:
            df['supertrend'][i] = df['upperband'][i]
        else:
            df['supertrend'][i] = df['supertrend'][i-1]
    return df

def analyze(symbol):
    df = fetch_data(symbol)
    macd = MACD(df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["vwap"] = (df["volume"] * (df["high"] + df["low"] + df["close"]) / 3).cumsum() / df["volume"].cumsum()
    
    df = supertrend(df)  # Apply supertrend

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
