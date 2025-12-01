import time
from datetime import datetime, timezone
import requests
import pandas as pd
import yfinance as yf
# Flask ইমপোর্ট করুন
from flask import Flask
import threading

# =========================
# DIRECT TELEGRAM SETTINGS
# =========================
TELEGRAM_BOT_TOKEN = "8537811183:AAF4DWeA5Sks86mBISJvS1iNvLRpkY_FgnA"
TELEGRAM_CHAT_ID = "8191014589"

SEND_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# Coins (yfinance supports these tickers safely)
# কয়েন এবং সেটিংস
# --- এখন মোট 20টি কয়েন চেক করা হবে ---
COINS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD",
    "XRP-USD", "DOGE-USD", "AVAX-USD", "LINK-USD",
    # টপ 20 তালিকা থেকে নতুন কয়েন যোগ করা হলো (লিকুইডিটি অনুযায়ী)
    "USDC-USD", "ADA-USD", "DOT-USD", "TRX-USD", 
    "MATIC-USD", "SHIB-USD", "WLD-USD", "NEAR-USD", 
    "ATOM-USD", "LTC-USD", "ETC-USD", "XLM-USD",
]
TF_DIR = "4h"
TF_ENTRY = "1h"

EMA_PERIOD = 200
TP_PERCENT = [2, 5, 10]      # TP1, TP2, TP3
MAX_SL = 3.0                 # Max SL fallback
CHECK_INTERVAL_MIN = 10      # cycle time


# ===============================
# Telegram Sender
# ===============================
def send_telegram(msg):
    try:
        r = requests.post(
            SEND_URL,
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
        )
        if r.status_code != 200:
            print("Telegram error:", r.text)
    except Exception as e:
        print("Telegram exception:", e)


# ===============================
# Fetch OHLCV (safe version)
# ===============================
def get_data(ticker, interval, period):
    try:
        df = yf.download(ticker, interval=interval, period=period, auto_adjust=False, progress=False)
        if df is None or df.empty:
            return None
        df = df[['Open','High','Low','Close','Volume']]
        df.columns = ['open','high','low','close','volume']
        df = df.dropna()
        df.index = pd.to_datetime(df.index, utc=True)
        return df
    except Exception as e:
        print("Data fetch error:", ticker, e)
        return None


# ===============================
# Indicators
# ===============================
def add_ema(df):
    df["ema200"] = df["close"].ewm(span=EMA_PERIOD, adjust=False).mean()
    return df


# ===============================
# Strategy Logic (Simple but stable)
# ===============================
def detect_signal(df_dir, df_entry):

    df_dir = add_ema(df_dir)
    trend = "bull" if df_dir["close"].iloc[-1] > df_dir["ema200"].iloc[-1] else "bear"

    # Order-block approximation
    last_10 = df_dir.tail(20)
    ob_candle = last_10.iloc[-4]
    ob_high = max(ob_candle.open, ob_candle.high, ob_candle.close)
    ob_low  = min(ob_candle.open, ob_candle.low, ob_candle.close)

    cur = df_entry.iloc[-1]
    price = cur.close

    # Entry condition
    entry = None
    side = None
    sl = None

    if trend == "bull" and ob_low <= price <= ob_high:
        entry = price
        side = "long"
        sl = ob_low * 0.995

    if trend == "bear" and ob_low <= price <= ob_high:
        entry = price
        side = "short"
        sl = ob_high * 1.005

    if entry is None:
        return None

    # SL fallback
    sl_pct = abs((entry - sl) / entry * 100)
    if sl_pct > MAX_SL:
        if side == "long":
            sl = entry * (1 - MAX_SL/100)
        else:
            sl = entry * (1 + MAX_SL/100)

    # TPs
    tps = []
    for p in TP_PERCENT:
        if side == "long":
            tps.append(round(entry * (1 + p/100), 6))
        else:
            tps.append(round(entry * (1 - p/100), 6))

    return {
        "side": side,
        "entry": round(entry,6),
        "sl": round(sl,6),
        "tps": tps,
        "trend": trend
    }


# ===============================
# Format Alert
# ===============================
def format_alert(ticker, sig):
    emoji = "🔵 LONG" if sig["side"]=="long" else "🔴 SHORT"
    msg = f"""
<b>{ticker} — {emoji}</b>

Trend: {sig['trend']}
Entry: <b>{sig['entry']}</b>
SL: <b>{sig['sl']}</b>

TP1: {sig['tps'][0]}
TP2: {sig['tps'][1]}
TP3: {sig['tps'][2]}

⏳ Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

<i>Auto swing signal — backtest before use.</i>
"""
    return msg


# ===============================
# TRADING MAIN LOOP
# ===============================
def main():
    """আপনার প্রধান ট্রেডিং লজিক লুপ"""
    sent = {}

    send_telegram("🚀 Swing Crypto Bot Started.")

    while True:
        cycle_start = time.time()

        for coin in COINS:
            try:
                df_dir = get_data(coin, TF_DIR, "90d")
                df_entry = get_data(coin, TF_ENTRY, "30d")

                if df_dir is None or df_entry is None:
                    print("No data:", coin)
                    continue

                sig = detect_signal(df_dir, df_entry)
                if sig:
                    key = f"{coin}_{sig['side']}_{sig['entry']}"

                    if key not in sent:
                        msg = format_alert(coin, sig)
                        send_telegram(msg)
                        sent[key] = time.time()
                        print("Sent:", key)

            except Exception as e:
                print("Error processing", coin, e)

        sleep_time = max(60, CHECK_INTERVAL_MIN*60 - (time.time() - cycle_start))
        print("Sleeping", int(sleep_time), "sec")
        time.sleep(sleep_time)


# ===============================
# KEEP-ALIVE WEB SERVER (Flask)
# ===============================

# Flask অ্যাপ তৈরি করুন
app = Flask(__name__)

# রুট (route) তৈরি করুন যা UptimeRobot বা হোস্টিং প্ল্যাটফর্ম চেক করবে
@app.route('/')
def home():
    return "Bot is running!", 200

# থ্রেড ব্যবহার করে Flask সার্ভারটি চালু করার ফাংশন
def run_flask_server():
    # Render বা Replit-এ চালানোর জন্য '0.0.0.0' ব্যবহার করা নিরাপদ
    app.run(host='0.0.0.0', port=8080, debug=False)


if __name__ == "__main__":
    # Flask সার্ভারটি একটি নতুন থ্রেডে চালু করুন
    flask_thread = threading.Thread(target=run_flask_server)
    flask_thread.start()

    # প্রধান ট্রেডিং লুপটি চালু করুন
    main()
        

