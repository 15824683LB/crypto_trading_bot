import time
from datetime import datetime, timezone
import requests
import pandas as pd
import yfinance as yf
from flask import Flask
import threading

# =========================
# TELEGRAM SETTINGS
# =========================
TELEGRAM_BOT_TOKEN = "8537811183:AAF4DWeA5Sks86mBISJvS1iNvLRpkY_FgnA"
TELEGRAM_CHAT_ID = "8191014589"

SEND_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# কয়েন এবং সেটিংস
COINS = [
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", 
    "XRP-USD", "ADA-USD", "DOGE-USD", "AVAX-USD", 
    "DOT-USD", "LINK-USD"
]

TF_DIR = "4h"
TF_ENTRY = "1h"

EMA_PERIOD = 200
TP_PERCENT = [2, 5, 10]      # TP1, TP2, TP3
MAX_SL = 3.0                 # Max SL fallback
CHECK_INTERVAL_MIN = 10      # প্রতি লুপ সাইকেলের সময় (মিনিটে)
HEALTH_CHECK_INTERVAL_MIN = 60 # স্ট্যাটাস মেসেজ পাঠানোর সময় (মিনিটে)

# ===============================
# Telegram Sender
# ===============================
def send_telegram(msg):
    """টেলিগ্রামের মাধ্যমে বার্তা পাঠায়"""
    try:
        r = requests.post(
            SEND_URL,
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
        )
        # প্রিন্ট স্টেটমেন্টটি কমেন্ট করা হলো, কারণ এটি অতিরিক্ত লগ তৈরি করতে পারে
        # if r.status_code != 200:
        #     print("Telegram error:", r.text)
    except Exception as e:
        print("Telegram exception:", e)

# ===============================
# Fetch OHLCV (safe version)
# ===============================
def get_data(ticker, interval, period):
    """yfinance থেকে নিরাপদভাবে OHLCV ডেটা সংগ্রহ করে"""
    try:
        # data fetch
        df = yf.download(ticker, interval=interval, period=period, auto_adjust=False, progress=False)
        if df is None or df.empty:
            return None
            
        df = df[['Open','High','Low','Close','Volume']]
        df.columns = ['open','high','low','close','volume']
        df = df.dropna()
        df.index = pd.to_datetime(df.index, utc=True)
        return df
    except Exception as e:
        # print("Data fetch error:", ticker, e) # লজিক এরর ট্র্যাকিং এর জন্য কমেন্ট করা হলো
        return None

# ===============================
# Indicators
# ===============================
def add_ema(df):
    """ডেটাফ্রেমে EMA(200) যোগ করে"""
    df["ema200"] = df["close"].ewm(span=EMA_PERIOD, adjust=False).mean()
    return df

# ===============================
# Strategy Logic (Simple but stable)
# ===============================
def detect_signal(df_dir, df_entry):
    """ট্রেডিং সিগন্যাল সনাক্ত করে"""

    df_dir = add_ema(df_dir)
    # ট্রেন্ড নির্ধারণ: বুলিশ যদি ক্লোজ EMA200 এর উপরে থাকে, অন্যথায় বিয়ারিশ
    trend = "bull" if df_dir["close"].iloc[-1] > df_dir["ema200"].iloc[-1] else "bear"

    # অর্ডার-ব্লক এর কাছাকাছি দামের অনুমান (last 4th candle in 4h)
    # yfinance এ ডেটা সবসময় UTC টাইমজোন অনুযায়ী থাকে
    if len(df_dir) < 4:
         return None

    ob_candle = df_dir.iloc[-4]
    ob_high = max(ob_candle.open, ob_candle.high, ob_candle.close)
    ob_low  = min(ob_candle.open, ob_candle.low, ob_candle.close)

    cur = df_entry.iloc[-1]
    price = cur.close

    # এন্ট্রি কন্ডিশন
    entry = None
    side = None
    sl = None

    # বুলিশ ট্রেন্ড: যদি দাম OB রেঞ্জের মধ্যে থাকে, লং এন্ট্রি
    if trend == "bull" and ob_low <= price <= ob_high:
        entry = price
        side = "long"
        sl = ob_low * 0.995 # OB লো এর নিচে সামান্য SL

    # বিয়ারিশ ট্রেন্ড: যদি দাম OB রেঞ্জের মধ্যে থাকে, শর্ট এন্ট্রি
    if trend == "bear" and ob_low <= price <= ob_high:
        entry = price
        side = "short"
        sl = ob_high * 1.005 # OB হাই এর উপরে সামান্য SL

    if entry is None:
        return None

    # SL ফ Tলব্যাক: SL% যদি MAX_SL এর বেশি হয়, তবে MAX_SL অনুযায়ী সেট করা হবে
    sl_pct = abs((entry - sl) / entry * 100)
    if sl_pct > MAX_SL:
        if side == "long":
            sl = entry * (1 - MAX_SL/100)
        else:
            sl = entry * (1 + MAX_SL/100)

    # TP লেভেল
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
    """ট্রেডিং সিগন্যালের জন্য টেলিগ্রাম বার্তা তৈরি করে"""
    emoji = "🔵 LONG" if sig["side"]=="long" else "🔴 SHORT"
    
    # SL/TP গণনা: SL এবং TP1 এর মধ্যে দূরত্ব এন্ট্রি থেকে SL এর দূরত্বের গুণিতক হতে হবে
    risk = abs(sig['entry'] - sig['sl'])
    
    # R:R গণনা করা হচ্ছে (এন্ট্রি থেকে TP দূরত্ব / এন্ট্রি থেকে SL দূরত্ব)
    # TP1 R:R
    reward1 = abs(sig['tps'][0] - sig['entry'])
    rr1 = round(reward1 / risk, 2) if risk > 0 else "N/A"
    
    # TP3 R:R (সর্বোচ্চ TP)
    reward3 = abs(sig['tps'][2] - sig['entry'])
    rr3 = round(reward3 / risk, 2) if risk > 0 else "N/A"
    
    msg = f"""
📈 <b>{ticker} — {emoji} Signal</b>

Trend: {sig['trend'].upper()}
Entry: <b>{sig['entry']}</b>
SL: <b>{sig['sl']}</b> (Risk: {round(risk/sig['entry']*100, 2)}%)

Targets (TP):
TP1: {sig['tps'][0]} (R:R ~{rr1})
TP2: {sig['tps'][1]}
TP3: {sig['tps'][2]} (R:R ~{rr3})

⏰ Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
"""
    return msg

