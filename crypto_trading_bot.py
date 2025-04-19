import time
import ccxt
import requests
import pandas as pd

# Telegram Bot Credentials
TELEGRAM_BOT_TOKEN = "7615583534:AAHaKfWLN7NP83LdmR32i6BfNWqq73nBsAE"
TELEGRAM_CHAT_ID = "8191014589"  # Personal
TELEGRAM_GROUP_CHAT_ID = "@TradeAlertcrypto"  # Group ID (তোমার Group Chat ID বসাও)

# Send Message Function
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=data)
    data["chat_id"] = TELEGRAM_GROUP_CHAT_ID  # Send to Group also
    requests.post(url, data=data)

# Trading Settings
exchange = ccxt.binance()
pairs = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"]
timeframes = {"Intraday": "15m", "Swing": "4h"}  # Only Intraday & Swing

# Fetch Data Function
def fetch_data(pair, timeframe):
    try:
        ohlcv = exchange.fetch_ohlcv(pair, timeframe, limit=20)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return df
    except Exception as e:
        print(f"Data Fetch Error for {pair}: {e}")
        return None

# Liquidity Grab & Order Block Strategy
def liquidity_grab_order_block(df, trade_type):
    df['high_shift'] = df['high'].shift(1)
    df['low_shift'] = df['low'].shift(1)

    liquidity_grab = (df['high'] > df['high_shift']) & (df['low'] < df['low_shift'])
    order_block = (df['close'] > df['open'])  # Simple bullish confirmation

    if liquidity_grab.iloc[-1] and order_block.iloc[-1]:
        entry = round(df['close'].iloc[-1], 3)
        stop_loss = round(df['low'].iloc[-2], 3)
        take_profit = round(entry + (entry - stop_loss) * 2, 3)
        tsl = round(entry + (entry - stop_loss) * 1.5, 3)
        return "BUY", entry, stop_loss, take_profit, tsl, trade_type, "\U0001F7E2"
    elif liquidity_grab.iloc[-1] and not order_block.iloc[-1]:
        entry = round(df['close'].iloc[-1], 3)
        stop_loss = round(df['high'].iloc[-2], 3)
        take_profit = round(entry - (stop_loss - entry) * 2, 3)
        tsl = round(entry - (stop_loss - entry) * 1.5, 3)
        return "SELL", entry, stop_loss, take_profit, tsl, trade_type, "\U0001F534"
    return "NO SIGNAL", None, None, None, None, None, None

# Open Trades Dictionary
open_trades = {}

# Main Trading Loop (Refresh Every 5 Min)
while True:
    signal_found = False
    trade_sent = False  # Flag to ensure we only send one signal per loop

    for pair in pairs:
        if trade_sent:
            break
        for trade_type, tf in timeframes.items():
            df = fetch_data(pair, tf)
            if df is not None:
                signal, entry, sl, tp, tsl, timeframe, color = liquidity_grab_order_block(df, trade_type)
                if signal != "NO SIGNAL":
                    msg = f"{color} *{signal} Signal for {pair}*\nType: {trade_type}\nTimeframe: {tf}\nEntry: `{entry}`\nSL: `{sl}`\nTP: `{tp}`\nTSL: `{tsl}`"
                    send_telegram_message(msg)

                    # Save trade details
                    open_trades[pair] = {"entry": entry, "sl": sl, "tp": tp, "tsl": tsl}
                    signal_found = True
                    trade_sent = True
                    break  # Exit inner loop after signal

    # Only send "No Signal" if no signal was found at all
    if not signal_found:
        send_telegram_message("📌 No New Signals in Last 5 Minutes")

    # Check if SL or TP is hit
    for pair in list(open_trades.keys()):
        try:
            current_price = exchange.fetch_ticker(pair)['last']
            trade = open_trades[pair]
            if current_price >= trade["tp"]:
                send_telegram_message(f"✅ *Target Hit!* 🎯\nPair: {pair}\nEntry: `{trade['entry']}`\nTP: `{trade['tp']}`")
                del open_trades[pair]
            elif current_price <= trade["sl"]:
                send_telegram_message(f"❌ *Stop-Loss Hit!* 🚨\nPair: {pair}\nEntry: `{trade['entry']}`\nSL: `{trade['sl']}`")
                del open_trades[pair]
        except Exception as e:
            print(f"Error fetching price for {pair}: {e}")

    time.sleep(300)  # Refresh Every 5 Minutes
