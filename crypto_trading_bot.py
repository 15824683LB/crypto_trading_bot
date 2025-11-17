import yfinance as yf
import pandas as pd
import time
import requests
from datetime import datetime

# ==========================
# USER SETTINGS
# ==========================

PAIR = "BTC-USD"
TELEGRAM_TOKEN = "8537811183:AAF4DWeA5Sks86mBISJvS1iNvLRpkY_FgnA"
CHAT_ID = "8191014589"

# Intraday allowed trading time (24-hr)
START_TIME = "18:00"
END_TIME = "23:00"

# ==========================
# TELEGRAM ALERT FUNCTION
# ==========================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg}
    try:
        requests.post(url, data=data)
    except:
        print("Telegram Error!")


# ==========================
# SUPER TREND INDICATOR
# ==========================
def supertrend(df, period=10, multiplier=3):
    hl2 = (df['High'] + df['Low']) / 2
    df['atr'] = df['Close'].rolling(period).std() * multiplier

    df['upperband'] = hl2 + df['atr']
    df['lowerband'] = hl2 - df['atr']

    df['supertrend'] = 0
    for i in range(1, len(df)):
        if df['Close'][i] > df['upperband'][i-1]:
            df['supertrend'][i] = df['lowerband'][i]
        elif df['Close'][i] < df['lowerband'][i-1]:
            df['supertrend'][i] = df['upperband'][i]
        else:
            df['supertrend'][i] = df['supertrend'][i-1]
    return df


# ==========================
# FETCH OHLC DATA
# ==========================
def get_data(tf="1h"):
    return yf.download(PAIR, period="5d", interval=tf, progress=False)


# ==========================
# TRADING LOGIC
# ==========================
def check_signal():
    now = datetime.now().strftime("%H:%M")

    # Out-of-time skip
    if not (START_TIME <= now <= END_TIME):
        return "NO_TRADE"

    # -------- 1H TREND --------
    df_1h = get_data("1h")
    df_1h["EMA50"] = df_1h["Close"].ewm(50).mean()

    trend_up = df_1h["Close"].iloc[-1] > df_1h["EMA50"].iloc[-1]
    trend_dn = df_1h["Close"].iloc[-1] < df_1h["EMA50"].iloc[-1]

    # -------- 15M ENTRY --------
    df_15 = get_data("15m")
    df_15 = supertrend(df_15)

    last_close = df_15["Close"].iloc[-1]
    last_st = df_15["supertrend"].iloc[-1]

    # BUY SIGNAL
    if trend_up and last_close > last_st:
        return f"BUY Signal 🔥\nPair: BTCUSD\nPrice: {last_close}"

    # SELL SIGNAL
    if trend_dn and last_close < last_st:
        return f"SELL Signal ⚠️\nPair: BTCUSD\nPrice: {last_close}"

    return "NO_TRADE"


# ==========================
# MAIN LOOP
# ==========================
send_telegram("🚀 BTC Intraday Bot Started (1H Trend + 15M Entry)")

while True:
    signal = check_signal()

    if signal != "NO_TRADE":
        send_telegram(signal)
        print("Alert Sent:", signal)
    else:
        print("No Trade | Waiting...")

    time.sleep(60)   # every 1 minute check
