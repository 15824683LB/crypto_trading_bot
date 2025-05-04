import time
import requests
import logging
from datetime import datetime
from binance.client import Client
import pytz
import os
from keep_alive import keep_alive

keep_alive()

# Telegram Config
TELEGRAM_BOT_TOKEN = "8100205821:AAE0sGJhnA8ySkuSusEXSf9bYU5OU6sFzVg"
TELEGRAM_CHAT_ID = "-1002689167916"

# Binance API Config
BINANCE_API_KEY = "your_binance_api_key"
BINANCE_SECRET_KEY = "your_binance_secret_key"
client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)

# Crypto symbols
CRYPTO_PAIRS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT"]
TIMEFRAMES = {"15m": Client.KLINE_INTERVAL_15MINUTE, "30m": Client.KLINE_INTERVAL_30MINUTE}
active_trades = {}
last_signal_time = time.time()
kolkata_tz = pytz.timezone("Asia/Kolkata")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, data=data)
    except Exception as e:
        print(f"Telegram error: {e}")

def fetch_ohlcv(symbol, interval):
    try:
        klines = client.get_klines(symbol=symbol, interval=interval, limit=50)
        data = []
        for k in klines:
            data.append({
                "timestamp": int(k[0]),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5])
            })
        return data
    except Exception as e:
        logging.error(f"Error fetching {symbol} - {e}")
        return None

def calculate_vwap(data):
    cumulative_vwap = 0
    cumulative_volume = 0
    for i in range(len(data)):
        typical_price = (data[i]["high"] + data[i]["low"] + data[i]["close"]) / 3
        cumulative_vwap += typical_price * data[i]["volume"]
        cumulative_volume += data[i]["volume"]
        data[i]["vwap"] = cumulative_vwap / cumulative_volume if cumulative_volume else 0
    return data

def detect_order_block(data, direction):
    if len(data) < 4:
        return False
    if direction == "BUY":
        return data[-1]['low'] > data[-3]['low'] and data[-1]['close'] > data[-1]['open']
    elif direction == "SELL":
        return data[-1]['high'] < data[-3]['high'] and data[-1]['close'] < data[-1]['open']
    return False

def liquidity_grab_with_vwap(data):
    data = calculate_vwap(data)
    if len(data) < 3:
        return "NO SIGNAL", None, None, None, None, None

    curr = data[-1]
    prev = data[-2]

    liquidity_grab = curr['high'] > prev['high'] and curr['low'] < prev['low']
    above_vwap = curr['close'] > curr['vwap'] and curr['open'] > curr['vwap']
    below_vwap = curr['close'] < curr['vwap'] and curr['open'] < curr['vwap']

    if liquidity_grab and above_vwap and detect_order_block(data, "BUY"):
        entry = round(curr['close'], 4)
        sl = round(prev['low'], 4)
        tp = round(entry + (entry - sl) * 2, 4)
        tsl = round(entry + (entry - sl) * 1.5, 4)
        return "BUY", entry, sl, tp, tsl, "\U0001F7E2"
    elif liquidity_grab and below_vwap and detect_order_block(data, "SELL"):
        entry = round(curr['close'], 4)
        sl = round(prev['high'], 4)
        tp = round(entry - (sl - entry) * 2, 4)
        tsl = round(entry - (sl - entry) * 1.5, 4)
        return "SELL", entry, sl, tp, tsl, "\U0001F534"

    return "NO SIGNAL", None, None, None, None, None

while True:
    signal_found = False
    for symbol in CRYPTO_PAIRS:
        if symbol in active_trades:
            price = float(client.get_symbol_ticker(symbol=symbol)['price'])
            trade = active_trades[symbol]
            now_time = datetime.now(kolkata_tz).strftime('%Y-%m-%d %H:%M')

            if trade['direction'] == "BUY" and price >= trade['tp']:
                send_telegram_message(f"✅ *TP HIT for {symbol}*\nTime: `{now_time}`\nPrice: `{price}`\nSignal: BUY")
                del active_trades[symbol]
            elif trade['direction'] == "BUY" and price <= trade['sl']:
                send_telegram_message(f"🛑 *SL HIT for {symbol}*\nTime: `{now_time}`\nPrice: `{price}`\nSignal: BUY")
                del active_trades[symbol]
            elif trade['direction'] == "SELL" and price <= trade['tp']:
                send_telegram_message(f"✅ *TP HIT for {symbol}*\nTime: `{now_time}`\nPrice: `{price}`\nSignal: SELL")
                del active_trades[symbol]
            elif trade['direction'] == "SELL" and price >= trade['sl']:
                send_telegram_message(f"🛑 *SL HIT for {symbol}*\nTime: `{now_time}`\nPrice: `{price}`\nSignal: SELL")
                del active_trades[symbol]
            continue

        for label, tf in TIMEFRAMES.items():
            data = fetch_ohlcv(symbol, tf)
            if data:
                signal, entry, sl, tp, tsl, emoji = liquidity_grab_with_vwap(data)
                if signal != "NO SIGNAL":
                    signal_time = datetime.now(kolkata_tz).strftime('%Y-%m-%d %H:%M:%S')
                    msg = (
                        f"{emoji} *{signal} Signal for {symbol}*\n"
                        f"Type: {label}\nTime: `{signal_time}`\n"
                        f"Entry: `{entry}`\nSL: `{sl}`\nTP: `{tp}`\nTSL: `{tsl}`"
                    )
                    send_telegram_message(msg)
                    active_trades[symbol] = {
                        "signal_time": signal_time,
                        "entry": entry,
                        "sl": sl,
                        "tp": tp,
                        "direction": signal
                    }
                    signal_found = True
                    break
        if signal_found:
            break

    if not signal_found and (time.time() - last_signal_time > 3600):
        send_telegram_message("⚠️ No Signal in the Last 1 Hour (Crypto Market)")
        last_signal_time = time.time()

    time.sleep(60)
    print("Crypto Bot is running 24/7!")