# ===============================
# TRADING MAIN LOOP
# ===============================
def main():
    """আপনার প্রধান ট্রেডিং লজিক লুপ ও স্বাস্থ্য পরীক্ষা"""
    sent = {}
    
    # স্বাস্থ্য পরীক্ষার সময় ট্র্যাক করার জন্য
    # ফ্লাস্ক সার্ভার চালু হওয়ার আগে প্রাথমিক বার্তা
    send_telegram("🚀 Swing Crypto Bot Started. (Initial Check)")
    last_health_check_time = time.time() 
    HEALTH_CHECK_SECONDS = HEALTH_CHECK_INTERVAL_MIN * 60

    while True:
        cycle_start = time.time()
        
        # লজিক এরর ট্র্যাক করার জন্য
        logic_error_count = 0
        total_coins_checked = 0

        for coin in COINS:
            total_coins_checked += 1
            try:
                # 1. ডেটা ফেচ
                df_dir = get_data(coin, TF_DIR, "90d")
                df_entry = get_data(coin, TF_ENTRY, "30d")

                if df_dir is None or df_entry is None:
                    # ডেটা ফেচ ব্যর্থ হলে, এটিকে একটি লজিক এরর হিসেবে গণনা করুন
                    print(f"No data or missing data for: {coin}")
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
                        
                    # পুরনো সিগন্যাল পরিষ্কার করা (ঐচ্ছিক, তবে মেমরি ব্যবস্থাপনার জন্য ভাল)
                    # 4 ঘণ্টা পুরনো সিগন্যাল মুছে ফেলা
                    cutoff = time.time() - (4 * 3600)
                    sent = {k: v for k, v in sent.items() if v > cutoff}


            except Exception as e:
                # লজিক বা অন্য কোনো অপ্রত্যাশিত ত্রুটি ধরুন
                print(f"Error processing {coin}: {e}")
                logic_error_count += 1
                
        # ===============================
        # HOURLY HEALTH CHECK LOGIC
        # ===============================
        if (time.time() - last_health_check_time) >= HEALTH_CHECK_SECONDS:
            
            # স্বাস্থ্য পরীক্ষার বার্তা তৈরি করুন
            current_time_utc = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            
            if logic_error_count > 0:
                 # ত্রুটি সহ সতর্কবার্তা
                 health_msg = f"⚠️ <b>Bot Health Warning (1 Hour Cycle)</b>\n"
                 health_msg += f"Time: {current_time_utc}\n"
                 health_msg += f"Status: Logic errors detected.\n"
                 health_msg += f"Details: {logic_error_count} out of {total_coins_checked} coins had data or processing errors in the last cycle."
            else:
                 # সফল বার্তা
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
# KEEP-ALIVE WEB SERVER (Flask)
# ===============================

# Flask অ্যাপ তৈরি করুন
app = Flask(__name__)

# রুট (route) তৈরি করুন যা UptimeRobot বা হোস্টিং প্ল্যাটফর্ম চেক করবে
@app.route('/')
def home():
    """সার্ভার জীবিত আছে কিনা তা নিশ্চিত করার জন্য রুট"""
    return f"Bot is running! Last check at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 200

# থ্রেড ব্যবহার করে Flask সার্ভারটি চালু করার ফাংশন
def run_flask_server():
    """একটি পৃথক থ্রেডে Flask সার্ভার শুরু করে"""
    # Render বা Replit-এ চালানোর জন্য '0.0.0.0' ব্যবহার করা নিরাপদ
    # 8080 পোর্ট ব্যবহার করা হলো কারণ এটি রেন্ডার/অন্যান্য প্ল্যাটফর্মে সাধারণ
    app.run(host='0.0.0.0', port=8080, debug=False)


if __name__ == "__main__":
    # Flask সার্ভারটি একটি নতুন থ্রেডে চালু করুন
    flask_thread = threading.Thread(target=run_flask_server, daemon=True)
    flask_thread.start()

    # প্রধান ট্রেডিং লুপটি চালু করুন
    main()
