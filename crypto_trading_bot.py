import time
from datetime import datetime, timezone
import requests
import pandas as pd
import yfinance as yf
from flask import Flask
import threading
import numpy as np

# =========================
# TELEGRAM SETTINGS (আপনার সেটিংস অপরিবর্তিত)
# =========================
TELEGRAM_BOT_TOKEN = "8537811183:AAF4DWeA5Sks86mBISJvS1iNvLRpkY_FgnA"
TELEGRAM_CHAT_ID = "8191014589"
SEND_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# কয়েন এবং সেটিংস
COINS = [
    "BNB-USD", "SOL-USD", 
    "XRP-USD", "DOGE-USD",
    "LINK-USD"
]

TF_DIR = "4h"
TF_ENTRY = "1h"

EMA_PERIOD = 200
ATR_PERIOD = 14     # ATR ক্যালকুলেশনের সময়কাল
ATR_MULTIPLIER = 2.0 # SL এর জন্য ATR এর গুণিতক (ভলাটিলিটি বাফার)

RR_TARGETS = [2.0, 3.0, 4.0] # Risk-to-Reward অনুপাত: TP1(2.0), TP2(3.0), TP3(4.0)
MAX_SL_PCT = 3.0    # SL-এর সর্বোচ্চ শতাংশ (ফলব্যাক)
CHECK_INTERVAL_MIN = 10 
HEALTH_CHECK_INTERVAL_MIN = 60 

# ===============================
# Telegram Sender (অপরিবর্তিত)
# ===============================
def send_telegram(msg):
    """টেলিগ্রামের মাধ্যমে বার্তা পাঠায়"""
    try:
        r = requests.post(
            SEND_URL,
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
        )
    except Exception as e:
        print("Telegram exception:", e)

# ===============================
# Fetch OHLCV (অপরিবর্তিত)
# ===============================
def get_data(ticker, interval, period):
    """yfinance থেকে নিরাপদভাবে OHLCV ডেটা সংগ্রহ করে"""
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
        return None

