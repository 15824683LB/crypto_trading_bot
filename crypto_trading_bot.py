import time
import requests
import pandas as pd
import ccxt
from datetime import datetime
import traceback
from keep_alive import keep_alive
keep_alive()

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = "7615583534:AAHaKfWLN7NP83LdmR32i6BfNWqq73nBsAE"
TELEGRAM_CHAT_ID = "8191014589"
TELEGRAM_GROUP_CHAT_ID = ""

# MEXC API Setup (Binance Alternative)
exchange = ccxt.mexc({
    'enableRateLimit': True,
    'session': requests.Session(),
})


# List of Crypto Pairs to Scan
CRYPTO_PAIRS = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"]

# Timeframes
timeframes = {"Scalping": "5m", "Intraday": "15m", "Swing": "4h"}

# Active Trade Tracker
active_trades = {}
last_signal_time = time.time()

# Function to Send Telegram Message
def send_telegram_message(message, chat_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Telegram Error:", e)

# Fetch OHLCV Data
def fetch_data(symbol, timeframe):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=50)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception:
        print(f"Error fetching data for {symbol} [{timeframe}]:\n{traceback.format_exc()}")
        return None

# Strategy: Liquidity Grab + Order Block
def liquidity_grab_order_block(df):
    df['high_shift'] = df['high'].shift(1)
    df['low_shift'] = df['low'].shift(1)
    liquidity_grab = (df['high'] > df['high_shift']) & (df['low'] < df['low_shift'])
    order_block = (df['close'] > df['open'])

    if liquidity_grab.iloc[-1] and order_block.iloc[-1]:
        entry = round(df['close'].iloc[-1], 3)
        sl = round(df['low'].iloc[-2], 3)
        tp = round(entry + (entry - sl) * 2, 3)
        tsl = round(entry + (entry - sl) * 1.5, 3)
        return "BUY", entry, sl, tp, tsl, "\U0001F7E2"
    elif liquidity_grab.iloc[-1] and not order_block.iloc[-1]:
        entry = round(df['close'].iloc[-1], 3)
        sl = round(df['high'].iloc[-2], 3)
        tp = round(entry - (sl - entry) * 2, 3)
        tsl = round(entry - (sl - entry) * 1.5, 3)
        return "SELL", entry, sl, tp, tsl, "\U0001F534"
    return "NO SIGNAL", None, None, None, None, None

# Function to Check TP or SL Hit
def check_tp_sl():
    global active_trades
    for pair, trade in list(active_trades.items()):
        df = fetch_data(pair, "1m")
        time.sleep(1)
        if df is not None:
            last_price = df['close'].iloc[-1]
            now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            signal_time = trade.get("signal_time", "N/A")

            if trade['direction'] == "BUY":
                if last_price >= trade['tp']:
                    msg = (
                        f"✅ *{pair} TP Hit!*\n📈 Direction: BUY\n🎯 Entry: `{trade['entry']}`\n"
                        f"💰 TP: `{trade['tp']}`\n🕐 Signal Time: `{signal_time}`\n📍 TP Time: `{now_time}`"
                    )
                    send_telegram_message(msg, TELEGRAM_CHAT_ID)
                    send_telegram_message(msg, TELEGRAM_GROUP_CHAT_ID)
                    del active_trades[pair]
                elif last_price <= trade['sl']:
                    msg = (
                        f"❌ *{pair} SL Hit!*\n📈 Direction: BUY\n🎯 Entry: `{trade['entry']}`\n"
                        f"💥 SL: `{trade['sl']}`\n🕐 Signal Time: `{signal_time}`\n📍 SL Time: `{now_time}`"
                    )
                    send_telegram_message(msg, TELEGRAM_CHAT_ID)
                    send_telegram_message(msg, TELEGRAM_GROUP_CHAT_ID)
                    del active_trades[pair]

            elif trade['direction'] == "SELL":
                if last_price <= trade['tp']:
                    msg = (
                        f"✅ *{pair} TP Hit!*\n📉 Direction: SELL\n🎯 Entry: `{trade['entry']}`\n"
                        f"💰 TP: `{trade['tp']}`\n🕐 Signal Time: `{signal_time}`\n📍 TP Time: `{now_time}`"
                    )
                    send_telegram_message(msg, TELEGRAM_CHAT_ID)
                    send_telegram_message(msg, TELEGRAM_GROUP_CHAT_ID)
                    del active_trades[pair]
                elif last_price >= trade['sl']:
                    msg = (
                        f"❌ *{pair} SL Hit!*\n📉 Direction: SELL\n🎯 Entry: `{trade['entry']}`\n"
                        f"💥 SL: `{trade['sl']}`\n🕐 Signal Time: `{signal_time}`\n📍 SL Time: `{now_time}`"
                    )
                    send_telegram_message(msg, TELEGRAM_CHAT_ID)
                    send_telegram_message(msg, TELEGRAM_GROUP_CHAT_ID)
                    del active_trades[pair]

# Main Trading Loop
while True:
    signal_found = False

    for pair in CRYPTO_PAIRS:
        if pair in active_trades:
            continue  # Skip duplicate signal

        for label, tf in timeframes.items():
            df = fetch_data(pair, tf)
            time.sleep(1)
            if df is not None:
                signal, entry, sl, tp, tsl, emoji = liquidity_grab_order_block(df)
                if signal != "NO SIGNAL":
                    signal_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    msg = (
                        f"{emoji} *{signal} Signal for {pair}*\nType: {label}\nTimeframe: {tf}\n"
                        f"Time: `{signal_time}`\nEntry: `{entry}`\nSL: `{sl}`\nTP: `{tp}`\nTSL: `{tsl}`"
                    )
                    send_telegram_message(msg, TELEGRAM_CHAT_ID)
                    send_telegram_message(msg, TELEGRAM_GROUP_CHAT_ID)

                    active_trades[pair] = {
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

    # Check TP/SL
    check_tp_sl()

    # No Signal Alert
    if not signal_found and (time.time() - last_signal_time) > 3600:
        send_telegram_message("⚠️ No Signal in the Last 1 Hour", TELEGRAM_CHAT_ID)
        send_telegram_message("⚠️ No Signal in the Last 1 Hour", TELEGRAM_GROUP_CHAT_ID)
        last_signal_time = time.time()

    # Wait before next round
    time.sleep(60)
print("Bot is running 24/7!")
