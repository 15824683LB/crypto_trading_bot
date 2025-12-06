import pandas as pd
import yfinance as yf
import numpy as np
import warnings
import math 
import time  
import requests 
import hmac
import hashlib
from datetime import datetime, timedelta
import os
import json # JSON-কে আরও নির্ভরযোগ্যভাবে ব্যবহার করার জন্য

warnings.filterwarnings("ignore") 

# ====================================================================
# 🔑 নিরাপত্তা: API KEY ও SECRET KEY লোডিং (আবশ্যিক পরিবর্তন)
# ====================================================================

# ⚠️ WARNING: কোড থেকে API Key, Secret Key এবং Telegram Key/ID সরিয়ে 
#    OS Environment Variable থেকে লোড করা হচ্ছে।
#    লাইভ ডিপ্লয়মেন্টের আগে এই ভেরিয়েবলগুলো (যেমন, RENDER ড্যাশবোর্ড) সেট করুন।

GENERIC_PLACEHOLDER = "PLACEHOLDER_FOR_MOCK_CHECK"
MOCK_MODE = False

API_KEY = os.getenv("COINDCX_API_KEY", GENERIC_PLACEHOLDER)
SECRET_KEY = os.getenv("COINDCX_SECRET_KEY", GENERIC_PLACEHOLDER) 

# টেলিগ্রাম সেটিংস
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", None)
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", None)

if API_KEY == GENERIC_PLACEHOLDER or SECRET_KEY == GENERIC_PLACEHOLDER:
    print("❌ WARNING: API Keys not found in environment variables. Running in MOCK mode.")
    MOCK_MODE = True
else:
    print("✅ API Keys successfully loaded from environment.")


# ====================================================================
# 🔒 CoinDCX API ফাংশন ও নিরাপত্তা (REST API)
# ====================================================================

BASE_URL = "https://api.coindcx.com" 

def create_signature(payload, secret_key):
    """Payload এর উপর ভিত্তি করে HMAC SHA256 Signature তৈরি করে।"""
    # Payload কে JSON string এ রূপান্তর করে (separators=(',', ':') ব্যবহার করে space ছাড়া)
    payload_str = json.dumps(payload, separators=(',', ':'))

    # Secret Key বাইটে এনকোড করা
    secret_bytes = bytes(secret_key, 'utf-8')

    # HMAC-SHA256 হ্যাশ তৈরি করা
    signature = hmac.new(secret_bytes, payload_str.encode('utf-8'), hashlib.sha256).hexdigest()
    return signature

