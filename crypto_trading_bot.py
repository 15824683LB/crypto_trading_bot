import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime
import warnings
import requests 
import time
import json # ডেটা পারসিসটেন্সের জন্য

warnings.filterwarnings("ignore") 

# শেষ কবে Alive চেক মেসেজ পাঠানো হয়েছে, তা ট্র্যাক করার জন্য
LAST_ALIVE_CHECK = None 

# =========================
# ⚙️ টেলিগ্রাম সেটিংস (TELEGRAM SETTINGS)
# =========================
# আপনার নিজস্ব টেলিগ্রাম বট টোকেন এবং চ্যাট আইডি দিন
TELEGRAM_BOT_TOKEN = "8537811183:AAF4DWeA5Sks86mBISJvS1iNvLRpkY_FgnA"  
TELEGRAM_CHAT_ID = "8191014589"     

# =========================
# ⚙️ ট্রেডিং সেটিংস (TRADING SETTINGS)
# =========================

COINS = [
    "ADA-USD",
    "BNB-USD", 
    "BTC-USD", 
    "DOGE-USD",
    "SOL-USD"
]

TF_DIR = "4h"       # ট্রেন্ড নির্ধারণ
TF_ENTRY = "1h"     # এন্ট্রি ম্যানেজমেন্ট

EMA_PERIOD = 200    
ATR_PERIOD = 14     
ATR_MULTIPLIER = 2.0 # SL দূরত্ব
TP_MULTIPLIER = 4.0  # TP দূরত্ব (1:2 R:R)

MAX_SL_PCT = 3.0    # সর্বোচ্চ ঝুঁকি

# ===============================
# 💾 ডেটা পারসিসটেন্স ফাংশন
# ===============================
def load_open_trades():
    """trades.json ফাইল থেকে ওপেন ট্রেড লোড করে"""
    try:
        with open('trades.json', 'r') as f:
            print("Trades loaded successfully from trades.json.")
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print("No trades file found or file corrupted. Starting fresh.")
        return {}

def save_open_trades(trades):
    """trades.json ফাইলে ওপেন ট্রেড সেভ করে"""
    try:
        with open('trades.json', 'w') as f:
            json.dump(trades, f, indent=4)
    except Exception as e:
        print(f"Error saving trades to file: {e}")

# ===============================
# 📣 টেলিগ্রাম ফাংশন
# ===============================
def send_telegram_message(message):
    """টেলিগ্রামের মাধ্যমে একটি মেসেজ পাঠায়"""
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN" or TELEGRAM_CHAT_ID == "YOUR_CHAT_ID":
        print(f"TELEGRAM ALERT (Not Sent - Config Missing): {message}")
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        requests.post(url, data=payload)
    except requests.exceptions.RequestException as e:
        print(f"Error sending Telegram message: {e}")

