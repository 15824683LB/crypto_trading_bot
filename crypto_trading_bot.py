import time
import requests
import pandas as pd
import ccxt
from datetime import datetime
import traceback
from keep_alive import keep_alive

# Start the keep-alive server
keep_alive()

# Your trading bot code starts here
print("Crypto bot is running...")

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = "7615583534:AAHaKfWLN7NP83LdmR32i6BfNWqq73nBsAE"
TELEGRAM_CHAT_ID = "8191014589"
TELEGRAM_GROUP_CHAT_ID = "@TradeAlertcrypto"

# MEXC API Setup
exchange = ccxt.mexc({
    'enableRateLimit': True,
    'session': requests.Session(),
})

# Function to Send Telegram Message
def send_telegram_message(message, chat_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Telegram Error:", e)

# Fetch OHLCV Data
def fetch_data(symbol, interval, lookback):
    since = exchange.parse8601(lookback)
    ohlcv = exchange.fetch_ohlcv(symbol, interval, since=since)
    df = pd.DataFrame(ohlcv, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume'
    ])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    df = df.astype(float)
    return df

# Strategy: Liquidity Grab + Order Block
def liquidity_grab_order_block(df):
    df['high_shift'] = df['high'].shift(1)
    df['low_shift'] = df['low'].shift(1)
    liquidity_grab = (df['high'] > df['high_shift']) & (df['low'] < df['low_shift'])
    order_block = df['close'] > df['open']

    if liquidity_grab.iloc[-1] and order_block.iloc[-1]:
        entry = round(df['close'].iloc[-1], 2)
        sl = round(df['low'].iloc[-2], 2)
        tp = round(entry + (entry - sl) * 2, 2)
        tsl = round(entry + (entry - sl) * 1.5, 2)
        return "BUY", entry, sl, tp, tsl, "\U0001F7E2"
    elif liquidity_grab.iloc[-1] and not order_block.iloc[-1]:
        entry = round(df['close'].iloc[-1], 2)
        sl = round(df['high'].iloc[-2], 2)
        tp = round(entry - (sl - entry) * 2, 2)
        tsl = round(entry - (sl - entry) * 1.5, 2)
        return "SELL", entry, sl, tp, tsl, "\U0001F534"
    return "NO SIGNAL", None, None, None, None, None

# Function to Check TP or SL Hit
def check_tp_sl():
    global active_trades
    for pair, trade in list(active_trades.items()):
        df = fetch_data(pair, '1m', '2 days ago UTC')
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
CRYPTO_SYMBOLS = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT"]
timeframes = {
    "Intraday 15m": '15m',
    "Intraday 30m": '30m',
    "Swing": '1h',
    "Position": '1d'
}

active_trades = {}
last_signal_time = time.time()

while True:
    signal_found = False

    for symbol in CRYPTO_SYMBOLS:
        if symbol in active_trades:
            df = fetch_data(symbol, '1m', '2 days ago UTC')
            if df is not None:
                check_tp_sl()
        else:
            df = fetch_data(symbol, '1m', '2 days ago UTC')
            if df is not None:
                signal, entry, sl, tp, tsl, color = liquidity_grab_order_block(df)
                if signal != "NO SIGNAL":
                    active_trades[symbol] = {
                        'direction': signal,
                        'entry': entry,
                        'sl': sl,
                        'tp': tp,
                        'tsl': tsl,
                        'signal_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    msg = (
                        f"⚡️ New {signal} Signal for {symbol}!\n"
                        f"🎯 Entry: `{entry}`\n"
                        f"💥 SL: `{sl}`\n"
                        f"💰 TP: `{tp}`\n"
                        f"🔺 TSL: `{tsl}`\n"
                        f"⏰ Signal Time: `{active_trades[symbol]['signal_time']}`"
                    )
                    send_telegram_message(msg, TELEGRAM_CHAT_ID)
                    send_telegram_message(msg, TELEGRAM_GROUP_CHAT_ID)
                    print(f"{signal} Signal Sent for {symbol} at {entry}")

    time.sleep(60)