def make_coindcx_request(endpoint, payload):
    """CoinDCX API এ Signed Request পাঠায়।"""
    global MOCK_MODE

    if MOCK_MODE and endpoint not in ["/exchange/v1/users/balances"]: # মক মোডে ব্যালেন্স চেক করার অনুমতি
        return {"status": "mock", "message": f"MOCK request to {endpoint}"}

    # 1. Signature তৈরি
    payload['timestamp'] = int(time.time() * 1000)
    signature = create_signature(payload, SECRET_KEY)

    headers = {
        'X-AUTH-APIKEY': API_KEY,
        'X-AUTH-SIGNATURE': signature,
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(BASE_URL + endpoint, headers=headers, json=payload)
        response.raise_for_status() # HTTP ত্রুটি হলে Exception তৈরি করে
        return response.json()
    except requests.exceptions.HTTPError as err:
        error_msg = f"API HTTP Error: {err.response.status_code} - {err.response.text}"
        print(f"❌ ERROR: {error_msg}")
        # লাইভ ট্রেডিং এর জন্য, API Key ভুল হলে MOCK মোড আর ব্যবহার করা উচিত নয়, 
        # বরং এটি সম্পূর্ণভাবে ব্যর্থ হওয়া উচিত।
        if 'Invalid credentials' in err.response.text or 'invalid signature' in err.response.text:
             send_telegram_message(f"🚨 CRITICAL API KEY ERROR 🚨: {error_msg}. Shutting down.")
             # কোড বন্ধ করার জন্য এখানে SystemExit উত্থাপন করা উচিত।
             raise SystemExit("Critical API Error") 
        return {"error": error_msg}
    except Exception as e:
        print(f"❌ ERROR: General Request Error: {e}")
        return {"error": str(e)}

def get_coindcx_balance():
    """একাউন্ট ব্যালেন্স ফ্রেচ করে।"""
    payload = {}
    return make_coindcx_request("/exchange/v1/users/balances", payload)

def get_coindcx_future_market_id(pair):
    """ফিউচার মার্কেটের ID বের করে (লাইভ ডেটা থেকে এটি ফ্রেচ করা ভালো)"""
    # 💡 পরামর্শ: এই ম্যাপটি হার্ডকোড না করে, CoinDCX-এর Market Data API থেকে ফ্রেচ করে নিশ্চিত করুন।
    FUTURE_MAP = {
        "SOL/INR": "SOLUSDTF",
        "XRP/INR": "XRPUSDTF",
        "ADA/INR": "ADAUSDTF"
    }
    return FUTURE_MAP.get(pair, None)

# ====================================================================
# 🛠️ API কী লোডিং এবং ক্লায়েন্ট ইনিশিয়ালাইজেশন (সংশোধিত)
# ====================================================================

# শুধুমাত্র MOCK_MODE না হলে ব্যালেন্স চেক করা হবে।
if not MOCK_MODE:
    try:
        balance_response = get_coindcx_balance()

        if 'error' in balance_response:
            raise Exception(f"API connection failed: {balance_response['error']}")

        # ব্যালেন্স সফল হলে টেলিগ্রামে স্ট্যাটাস মেসেজ পাঠানো
        total_balance = "N/A"
        # CoinDCX থেকে USDT বা INR ব্যালেন্স খুঁজে বের করে এখানে যোগ করা যেতে পারে
        send_telegram_message("✅ CoinDCX Futures Algo Initialized! Balance check successful.")
        print(f"✅ API Keys configured and CoinDCX client initialized. Balance check successful.")

    except SystemExit as e:
        print(f"❌ CRITICAL SHUTDOWN: {e}")
        exit() # গুরুত্বপূর্ণ API ত্রুটির কারণে বন্ধ
    except Exception as e:
        print(f"❌ WARNING: API Initialization failed ({e}). Switching to MOCK mode.")
        MOCK_MODE = True
        send_telegram_message(f"⚠️ API Init Failed: {e}. Switching to MOCK mode.")

# =========================
# ⚙️ CoinDCX অ্যালগো সেটিংস 
# =========================
CAPITAL_INR = 10000.0   # মোট পজিশন ভ্যালু এই ক্যাপিটালের ভিত্তিতে গণনা হবে
RISK_PER_TRADE_PCT = 0.5 # প্রতি ট্রেডে মোট ক্যাপিটালের উপর সর্বোচ্চ ঝুঁকি
MAX_SL_PCT = 3.0         # পজিশন থেকে স্টপ লস-এর সর্বোচ্চ শতাংশ দূরত্ব
LEVERAGE = 5             
TF_DIR = "1h"       
TF_ENTRY = "15m"    
EMA_PERIOD = 200    
ATR_MULTIPLIER = 2.0 
RR_TARGETS = [2.0]  
COINDCX_PAIRS = ["SOL/INR", "XRP/INR", "ADA/INR"] 
YF_TICKERS = {
    "SOL/INR": "SOL-USD",
    "XRP/INR": "XRP-USD",
    "ADA/INR": "ADA-USD"
}
ACTIVE_ORDERS = {} # বর্তমানে খোলা অর্ডার ট্র্যাক করার জন্য

# ===============================
# 📬 টেলিগ্রাম ফাংশন
# ===============================
def send_telegram_message(message):
    """টেলিগ্রামের মাধ্যমে একটি মেসেজ পাঠায়।"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        # মক মোডে থাকলে প্রিন্ট করবে
        if MOCK_MODE:
             print(f"[Telegram MOCK] {message}")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        requests.post(url, json=payload).raise_for_status() 
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

# ===============================
# 💰 পজিশন সাইজিং লজিক (Position Sizing Logic)
# ===============================
def calculate_position_size(entry_price, sl_price):
    """
    Max Risk per Trade এবং SL দূরত্বের উপর ভিত্তি করে পজিশন সাইজ (Volume) গণনা করে।
    """
    # SL দূরত্ব (শতাংশ)
    risk_pct_on_trade = abs(entry_price - sl_price) / entry_price
    
    # মোট ঝুঁকির পরিমাণ (INR)
    max_risk_inr = CAPITAL_INR * (RISK_PER_TRADE_PCT / 100)

    if risk_pct_on_trade == 0:
        return 0.0, 0.0 

    # লিভারেজ সহ পজিশনের মোট ভ্যালু (INR)
    position_value_inr = max_risk_inr / risk_pct_on_trade
    
    # Volume (ইউনিট) গণনা করা: Volume = Position Value / Entry Price
    # USD (YF) প্রাইস ব্যবহার করে ভলিউম গণনা করা হচ্ছে, কারণ INR প্রাইস সরাসরি নেই।
    # এটি একটি সম্ভাব্য ত্রুটি, লাইভ ট্রেডিংয়ে CoinDCX থেকে USDT মূল্য ব্যবহার করা ভালো।
    volume_to_trade = position_value_inr / entry_price 

    # CoinDCX-এ ন্যূনতম অর্ডার ভ্যালু চেক করা উচিত (ধরা যাক 500 INR)
    if position_value_inr < 500 and not MOCK_MODE:
        # ন্যূনতম পজিশন সাইজ পূরণ না হলে ট্রেড বাতিল করা
        return 0.0, 0.0

    # CoinDCX API-এর জন্য সঠিক দশমিক স্থানে রাউন্ড করা গুরুত্বপূর্ণ (যেমন, XRP-এর জন্য ৪)
    # এখানে আমরা ধরে নিচ্ছি ৪ দশমিক স্থানই যথেষ্ট
    return round(position_value_inr * LEVERAGE, 2), round(volume_to_trade * LEVERAGE, 4) # লিভারেজ যোগ করা

# ===============================
# 🤖 লাইভ অর্ডার প্লেসমেন্ট (CoinDCX REST API)
# ===============================

def live_place_order(pair, side, volume, sl_price, tp_price):
    """
    CoinDCX Future API এ মার্কেট অর্ডার, SL এবং TP অর্ডার প্লেস করে।
    """
    market_id = get_coindcx_future_market_id(pair)
    if not market_id:
        print(f"❌ ERROR: Future Market ID not found for {pair}")
        send_telegram_message(f"❌ Order Failed: Market ID not found for {pair}")
        return None

    if MOCK_MODE:
        print(f"\n--- 🤖 MOCK ORDER PLACED (CoinDCX) ---")
        print(f"  Symbol: {market_id}, Side: {side}, Volume: {volume}, SL: {sl_price:.4f}, TP: {tp_price:.4f}")
        print("---------------------------------------")
        return {"orderId": f"MOCK_{market_id}_{int(time.time())}", "status": "filled"} 

    try:
        # 1. মার্কেট অর্ডার প্লেস করা (Main Entry)
        # side: 'buy' for Long, 'sell' for Short
        main_order_payload = {
            "symbol": market_id,
            "side": side.lower(),
            "order_type": "market",
            "quantity": round(volume, 4), 
            "leverage": LEVERAGE
        }
        order_response = make_coindcx_request("/exchange/v1/futures/order/create", main_order_payload)

        if 'error' in order_response or order_response.get('status') != 'filled': # সফল মার্কেট অর্ডার 'filled' হওয়া উচিত
            raise Exception(f"Main Order failed: {order_response}")

        order_id = order_response.get('orderId', 'N/A')
        
        # 2. SL অর্ডার প্লেস করা (Stop Limit)
        sl_side = 'sell' if side.upper() == 'LONG' else 'buy'
        sl_payload = {
            "symbol": market_id,
            "side": sl_side,
            "order_type": "stop_limit", 
            "quantity": round(volume, 4),
            "stop_price": round(sl_price, 4),
            # Limit Price = Stop Price-এর কাছাকাছি একটি মূল্য
            # এটি নিশ্চিত করে যে Stop ট্রিগার হলেও একটি নির্দিষ্ট দামে ফিলাপ হয়
            "price": round(sl_price * 0.999, 4) if sl_side == 'sell' else round(sl_price * 1.001, 4),
            "leverage": LEVERAGE
        }
        sl_response = make_coindcx_request("/exchange/v1/futures/order/create", sl_payload)

        # 3. TP অর্ডার প্লেস করা (Limit)
        tp_side = 'sell' if side.upper() == 'LONG' else 'buy'
        tp_payload = {
            "symbol": market_id,
            "side": tp_side,
            "order_type": "limit",
            "quantity": round(volume, 4),
            "price": round(tp_price, 4),
            "leverage": LEVERAGE
        }
        tp_response = make_coindcx_request("/exchange/v1/futures/order/create", tp_payload)

        # SL/TP অর্ডার ব্যর্থ হলে শুধু ওয়ার্নিং দেওয়া হলো, তবে মেইন অর্ডার খোলা থাকবে
        sl_id = sl_response.get('orderId', 'SL_FAILED')
        tp_id = tp_response.get('orderId', 'TP_FAILED')
        
        if 'error' in sl_response or 'error' in tp_response:
             send_telegram_message(f"⚠️ Warning: SL/TP Order Placement Failed for {pair}. Check manually!")
             
        message = f"✅ LIVE ORDER SUCCESS | {pair} **{side.upper()}** @ {order_response.get('avgPrice', 'N/A')}\n* Volume: {volume:.4f} \n* SL: {sl_price:.4f} (ID: {sl_id})\n* TP: {tp_price:.4f} (ID: {tp_id})"
        send_telegram_message(message)
        print(message)

        return {"orderId": order_id, "status": "open", "slId": sl_id, "tpId": tp_id}

    except Exception as e:
        error_message = f"❌ LIVE ORDER FAILED on {pair}: {e}"
        send_telegram_message(error_message)
        print(error_message)
        return None

# ===============================
# 🧪 ইন্ডিকেটর এবং সিগন্যাল লজিক (পূর্বের মতোই)
# ===============================
# add_indicators, detect_signal ফাংশনগুলি আগের মতোই থাকবে কারণ সেগুলি শুধুমাত্র ডেটা বিশ্লেষণের জন্য।

def add_indicators(df):
    """ডেটাফ্রেমে EMA(200), EMA(21), ATR, MACD এবং RSI যোগ করে"""
    df_copy = df.copy() 
    df_copy["ema200"] = df_copy["Close"].ewm(span=EMA_PERIOD, adjust=False).mean() 
    df_copy["ema12"] = df_copy["Close"].ewm(span=12, adjust=False).mean()
    df_copy["ema26"] = df_copy["Close"].ewm(span=26, adjust=False).mean()
    df_copy["macd_line"] = df_copy["ema12"] - df_copy["ema26"]
    df_copy["macd_signal"] = df_copy["macd_line"].ewm(span=9, adjust=False).mean()
    high_low = df_copy["High"] - df_copy["Low"] 
    high_close = np.abs(df_copy["High"] - df_copy["Close"].shift())
    low_close = np.abs(df_copy["Low"] - df_copy["Close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df_copy["atr"] = tr.ewm(span=14, adjust=False).mean()
    delta = df_copy['Close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(com=13, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(com=13, adjust=False).mean()
    rs = gain / loss
    df_copy['rsi'] = 100 - (100 / (1 + rs))
    df_copy['close'] = df_copy['Close'] 
    return df_copy.dropna()

def detect_signal(df_dir_slice, df_entry_slice):
    """সিগন্যাল সনাক্ত করে"""
    if len(df_dir_slice) < EMA_PERIOD or len(df_entry_slice) < 14:
         return None

    trend = "bull" if df_dir_slice["close"].iloc[-1] > df_dir_slice["ema200"].iloc[-1] else "bear"
    ob_candles = df_dir_slice.iloc[-5:-1] 
    ob_low  = ob_candles["Low"].min()
    ob_high = ob_candles["High"].max()
    cur = df_entry_slice.iloc[-1]
    price = cur.close
    atr_val = cur.atr
    rsi_val = cur.rsi
    macd_line = df_dir_slice["macd_line"].iloc[-1]
    macd_signal = df_dir_slice["macd_signal"].iloc[-1]
    macd_bullish = macd_line > macd_signal
    macd_bearish = macd_line < macd_signal

    sl_distance = atr_val * ATR_MULTIPLIER

    entry, side, sl = None, None, None

    # Long Entry 
    if trend == "bull" and macd_bullish and ob_low <= price <= ob_high and rsi_val > 55:
        entry = price
        side = "long"
        sl = entry - sl_distance 

    # Short Entry
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

    # TP/BE Level
    rr = RR_TARGETS[0]
    tp1 = entry + (risk_distance * rr) if side == "long" else entry - (risk_distance * rr)
    # be_level = entry + risk_distance if side == "long" else entry - risk_distance # বর্তমানে ব্যবহার হচ্ছে না
    
    # নিশ্চিত করুন যে SL/TP মূল্য নেতিবাচক না হয় বা এন্ট্রি প্রাইসের খুব কাছাকাছি না হয়
    if (side == "long" and (sl >= entry or tp1 <= entry)) or \
       (side == "short" and (sl <= entry or tp1 >= entry)):
        print("❌ Signal Rejected: SL/TP calculation error.")
        return None

    return {
        "side": side,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "risk_distance": risk_distance
    }


# ===============================
# 🚀 অ্যালগো মেইন লুপ 
# ===============================

def run_algo_monitor_loop():
    global ACTIVE_ORDERS
    last_heartbeat_time = datetime.now() - timedelta(hours=2) 
    print(f"\n--- 🤖 CoinDCX 24/7 Algo Monitor Started ---")

    while True:
        current_time = datetime.now()

        # ১ ঘন্টায় একবার হার্টবিট মেসেজ পাঠানো
        if current_time - last_heartbeat_time >= timedelta(hours=1):
            status_msg = f"❤️ Algo Heartbeat - {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            status_msg += f"Monitor is running smoothly. Active Orders: **{len(ACTIVE_ORDERS)}** (Mode: {'MOCK' if MOCK_MODE else 'LIVE'})"
            send_telegram_message(status_msg)
            last_heartbeat_time = current_time

        start_date = (current_time - pd.Timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = current_time.strftime('%Y-%m-%d')

        for cdcx_pair in COINDCX_PAIRS:
            # যদি বর্তমানে কোনো অর্ডার খোলা থাকে, তাহলে নতুন সিগন্যাল চেক করা হবে না
            if cdcx_pair in ACTIVE_ORDERS and ACTIVE_ORDERS[cdcx_pair]['status'] == 'open':
                print(f"[{cdcx_pair}] Skipping check: Order already active.")
                continue

            yf_ticker = YF_TICKERS[cdcx_pair]

            # 1. ডেটা ফ্রেচ ও ইন্ডিকেটর গণনা
            try:
                # yf.download-এ today() ব্যবহার করা হলো যাতে শেষ ক্যান্ডেলটি পাওয়া যায়
                df_dir = yf.download(yf_ticker, interval=TF_DIR, period="7d", progress=False, auto_adjust=False).dropna()
                df_entry = yf.download(yf_ticker, interval=TF_ENTRY, period="7d", progress=False, auto_adjust=False).dropna()
            except Exception as e:
                print(f"Error fetching data for {cdcx_pair}: {e}")
                continue

            if df_dir.empty or df_entry.empty:
                continue

            df_dir = add_indicators(df_dir)
            df_entry = add_indicators(df_entry)

            # 2. সিগন্যাল সনাক্তকরণ
            sig = detect_signal(df_dir, df_entry)

            if sig:
                print(f"  ✅ Signal Found: {sig['side'].upper()} @ {sig['entry']:.4f} for {cdcx_pair}")

                # 3. পজিশন সাইজিং
                # পজিশন ভ্যালু এবং ভলিউম গণনা 
                position_value_inr, volume_to_trade = calculate_position_size(sig['entry'], sig['sl'])

                if volume_to_trade == 0.0:
                    print(f"[{cdcx_pair}] Signal rejected: Position size is too small or SL distance is zero.")
                    continue

                # 4. লাইভ অর্ডার প্লেসমেন্ট (TP/SL সহ)
                order_response = live_place_order(
                    cdcx_pair, 
                    sig['side'].upper(), 
                    volume_to_trade, 
                    sig['sl'], 
                    sig['tp1']
                )

                if order_response and order_response.get('status') == 'open':
                    ACTIVE_ORDERS[cdcx_pair] = {
                        "id": order_response.get('orderId', 'N/A'),
                        "status": "open",
                        "side": sig['side'],
                        "entry": sig['entry'],
                        "sl": sig['sl'],
                        "tp1": sig['tp1'],
                        "volume": volume_to_trade,
                        "time": current_time.strftime('%Y-%m-%d %H:%M:%S')
                    }
            else:
                pass 

        # ১৫ মিনিট অপেক্ষা
        print(f"\nSleeping for 15 minutes...")
        time.sleep(15 * 60) 

# ===============================
# 🚀 মূল এক্সিকিউশন
# ===============================
if __name__ == "__main__":
    try:
        run_algo_monitor_loop()
    except KeyboardInterrupt:
        print("\nMonitor stopped manually.")
    except SystemExit as e:
        print(f"\nSystem exiting due to critical error: {e}")
    except Exception as e:
        error_msg = f"CRITICAL ERROR: Algo crashed! {e}"
        print(error_msg)
        send_telegram_message(f"🚨 CRASH ALERT 🚨: {error_msg}")
    