# ===============================
# 📊 ডেটা সংগ্রহ (Data Fetch)
# ===============================
def get_data(ticker, interval, start_date=None, end_date=None):
    try:
        # 4h ও 1h ডেটার জন্য যথেষ্ট ডেটা fetch করা হচ্ছে 
        df = yf.download(ticker, interval=interval, period='5d', auto_adjust=False, progress=False) 
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
# 🧪 ইন্ডিকেটর ক্যালকুলেশন (Indicators)
# ===============================
def add_indicators(df):
    df_copy = df.copy() 
    
    # EMA, MACD, ATR, RSI ক্যালকুলেশন... (লজিক অপরিবর্তিত)
    df_copy["ema200"] = df_copy["close"].ewm(span=EMA_PERIOD, adjust=False).mean()
    df_copy["ema12"] = df_copy["close"].ewm(span=12, adjust=False).mean()
    df_copy["ema26"] = df_copy["close"].ewm(span=26, adjust=False).mean()
    df_copy["macd_line"] = df_copy["ema12"] - df_copy["ema26"]
    df_copy["macd_signal"] = df_copy["macd_line"].ewm(span=9, adjust=False).mean()

    high_low = df_copy["high"] - df_copy["low"]
    high_close = np.abs(df_copy["high"] - df_copy["close"].shift())
    low_close = np.abs(df_copy["low"] - df_copy["close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df_copy["atr"] = tr.ewm(span=ATR_PERIOD, adjust=False).mean()

    delta = df_copy['close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(com=ATR_PERIOD-1, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(com=ATR_PERIOD-1, adjust=False).mean()
    rs = gain / loss
    df_copy['rsi'] = 100 - (100 / (1 + rs))

    return df_copy

# ===============================
# 🎯 সিগন্যাল লজিক (Signal Logic)
# ===============================
def detect_signal(df_dir_slice, df_entry_slice):
    if len(df_dir_slice) < EMA_PERIOD or len(df_entry_slice) < ATR_PERIOD:
         return None

    # Trend Determination
    trend = "bull" if df_dir_slice["close"].iloc[-1] > df_dir_slice["ema200"].iloc[-1] else "bear"
    
    # OB/Zon (Pullback Zone)
    ob_candles = df_dir_slice.iloc[-5:-1] 
    ob_high = ob_candles["high"].max()
    ob_low  = ob_candles["low"].min()

    cur = df_entry_slice.iloc[-1]
    price = cur.close
    atr_val = cur.atr
    rsi_val = cur.rsi
    
    # MACD Confirmation
    macd_line = df_dir_slice["macd_line"].iloc[-1]
    macd_signal = df_dir_slice["macd_signal"].iloc[-1]
    macd_bullish = macd_line > macd_signal
    macd_bearish = macd_line < macd_signal

    # Risk/Reward Levels
    sl_distance = atr_val * ATR_MULTIPLIER
    tp_distance = atr_val * TP_MULTIPLIER

    entry, side, sl = None, None, None

    # Long Entry Condition (Trend: Bull, Pullback Zone, MACD Bullish, RSI > 55)
    if trend == "bull" and macd_bullish and ob_low <= price <= ob_high and rsi_val > 55:
        entry = price
        side = "long"
        sl = entry - sl_distance

    # Short Entry Condition (Trend: Bear, Pullback Zone, MACD Bearish, RSI < 45)
    if trend == "bear" and macd_bearish and ob_low <= price <= ob_high and rsi_val < 45:
        entry = price
        side = "short"
        sl = entry + sl_distance

    if entry is None:
        return None

    # SL Fallback (MAX_SL_PCT)
    sl_pct = abs((entry - sl) / entry * 100)
    if sl_pct > MAX_SL_PCT:
        if side == "long":
            sl = entry * (1 - MAX_SL_PCT/100)
        else:
            sl = entry * (1 + MAX_SL_PCT/100)
            
    risk_distance = abs(entry - sl)
    tp1 = entry + tp_distance if side == "long" else entry - tp_distance
    be_level = entry + risk_distance if side == "long" else entry - risk_distance 

    return {
        "side": side,
        "entry": round(entry,6),
        "sl": round(sl,6),
        "tp1": round(tp1, 6),
        "be_level": round(be_level, 6),
        "risk_distance": risk_distance
    }

# ----------------------------------------------------
# 💖 Alive Checker Function
# ----------------------------------------------------
def check_and_send_alive_status():
    """চেক করে যে মনিটর চালু আছে কিনা, এবং প্রতি 24 ঘন্টায় একবার টেলিগ্রামে মেসেজ পাঠায়।"""
    global LAST_ALIVE_CHECK
    
    ALIVE_INTERVAL = 86400 # 24 ঘন্টা = 86400 সেকেন্ড
    
    current_time = time.time()
    
    if LAST_ALIVE_CHECK is None or (current_time - LAST_ALIVE_CHECK) > ALIVE_INTERVAL:
        
        # টেলিগ্রাম মেসেজ 
        msg = (
            f"💖 *MONITOR ALIVE CHECK - HEARTBEAT*\n"
            f"Status: Trading Monitor is running successfully on Render.\n"
            f"Active Coins: {', '.join(COINS)}\n"
            f"Last Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}"
        )
        send_telegram_message(msg)
        
        # সময় আপডেট করুন
        LAST_ALIVE_CHECK = current_time
        print("\n[HEARTBEAT] Alive status sent to Telegram.")
    else:
        # 24 ঘন্টা পার না হলে শুধুমাত্র কনসোলে প্রিন্ট করুন
        time_to_next_check = int((ALIVE_INTERVAL - (current_time - LAST_ALIVE_CHECK)) / 3600)
        print(f"\n[ALIVE] Monitor is running. Next Telegram check in: {time_to_next_check} hours.")

# ===============================
# 📣 লাইভ সিগন্যাল মনিটর (LIVE SIGNAL MONITOR)
# ===============================
def monitor_signals():
    """নির্দিষ্ট কয়েনগুলির জন্য লাইভ সিগন্যাল চেক করে এবং টেলিগ্রাম অ্যালার্ট পাঠায়"""
    
    global open_trades
    
    # --- Alive Check ---
    check_and_send_alive_status() 
    # -------------------
    
    print(f"\n--- Checking Signals at {datetime.now().strftime('%H:%M:%S')} IST ---")
    
    for ticker in COINS:
        
        # ১. ডেটা ফেচ
        df_dir = get_data(ticker, TF_DIR)
        df_entry = get_data(ticker, TF_ENTRY)

        if df_dir is None or df_entry is None:
            continue

        df_dir = add_indicators(df_dir)
        df_entry = add_indicators(df_entry)
        
        # ২. সিগন্যাল জেনারেশন
        df_dir_slice = df_dir.dropna()
        df_entry_slice = df_entry.dropna()
        
        sig = detect_signal(df_dir_slice, df_entry_slice)
        
        # --- (A) নতুন এন্ট্রি সিগন্যাল ---
        if sig and ticker not in open_trades:
            
            msg = (
                f"🚀 *New ATR Breakout Signal - {ticker}*\n"
                f"Direction: {sig['side'].upper()}\n"
                f"Entry Price: ${sig['entry']:.6f}\n"
                f"Stop Loss: ${sig['sl']:.6f}\n"
                f"Target (1:2 R:R): ${sig['tp1']:.6f}\n"
                f"1:1 R:R Level (BE Trigger): ${sig['be_level']:.6f}"
            )
            send_telegram_message(msg)
            
            open_trades[ticker] = sig
            save_open_trades(open_trades) # ট্রেড সেভ করা হলো
            
        # --- (B) ট্রেইলিং SL অ্যালার্ট (Break-Even Simulation) ---
        elif ticker in open_trades:
            
            current_price = df_entry.iloc[-1]['close']
            trade = open_trades[ticker]
            
            be_hit = False
            if trade['side'] == 'long' and current_price >= trade['be_level']:
                be_hit = True
            elif trade['side'] == 'short' and current_price <= trade['be_level']:
                be_hit = True

            # যদি 1:1 হিট করে এবং এখনও অ্যালার্ট না দেওয়া হয়ে থাকে
            if be_hit and trade.get('sl_shift_alert') != True:
                
                msg = (
                    f"⚠️ *SL SHIFT ALERT - {ticker} ({trade['side'].upper()})*\n"
                    f"Price hit 1:1 R:R level (${trade['be_level']:.6f}).\n"
                    f"Please **MOVE STOP LOSS to ENTRY PRICE** (${trade['entry']:.6f}) on your exchange."
                )
                send_telegram_message(msg)
                
                open_trades[ticker]['sl_shift_alert'] = True
                save_open_trades(open_trades) # ট্র্যাকিং স্ট্যাটাস সেভ করা হলো
                
        # --- (C) ওপেন ট্রেড চেক (শুধুমাত্র কনসোলে) ---
        if ticker in open_trades:
            print(f"Tracking {ticker} | Side: {open_trades[ticker]['side'].upper()} | Entry: {open_trades[ticker]['entry']:.4f}")

# ===============================
# 🚀 মূল এক্সিকিউশন (MAIN EXECUTION)
# ===============================
if __name__ == "__main__":
    
    # স্ক্রিপ্ট শুরু হওয়ার সময় পূর্ববর্তী ট্রেডগুলি লোড করা হলো
    open_trades = load_open_trades()
    
    # 1h টাইমফ্রেম অনুযায়ী প্রতি 60 মিনিট অপেক্ষা
    CHECK_INTERVAL_SECONDS = 3600 

    print("--- Starting Trading Monitor Loop ---")
    
    while True:
        monitor_signals()
        print(f"Sleeping for {CHECK_INTERVAL_SECONDS / 60} minutes...")
        time.sleep(CHECK_INTERVAL_SECONDS)