# ===============================
# Indicators (উন্নত)
# ===============================
def add_indicators(df):
    """ডেটাফ্রেমে EMA(200), ATR এবং RSI যোগ করে"""
    df["ema200"] = df["close"].ewm(span=EMA_PERIOD, adjust=False).mean()
    
    # 1. ATR (Average True Range)
    # ATR ক্যালকুলেশনের জন্য 'High', 'Low', 'Close' কলামের নাম ব্যবহার করা হয়েছে
    high_low = df["high"] - df["low"]
    high_close = np.abs(df["high"] - df["close"].shift())
    low_close = np.abs(df["low"] - df["close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.ewm(span=ATR_PERIOD, adjust=False).mean()

    # 2. RSI (Relative Strength Index)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(com=ATR_PERIOD-1, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(com=ATR_PERIOD-1, adjust=False).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    return df

# ===============================
# Strategy Logic (উন্নত)
# ===============================
def detect_signal(df_dir, df_entry):
    """উন্নত ট্রেডিং সিগন্যাল সনাক্ত করে (ATR ও R:R ব্যবহার করে)"""

    df_dir = add_indicators(df_dir)
    df_entry = add_indicators(df_entry)
    
    if len(df_dir) < EMA_PERIOD or len(df_entry) < ATR_PERIOD:
         return None

    # ট্রেন্ড নির্ধারণ: বুলিশ যদি ক্লোজ EMA200 এর উপরে থাকে
    trend = "bull" if df_dir["close"].iloc[-1] > df_dir["ema200"].iloc[-1] else "bear"

    # অর্ডার-ব্লক/সাপ্লাই/ডিমান্ড জোন এর রেঞ্জ (শেষ 4টি 4h ক্যান্ডেলের হাই/লো)
    ob_candles = df_dir.iloc[-5:-1] # শেষ 5টি ক্যান্ডেল থেকে শেষটি বাদে আগের 4টি
    
    # শেষ 4টি ক্যান্ডেলের সর্বোচ্চ হাই এবং সর্বনিম্ন লো
    ob_high = ob_candles["high"].max()
    ob_low  = ob_candles["low"].min()

    cur = df_entry.iloc[-1]
    price = cur.close
    atr_val = cur.atr
    rsi_val = cur.rsi

    # ভলাটিলিটি ভিত্তিক বাফার
    sl_buffer = atr_val * ATR_MULTIPLIER

    entry = None
    side = None
    sl = None

    # --- এন্ট্রি কন্ডিশন ---

    # বুলিশ ট্রেন্ড (Long Entry):
    # 1. ট্রেন্ড বুলিশ হতে হবে।
    # 2. দাম OB/জোন রেঞ্জের মধ্যে থাকতে হবে (সাপোর্টের কাছাকাছি)
    # 3. RSI 50-এর উপরে থাকতে হবে (মোমেন্টাম ফিল্টার)
    if trend == "bull" and ob_low <= price <= ob_high and rsi_val > 50:
        entry = price
        side = "long"
        # SL সেট করা হলো OB লো থেকে ভলাটিলিটি বাফার নিচে
        sl = ob_low - sl_buffer 

    # বিয়ারিশ ট্রেন্ড (Short Entry):
    # 1. ট্রেন্ড বিয়ারিশ হতে হবে।
    # 2. দাম OB/জোন রেঞ্জের মধ্যে থাকতে হবে (রেজিস্ট্যান্সের কাছাকাছি)
    # 3. RSI 50-এর নিচে থাকতে হবে (মোমেন্টাম ফিল্টার)
    if trend == "bear" and ob_low <= price <= ob_high and rsi_val < 50:
        entry = price
        side = "short"
        # SL সেট করা হলো OB হাই থেকে ভলাটিলিটি বাফার উপরে
        sl = ob_high + sl_buffer 

    if entry is None:
        return None

    # SL ফ Tলব্যাক (Fixed Percentage SL)
    sl_pct = abs((entry - sl) / entry * 100)
    if sl_pct > MAX_SL_PCT:
        if side == "long":
            sl = entry * (1 - MAX_SL_PCT/100)
        else:
            sl = entry * (1 + MAX_SL_PCT/100)
            
    # চূড়ান্ত SL থেকে রিস্ক দূরত্ব গণনা করা হলো
    risk_distance = abs(entry - sl)

    # --- TP লেভেল (R:R ভিত্তিতে) ---
    tps = []
    for rr in RR_TARGETS:
        if side == "long":
            # TP = Entry + (Risk Distance * R:R)
            tp_price = entry + (risk_distance * rr)
        else:
            # TP = Entry - (Risk Distance * R:R)
            tp_price = entry - (risk_distance * rr)
            
        tps.append(round(tp_price, 6))

    return {
        "side": side,
        "entry": round(entry,6),
        "sl": round(sl,6),
        "tps": tps,
        "trend": trend,
        "risk_distance": risk_distance
    }

# ===============================
# Format Alert (উন্নত)
# ===============================
def format_alert(ticker, sig):
    """ট্রেডিং সিগন্যালের জন্য টেলিগ্রাম বার্তা তৈরি করে"""
    emoji = "🟢 LONG" if sig["side"]=="long" else "🔴 SHORT"
    
    # রিস্ক/রিওয়ার্ড বিশ্লেষণ
    risk = sig['risk_distance']
    risk_pct = round(risk/sig['entry']*100, 2)
    
    # TP1 এবং TP3 এর R:R ভ্যালু ব্যবহার
    rr1 = RR_TARGETS[0]
    rr3 = RR_TARGETS[2]
    
    msg = f"""
🎯 **HIGH ACCURACY SWING SIGNAL** 🎯
📈 <b>{ticker} — {emoji} Signal</b>

Trend: {sig['trend'].upper()} (4H EMA-200)
Entry: <b>{sig['entry']}</b>
SL: <b>{sig['sl']}</b> 
(Risk: {risk_pct}%)

Targets (TP): (Based on ATR and R:R)
TP1: {sig['tps'][0]} (R:R **{rr1}:1**)
TP2: {sig['tps'][1]} (R:R {RR_TARGETS[1]}:1)
TP3: {sig['tps'][2]} (R:R **{rr3}:1**)

💰 **RISK PER TRADE:** {risk:.6f}
⏰ Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
"""
    return msg

# ===============================
# TRADING MAIN LOOP (অপরিবর্তিত)
# ===============================
def main():
    """আপনার প্রধান ট্রেডিং লজিক লুপ ও স্বাস্থ্য পরীক্ষা"""
    sent = {}
    
    send_telegram("🚀 **Advanced Crypto Swing Bot** Started. (Initial Check)")
    last_health_check_time = time.time() 
    HEALTH_CHECK_SECONDS = HEALTH_CHECK_INTERVAL_MIN * 60

    while True:
        cycle_start = time.time()
        
        logic_error_count = 0
        total_coins_checked = 0

        for coin in COINS:
            total_coins_checked += 1
            try:
                # 1. ডেটা ফেচ
                df_dir = get_data(coin, TF_DIR, "90d")
                df_entry = get_data(coin, TF_ENTRY, "30d")

                if df_dir is None or df_entry is None:
                    # print(f"No data or missing data for: {coin}")
                    logic_error_count += 1
                    continue

                # 2. সিগন্যাল সনাক্তকরণ
                sig = detect_signal(df_dir, df_entry)
                if sig:
                    # সিগন্যাল ট্রিগার হলে, একটি ইউনিক কী তৈরি করুন
                    key = f"{coin}_{sig['side']}_{sig['entry']}"

                    if key not in sent:
                        msg = format_alert(coin, sig)
                        send_telegram(msg)
                        sent[key] = time.time()
                        print("Sent signal:", key)
                        
                    # পুরনো সিগন্যাল পরিষ্কার করা (12 ঘণ্টা পুরনো সিগন্যাল মুছে ফেলা)
                    cutoff = time.time() - (12 * 3600)
                    sent = {k: v for k, v in sent.items() if v > cutoff}


            except Exception as e:
                # লজিক বা অন্য কোনো অপ্রত্যাশিত ত্রুটি ধরুন
                print(f"Error processing {coin}: {e}")
                logic_error_count += 1
                
        # ===============================
        # HOURLY HEALTH CHECK LOGIC
        # ===============================
        if (time.time() - last_health_check_time) >= HEALTH_CHECK_SECONDS:
            
            current_time_utc = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            
            if logic_error_count > 0:
                 health_msg = f"⚠️ <b>Bot Health Warning (1 Hour Cycle)</b>\n"
                 health_msg += f"Time: {current_time_utc}\n"
                 health_msg += f"Status: Logic errors detected.\n"
                 health_msg += f"Details: {logic_error_count} out of {total_coins_checked} coins had data or processing errors in the last cycle."
            else:
                 health_msg = f"🟢 <b>Bot Health Check (1 Hour Cycle)</b>\n"
                 health_msg += f"Time: {current_time_utc}\n"
                 health_msg += f"Status: Logic is working fine."
                 health_msg += f"Details: Successfully checked {total_coins_checked} coins."
            
            send_telegram(health_msg)
            last_health_check_time = time.time()
            print("Sent hourly health check.")


        # পরবর্তী চেকের জন্য অপেক্ষা করুন
        cycle_duration = time.time() - cycle_start
        sleep_time = max(60, CHECK_INTERVAL_MIN*60 - cycle_duration)
        print(f"Cycle completed in {round(cycle_duration, 2)}s. Sleeping {int(sleep_time)} sec.")
        time.sleep(sleep_time)


# ===============================
# KEEP-ALIVE WEB SERVER (Flask) (অপরিবর্তিত)
# ===============================

app = Flask(__name__)

@app.route('/')
def home():
    """সার্ভার জীবিত আছে কিনা তা নিশ্চিত করার জন্য রুট"""
    return f"Bot is running! Last check at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 200

def run_flask_server():
    """একটি পৃথক থ্রেডে Flask সার্ভার শুরু করে"""
    app.run(host='0.0.0.0', port=8080, debug=False)


if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask_server, daemon=True)
    flask_thread.start()

    main()
                    

