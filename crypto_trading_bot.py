import time
import yfinance as yf
import requests
import logging
from datetime import datetime
import ssl
import certifi
import os
from keep_alive import keep_alive
import keep_alive

# SSL fix
os.environ['SSL_CERT_FILE'] = certifi.where()


keep_alive()

# Telegram Config
TELEGRAM_BOT_TOKEN = "8100205821:AAE0sGJhnA8ySkuSusEXSf9bYU5OU6sFzVg"
TELEGRAM_CHAT_ID = "-1002689167916"
# Crypto symbols (Binance format)
CRYPTO_PAIRS = ["BTC-USD", "ETH-USD", "BNB-USD"]

# Logging
logging.basicConfig(filename="crypto_bot.log", level=logging.INFO, format="%(asctime)s - %(message)s")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=data)

def fetch_data(symbol):
    try:
        df = yf.download(tickers=symbol, period="2d", interval="15m")
        df.reset_index(inplace=True)
        df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}, inplace=True)
        df = df[['Datetime', 'open', 'high', 'low', 'close', 'volume']]
        df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        return df
    except Exception as e:
        logging.error(f"Error fetching {symbol} - {e}")
        return None

def liquidity_grab_order_block(df):
    df['high_shift'] = df['high'].shift(1)
    df['low_shift'] = df['low'].shift(1)
    liquidity_grab = (df['high'] > df['high_shift']) & (df['low'] < df['low_shift'])
    order_block = df['close'] > df['open']

    if liquidity_grab.iloc[-1] and order_block.iloc[-1]:
        entry = round(df['close'].iloc[-1], 2)
        sl = round(df['low'].iloc[-2], 2)
        risk = round(entry - sl, 2)
        tp = round(entry + risk, 2)
        return "BUY", entry, sl, tp, "\U0001F7E2"
    elif liquidity_grab.iloc[-1] and not order_block.iloc[-1]:
        entry = round(df['close'].iloc[-1], 2)
        sl = round(df['high'].iloc[-2], 2)
        risk = round(sl - entry, 2)
        tp = round(entry - risk, 2)
        return "SELL", entry, sl, tp, "\U0001F534"
    return "NO SIGNAL", None, None, None, None

# Active trades tracker
active_trades = {}

# Main loop
while True:
    for symbol in CRYPTO_PAIRS:
        df = fetch_data(symbol)
        if df is None or df.empty:
            continue

        signal, entry, sl, tp, emoji = liquidity_grab_order_block(df)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if symbol in active_trades:
            last_price = df['close'].iloc[-1]
            trade = active_trades[symbol]
            if trade['direction'] == "BUY":
                if last_price >= trade['tp']:
                    send_telegram(f"✅ TP HIT on {symbol} at `{last_price}` ({now})")
                    del active_trades[symbol]
                elif last_price <= trade['sl']:
                    send_telegram(f"🛑 SL HIT on {symbol} at `{last_price}` ({now})")
                    del active_trades[symbol]
            elif trade['direction'] == "SELL":
                if last_price <= trade['tp']:
                    send_telegram(f"✅ TP HIT on {symbol} at `{last_price}` ({now})")
                    del active_trades[symbol]
                elif last_price >= trade['sl']:
                    send_telegram(f"🛑 SL HIT on {symbol} at `{last_price}` ({now})")
                    del active_trades[symbol]
            continue

        if signal != "NO SIGNAL":
            msg = (
                f"{emoji} *{signal} Signal - {symbol}*\nTime: `{now}`\n"
                f"Entry: `{entry}`\nSL: `{sl}`\nTP: `{tp}`\nRisk:Reward: `1:1`"
            )
            send_telegram(msg)
            active_trades[symbol] = {"entry": entry, "sl": sl, "tp": tp, "direction": signal}

    time.sleep(60)
