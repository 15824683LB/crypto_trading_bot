import time
import requests
import logging
from datetime import datetime
import pytz
from keep_alive import keep_alive

keep_alive()

# Telegram Config
TELEGRAM_BOT_TOKEN = "8100205821:AAE0sGJhnA8ySkuSusEXSf9bYU5OU6sFzVg"
TELEGRAM_CHAT_ID = "-1002689167916"

# CoinGecko API Base
COINGECKO_API = "https://api.coingecko.com/api/v3"

# Crypto pairs (CoinGecko uses IDs not symbols)
COIN_IDS = {
    "bitcoin": "BTCUSDT",
    "ethereum": "ETHUSDT",
    "binancecoin": "BNBUSDT",
    "solana": "SOLUSDT",
    "ripple": "XRPUSDT",
    "cardano": "ADAUSDT",
    "dogecoin": "DOGEUSDT",
    "avalanche-2": "AVAXUSDT",
    "polkadot": "DOTUSDT",
    "chainlink": "LINKUSDT"
}

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

def fetch_ohlcv(coin_id):
    try:
        url = f"{COINGECKO_API}/coins/{coin_id}/market_chart?vs_currency=usd&days=1&interval=hourly"
        response = requests.get(url)
        result = response.json()
        prices = result.get("prices", [])
        data = []
        for p in prices:
            timestamp = int(p[0])
            close = float(p[1])
            # Simple OHLCV emulation with close as proxy for open/high/low
            data.append({
                "timestamp": timestamp,
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1000  # fake volume
            })
        return data[-50:]  # last 50
    except Exception as e:
        logging.error(f"Error fetching {coin_id}: {e}")
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

def fetch_current_price(coin_id):
    try:
        url = f"{COINGECKO_API}/simple/price?ids={coin_id}&vs_currencies=usd"
        response = requests.get(url).json()
        return float(response[coin_id]["usd"])
    except Exception as e:
        logging.error(f"Error fetching price for {coin_id}: {e}")
        return None

while True:
    signal_found = False
    for coin_id, symbol in COIN_IDS.items():
        if symbol in active_trades:
            price = fetch_current_price(coin_id)
            if not price:
                continue
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

        data = fetch_ohlcv(coin_id)
        if data:
            signal, entry, sl, tp, tsl, emoji = liquidity_grab_with_vwap(data)
            if signal != "NO SIGNAL":
                signal_time = datetime.now(kolkata_tz).strftime('%Y-%m-%d %H:%M:%S')
                msg = (
                    f"{emoji} *{signal} Signal for {symbol}*\n"
                    f"Time: `{signal_time}`\n"
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

    if not signal_found and (time.time() - last_signal_time > 3600):
        send_telegram_message("⚠️ No Signal in the Last 1 Hour (Crypto Market)")
        last_signal_time = time.time()

    time.sleep(60)
    print("Crypto Bot is running 24/7!")
