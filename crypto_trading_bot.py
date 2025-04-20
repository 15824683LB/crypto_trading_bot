import time
import ccxt
import requests
import pandas as pd

# Telegram Bot Setup
TELEGRAM_BOT_TOKEN = "7615583534:AAHaKfWLN7NP83LdmR32i6BfNWqq73nBsAE"
TELEGRAM_CHAT_ID = "8191014589"
TELEGRAM_GROUP_CHAT_ID = "@@TradeAlertcrypto"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=data)
    data["chat_id"] = TELEGRAM_GROUP_CHAT_ID
    requests.post(url, data=data)

# Bybit Exchange Setup
exchange = ccxt.mexc() 
pairs = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
timeframes = {"Scalp": "15m", "Intraday": "1h", "Swing": "4h"}

def fetch_data(pair, timeframe):
    try:
        bars = exchange.fetch_ohlcv(pair, timeframe, limit=20)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return df
    except Exception as e:
        print(f"{pair} ({timeframe}) data error:", e)
        return None

def liquidity_grab_order_block(df):
    df['high_prev'] = df['high'].shift(1)
    df['low_prev'] = df['low'].shift(1)
    liquidity_grab = (df['high'] > df['high_prev']) & (df['low'] < df['low_prev'])
    order_block_bull = (df['close'] > df['open']) & (df['close'] > df['close'].shift(1))
    order_block_bear = (df['close'] < df['open']) & (df['close'] < df['close'].shift(1))

    if liquidity_grab.iloc[-1] and order_block_bull.iloc[-1]:
        entry = df['close'].iloc[-1]
        sl = df['low'].iloc[-2]
        tp = entry + 2 * (entry - sl)
        tsl = entry + 1.5 * (entry - sl)
        return "BUY", entry, sl, tp, tsl, "🟢"
    elif liquidity_grab.iloc[-1] and order_block_bear.iloc[-1]:
        entry = df['close'].iloc[-1]
        sl = df['high'].iloc[-2]
        tp = entry - 2 * (sl - entry)
        tsl = entry - 1.5 * (sl - entry)
        return "SELL", entry, sl, tp, tsl, "🔴"
    else:
        return "NO SIGNAL", None, None, None, None, None

# Track Open Trades
open_trades = {}

# Main Loop
while True:
    signal_found = False
    for pair in pairs:
        for name, tf in timeframes.items():
            df = fetch_data(pair, tf)
            if df is not None:
                signal, entry, sl, tp, tsl, color = liquidity_grab_order_block(df)
                if signal != "NO SIGNAL":
                    msg = (
                        f"{color} *{signal} Signal*\n"
                        f"Pair: `{pair}`\nType: {name}\nTimeframe: {tf}\n"
                        f"Entry: `{round(entry, 3)}`\nSL: `{round(sl, 3)}`\n"
                        f"TP: `{round(tp, 3)}`\nTSL: `{round(tsl, 3)}`"
                    )
                    send_telegram_message(msg)
                    open_trades[pair] = {"entry": entry, "sl": sl, "tp": tp}
                    signal_found = True
                    break
        if signal_found:
            break

    # SL/TP Check
    for pair in list(open_trades.keys()):
        try:
            price = exchange.fetch_ticker(pair)['last']
            trade = open_trades[pair]
            if price >= trade["tp"]:
                send_telegram_message(f"✅ *TP Hit*\nPair: {pair}\nTP: `{round(trade['tp'],3)}`")
                del open_trades[pair]
            elif price <= trade["sl"]:
                send_telegram_message(f"❌ *SL Hit*\nPair: {pair}\nSL: `{round(trade['sl'],3)}`")
                del open_trades[pair]
        except Exception as e:
            print(f"Price fetch error: {pair} - {e}")

    if not signal_found:
        send_telegram_message("📌 No New Signals in Last 5 Minutes")

    time.sleep(300)  # 5 Min Delay
