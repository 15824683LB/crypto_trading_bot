import time
import requests
import pandas as pd
import ccxt
from datetime import datetime, timedelta
import pytz
import traceback
from keep_alive import keep_alive

# Start the keep-alive server
keep_alive()

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

# Kolkata Time
def get_kolkata_time():
    return datetime.now(pytz.timezone("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S')

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

# Strategy
def liquidity_grab_order_block(df):
    df['high_shift'] = df['high'].shift(1)
    df['low_shift'] = df['low'].shift(1)
    df['close_shift'] = df['close'].shift(1)
    df['open_shift'] = df['open'].shift(1)

    liquidity_grab = (df['high'] > df['high_shift']) & (df['low'] < df['low_shift'])
    order_block = df['close'] > df['open']

    # Confirm candle direction logic
    bullish_confirm = (df['close'].iloc[-1] > df['open'].iloc[-1]) and (df['close'].iloc[-1] > df['close'].iloc[-2])
    bearish_confirm = (df['close'].iloc[-1] < df['open'].iloc[-1]) and (df['close'].iloc[-1] < df['close'].iloc[-2])

    # Check for volatility - filter high wick candles
    candle_body = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
    candle_range = df['high'].iloc[-1] - df['low'].iloc[-1]

    # Prevent divide by zero or NaN
    if candle_range == 0 or pd.isna(candle_range) or pd.isna(candle_body):
        return "NO SIGNAL", None, None, None, None, None

    if candle_body / candle_range < 0.3:
        return "NO SIGNAL", None, None, None, None, None

    
    # BUY Condition
if liquidity_grab.iloc[-1] and order_block.iloc[-1] and bullish_confirm:
    entry = round(df['close'].iloc[-1], 4)
    sl = round(min(df['low'].iloc[-2], df['low'].iloc[-3]) * 0.998, 4)
    tp = round(entry + (entry - sl) * 2, 4)
    tsl = round(entry + (entry - sl) * 1.5, 4)
    return "BUY", entry, sl, tp, tsl, "🟢"

# SELL Condition
elif liquidity_grab.iloc[-1] and not order_block.iloc[-1] and bearish_confirm:
    entry = round(df['close'].iloc[-1], 4)
    sl = round(max(df['high'].iloc[-2], df['high'].iloc[-3]) * 1.002, 4)
    tp = round(entry - (sl - entry) * 2, 4)
    tsl = round(entry - (sl - entry) * 1.5, 4)
    return "SELL", entry, sl, tp, tsl, "🔴"
    return "NO SIGNAL", None, None, None, None, None

# Check TP/SL
def check_tp_sl():
    global active_trades
    for pair, trade in list(active_trades.items()):
        df = fetch_data(pair, '1m', '2 days ago UTC')
        if df is not None:
            last_price = df['close'].iloc[-1]
            now_time = get_kolkata_time()
            signal_time = trade.get("signal_time", "N/A")
            tf = trade.get("timeframe", "1m")

            if trade['direction'] == "BUY":
                if last_price >= trade['tp']:
                    msg = (
                        f"✅ *TP Hit - {pair}*\n\n📈 Direction: *BUY*\n🕓 Timeframe: `{tf}`\n🎯 Entry: `{trade['entry']}`\n"
                        f"💰 TP: `{trade['tp']}`\n📍 SL: `{trade['sl']}`\n📌 Strategy: *Liquidity Grab + Order Block*\n\n"
                        f"🕐 Signal Time: `{signal_time}`\n🕒 TP Time: `{now_time}`"
                    )
                    send_telegram_message(msg, TELEGRAM_CHAT_ID)
                    send_telegram_message(msg, TELEGRAM_GROUP_CHAT_ID)
                    del active_trades[pair]
                elif last_price <= trade['sl']:
                    msg = (
                        f"❌ *SL Hit - {pair}*\n\n📈 Direction: *BUY*\n🕓 Timeframe: `{tf}`\n🎯 Entry: `{trade['entry']}`\n"
                        f"💥 SL: `{trade['sl']}`\n📌 Strategy: *Liquidity Grab + Order Block*\n\n"
                        f"🕐 Signal Time: `{signal_time}`\n🕒 SL Time: `{now_time}`"
                    )
                    send_telegram_message(msg, TELEGRAM_CHAT_ID)
                    send_telegram_message(msg, TELEGRAM_GROUP_CHAT_ID)
                    del active_trades[pair]

            elif trade['direction'] == "SELL":
                if last_price <= trade['tp']:
                    msg = (
                        f"✅ *TP Hit - {pair}*\n\n📉 Direction: *SELL*\n🕓 Timeframe: `{tf}`\n🎯 Entry: `{trade['entry']}`\n"
                        f"💰 TP: `{trade['tp']}`\n📍 SL: `{trade['sl']}`\n📌 Strategy: *Liquidity Grab + Order Block*\n\n"
                        f"🕐 Signal Time: `{signal_time}`\n🕒 TP Time: `{now_time}`"
                    )
                    send_telegram_message(msg, TELEGRAM_CHAT_ID)
                    send_telegram_message(msg, TELEGRAM_GROUP_CHAT_ID)
                    del active_trades[pair]
                elif last_price >= trade['sl']:
                    msg = (
                        f"❌ *SL Hit - {pair}*\n\n📉 Direction: *SELL*\n🕓 Timeframe: `{tf}`\n🎯 Entry: `{trade['entry']}`\n"
                        f"💥 SL: `{trade['sl']}`\n📌 Strategy: *Liquidity Grab + Order Block*\n\n"
                        f"🕐 Signal Time: `{signal_time}`\n🕒 SL Time: `{now_time}`"
                    )
                    send_telegram_message(msg, TELEGRAM_CHAT_ID)
                    send_telegram_message(msg, TELEGRAM_GROUP_CHAT_ID)
                    del active_trades[pair]

# Main Loop
TIMEFRAMES = ['15m', '30m', '4h']
CRYPTO_SYMBOLS = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT"]
active_trades = {}

def get_lookback_for_tf(tf):
    if tf == '15m':
        return '3 days ago UTC'
    elif tf == '30m':
        return '5 days ago UTC'
    elif tf == '4h':
        return '30 days ago UTC'
    return '2 days ago UTC'  # Default fallback

while True:
    try:
        for symbol in CRYPTO_SYMBOLS:
            for tf in TIMEFRAMES:
                trade_key = f"{symbol}_{tf}"
                lookback = get_lookback_for_tf(tf)
                df = fetch_data(symbol, tf, lookback)

                if df is not None:
                    if trade_key in active_trades:
                        check_tp_sl()
                    else:
                        signal, entry, sl, tp, tsl, color = liquidity_grab_order_block(df)
                        if signal != "NO SIGNAL":
                            active_trades[trade_key] = {
                                'direction': signal,
                                'entry': entry,
                                'sl': sl,
                                'tp': tp,
                                'tsl': tsl,
                                'signal_time': get_kolkata_time(),
                                'timeframe': tf
                            }
                            msg = (
                                f"{color} *New {signal} Signal - {symbol}*\n\n"
                                f"🕓 Timeframe: `{tf}`\n📌 Strategy: *Liquidity Grab + Order Block*\n"
                                f"🎯 Entry: `{entry}`\n💥 SL: `{sl}`\n💰 TP: `{tp}`\n🔺 TSL: `{tsl}`\n"
                                f"🕐 Signal Time: `{active_trades[trade_key]['signal_time']}`"
                            )
                            send_telegram_message(msg, TELEGRAM_CHAT_ID)
                            send_telegram_message(msg, TELEGRAM_GROUP_CHAT_ID)
                            print(f"{signal} Signal Sent for {symbol} ({tf}) at {entry}")

        time.sleep(60)

    except Exception as e:
        print("Error:", e)
        traceback.print_exc()
        time.sleep(60)
