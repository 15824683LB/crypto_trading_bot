import time
from datetime import datetime
import ccxt
import requests
import pandas as pd
import os
import ssl
import certifi
from keep_alive import keep_alive

keep_alive()
os.environ['SSL_CERT_FILE'] = certifi.where()

# Telegram Setup
TELEGRAM_BOT_TOKEN = "7735010030:AAGem8pNxsLsCMxnbdtQllWCh2Ha7A_pBao"
TELEGRAM_CHAT_ID = "8191014589"
TELEGRAM_GROUP_CHAT_ID = "@tradealertcrypto"  # Channel username with @

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=data)

    # Send to Channel
    data["chat_id"] = TELEGRAM_GROUP_CHAT_ID
    requests.post(url, data=data)

# Exchange Setup
exchange = ccxt.mexc()  # or ccxt.bybit()
pairs = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
timeframes = {"Scalp": "15m", "Intraday": "1h", "Swing": "4h"}

def fetch_data(pair, timeframe):
    try:
        bars = exchange.fetch_ohlcv(pair, timeframe, limit=100)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return df
    except Exception as e:
        print(f"{pair} ({timeframe}) data error:", e)
        return None

# Strategy
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

active_trades = {}
last_signal_time = time.time()

while True:
    signal_found = False

    for stock in pairs:
        if stock in active_trades:
            df = fetch_data(stock, "15m")
            if df is not None and not df.empty:
                last_price = df['close'].iloc[-1]
                trade = active_trades[stock]
                now_time = datetime.now().strftime('%Y-%m-%d %H:%M')

                if trade['direction'] == "BUY":
                    if last_price >= trade['tp']:
                        send_telegram_message(f"✅ *TP HIT for {stock}*\nTime: `{now_time}`\nPrice: `{last_price}`")
                        del active_trades[stock]
                    elif last_price <= trade['sl']:
                        send_telegram_message(f"🛑 *SL HIT for {stock}*\nTime: `{now_time}`\nPrice: `{last_price}`")
                        del active_trades[stock]
                elif trade['direction'] == "SELL":
                    if last_price <= trade['tp']:
                        send_telegram_message(f"✅ *TP HIT for {stock}*\nTime: `{now_time}`\nPrice: `{last_price}`")
                        del active_trades[stock]
                    elif last_price >= trade['sl']:
                        send_telegram_message(f"🛑 *SL HIT for {stock}*\nTime: `{now_time}`\nPrice: `{last_price}`")
                        del active_trades[stock]
            continue

        for label, tf in timeframes.items():
            df = fetch_data(stock, tf)
            if df is not None and not df.empty:
                signal, entry, sl, tp, tsl, emoji = liquidity_grab_order_block(df)
                if signal != "NO SIGNAL":
                    signal_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    msg = (
                        f"{emoji} *{signal} Signal for {stock}*\n"
                        f"Type: {label}\nTimeframe: {tf}\nTime: `{signal_time}`\n"
                        f"Entry: `{entry}`\nSL: `{sl}`\nTP: `{tp}`\nTSL: `{tsl}`"
                    )
                    send_telegram_message(msg)
                    active_trades[stock] = {
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
        send_telegram_message("⚠️ No Signal in the Last 1 Hour (Crypto Pairs)")
        last_signal_time = time.time()

    time.sleep(60)
    print("Bot is running 24/7!")
