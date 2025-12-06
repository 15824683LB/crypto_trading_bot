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

warnings.filterwarnings("ignore") 

# ====================================================================
# 🔑 API KEY & SECRET KEY (আপনার আসল কী বসান!)
# ====================================================================

# ⚠️ নিশ্চিত করুন, এখানে আপনার আসল Key গুলোই আছে!
API_KEY = "7483bb977c62d522309a78787db49f69a2db134edc95efb5"
SECRET_KEY = "ef01906f8368cbcc3027e98f1d5fc1cede7e909e9890732502af20d674580e6d" 

# টেলিগ্রাম সেটিংস
TELEGRAM_BOT_TOKEN = "8537811183:AAF4DWeA5Sks86mBISJvS1iNvLRpkY_FgnA"
TELEGRAM_CHAT_ID = "8191014589"

# এই প্লেসহোল্ডারটি শুধুমাত্র চেক করার জন্য
GENERIC_PLACEHOLDER = "PLACEHOLDER_FOR_MOCK_CHECK"
MOCK_MODE = False


# ====================================================================
# 🔒 CoinDCX API ফাংশন ও নিরাপত্তা (REST API)
# ====================================================================

BASE_URL = "https://api.coindcx.com" 

def create_signature(payload, secret_key):
    """Payload এর উপর ভিত্তি করে HMAC SHA256 Signature তৈরি করে।"""
    # Payload কে JSON string এ রূপান্তর করে (no space)
    payload_str = requests.json.dumps(payload, separators=(',', ':'))

    # Secret Key বাইটে এনকোড করা
    secret_bytes = bytes(secret_key, 'utf-8')

    # HMAC-SHA256 হ্যাশ তৈরি করা
    signature = hmac.new(secret_bytes, payload_str.encode('utf-8'), hashlib.sha256).hexdigest()
    return signature

def make_coindcx_request(endpoint, payload):
    """CoinDCX API এ Signed Request পাঠায়।"""
    global MOCK_MODE

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
        if 'Invalid credentials' in err.response.text or 'invalid signature' in err.response.text:
             # যদি API কী এর কারণে বারবার ভুল আসে, তবে মক মোডে চলে যাওয়া উচিত।
             MOCK_MODE = True
             return {"error": error_msg}
        return {"error": error_msg}
    except Exception as e:
        print(f"❌ ERROR: General Request Error: {e}")
        return {"error": str(e)}

def get_coindcx_balance():
    """একাউন্ট ব্যালেন্স (Future Wallet) ফ্রেচ করে।"""
    payload = {}
    return make_coindcx_request("/exchange/v1/users/balances", payload)

def get_coindcx_future_market_id(pair):
    """'SOL/INR' থেকে 'SOLUSDT' বা মার্কেটের ID বের করে (সাধারণত CoinDCX সরাসরি মার্কেট আইডি চায়)"""
    # যেহেতু CoinDCX Future API-এর পেয়ারের নাম আলাদা (যেমন BTCUSDTF), 
    # আমরা ধরে নিচ্ছি যে pair (যেমন SOL/INR) এর অংশগুলিকে কনভার্ট করতে হবে।
    # এটি লাইভ করার জন্য আপনাকে CoinDCX API ডকুমেন্টেশন অনুযায়ী ফিউচার পেয়ারের নাম নিশ্চিত করতে হবে।

    # আপাতত আমরা USD/INR পেয়ারকে (যেমন SOL/INR) ফিউচার পেয়ারের সাথে ম্যাপ করার জন্য একটি ডিকশনারি ব্যবহার করব।
    # CoinDCX এ ফিউচার পেয়ার সাধারণত USDT ফিউচার হয়। 

    # এই অংশে আপনার আসল ফিউচার পেয়ারের ID বসান (যেমন SOLUSDTF বা XRPUSDTF)
    FUTURE_MAP = {
        "SOL/INR": "SOLUSDTF",
        "XRP/INR": "XRPUSDTF",
        "ADA/INR": "ADAUSDTF"
    }
    return FUTURE_MAP.get(pair, None)


# ====================================================================
# 🛠️ API কী লোডিং এবং ক্লায়েন্ট ইনিশিয়ালাইজেশন (সংশোধিত)
# ====================================================================
try:
    if API_KEY == GENERIC_PLACEHOLDER or SECRET_KEY == GENERIC_PLACEHOLDER:
        raise ValueError("API Keys are still placeholders.")

    # API কানেকশন চেক করার জন্য ব্যালেন্স ফ্রেচ করা
    balance_response = get_coindcx_balance()

    if 'error' in balance_response:
        raise Exception(f"API connection failed: {balance_response['error']}")

    # এখানে CoinDCX এর Balance Response কে format করে দেখানো হলো
    total_balance = "N/A"
    print(f"✅ API Keys configured and CoinDCX client initialized. Balance check successful.")

except ValueError as e:
    print(f"❌ WARNING: API Initialization failed ({e}). Running in MOCK mode.")
    MOCK_MODE = True

except Exception as e:
    print(f"❌ WARNING: API Initialization failed ({e}). Running in MOCK mode.")
    MOCK_MODE = True

# =========================
# ⚙️ CoinDCX অ্যালগো সেটিংস 
# =========================
CAPITAL_INR = 10000.0   
RISK_PER_TRADE_PCT = 0.5 
MAX_SL_PCT = 3.0         
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
ACTIVE_ORDERS = {} 

# ===============================
# 📬 টেলিগ্রাম ফাংশন
# ===============================
def send_telegram_message(message):
    """টেলিগ্রামের মাধ্যমে একটি মেসেজ পাঠায়।"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
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
# 💰 পজিশন সাইজিং লজিক
# ===============================
def calculate_position_size(entry_price, sl_price, ticker_price):
    """
    Max Risk per Trade এবং SL দূরত্বের উপর ভিত্তি করে পজিশন সাইজ (Volume) গণনা করে।
    """
    risk_pct_on_trade = abs(entry_price - sl_price) / entry_price
    max_risk_inr = CAPITAL_INR * (RISK_PER_TRADE_PCT / 100)

    if risk_pct_on_trade == 0:
        return 0.0, 0.0 

    position_value_inr = max_risk_inr / risk_pct_on_trade
    volume_to_trade = position_value_inr / ticker_price

    if position_value_inr < 500: 
        position_value_inr = 500
        volume_to_trade = position_value_inr / ticker_price


    return round(position_value_inr, 2), round(volume_to_trade, 4)

# ===============================
# 🧪 ইন্ডিকেটর এবং সিগন্যাল লজিক (পূর্বের মতোই)
# ===============================

def add_indicators(df):
    """ডেটাফ্রেমে EMA(200), EMA(21), ATR, MACD এবং RSI যোগ করে"""
    df_copy = df.copy() 

    df_copy["ema200"] = df_copy["Close"].ewm(span=EMA_PERIOD, adjust=False).mean() 
    df_copy["ema21"] = df_copy["Close"].ewm(span=21, adjust=False).mean() 
    df_copy["ema12"] = df_copy["Close"].ewm(span=12, adjust=False).mean()
    df_copy["ema26"] = df_copy["Close"].ewm(span=26, adjust=False).mean()
    df_copy["macd_line"] = df_copy["ema12"] - df_copy["ema26"]
    df_copy["macd_signal"] = df_copy["macd_line"].ewm(span=9, adjust=False).mean()

    # ATR গণনা
    high_low = df_copy["High"] - df_copy["Low"] 
    high_close = np.abs(df_copy["High"] - df_copy["Close"].shift())
    low_close = np.abs(df_copy["Low"] - df_copy["Close"].shift())

    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df_copy["atr"] = tr.ewm(span=14, adjust=False).mean()

    # RSI গণনা
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

    # 1. ট্রেন্ড, OB Zone, এবং Indicators
    trend = "bull" if df_dir_slice["close"].iloc[-1] > df_dir_slice["ema200"].iloc[-1] else "bear"
    ob_candles = df_dir_slice.iloc[-5:-1] 
    ob_high = ob_candles["High"].max()
    ob_low  = ob_candles["Low"].min()
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
    be_level = entry + risk_distance if side == "long" else entry - risk_distance

    return {
        "side": side,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "be_level": be_level,
        "risk_distance": risk_distance
    }


# ===============================
# 🤖 লাইভ অর্ডার প্লেসমেন্ট (CoinDCX REST API)
# ===============================

def live_place_order(pair, side, volume, sl_price, tp_price):
    """
    CoinDCX Future API এ মার্কেট অর্ডার, SL এবং TP অর্ডার প্লেস করে।
    """
    if MOCK_MODE:
        # মক মোডে শুধু প্রিন্ট করা হবে
        print(f"\n--- 🤖 MOCK ORDER PLACED (CoinDCX) ---")
        print(f"  Symbol: {pair}, Side: {side}, Volume: {volume}, SL: {sl_price:.4f}, TP: {tp_price:.4f}")
        print("---------------------------------------")
        return {"orderId": "MOCK_ORDER_12345", "status": "new"} 

    # CoinDCX Future এর জন্য মার্কেট আইডি (যেমন SOLUSDTF)
    market_id = get_coindcx_future_market_id(pair)
    if not market_id:
        print(f"❌ ERROR: Future Market ID not found for {pair}")
        return None

    try:
        # 1. সেট লেভারেজ (CoinDCX এ ফিউচার অর্ডারের জন্য লেভারেজ Payload এর অংশ হতে পারে)
        # এখানে লেভারেজ সেট করার জন্য আলাদা একটি API কল করা যেতে পারে।

        # 2. মার্কেট অর্ডার প্লেস করা (Main Entry)
        main_order_payload = {
            "symbol": market_id,
            "side": side.lower(), # 'buy' বা 'sell'
            "order_type": "market",
            "quantity": round(volume, 4), 
            "leverage": LEVERAGE
        }
        order_response = make_coindcx_request("/exchange/v1/futures/order/create", main_order_payload)

        if 'error' in order_response or order_response.get('status') == 'rejected':
            raise Exception(f"Main Order failed: {order_response}")

        order_id = order_response.get('orderId', 'N/A')

        # 3. SL এবং TP অর্ডার প্লেস করা (OCO বা আলাদা Stop/Limit)
        # CoinDCX Future API-এ SL/TP সাধারণত পজিশন খোলার পর আলাদাভাবে প্লেস করতে হয়।

        # SL অর্ডার (Stop Limit/Stop Market)
        sl_side = 'sell' if side.upper() == 'LONG' else 'buy'
        sl_payload = {
            "symbol": market_id,
            "side": sl_side,
            "order_type": "stop_limit", # Stop Limit ব্যবহার করা হলো
            "quantity": round(volume, 4),
            "stop_price": round(sl_price, 4),
            "price": round(sl_price * 0.99, 4) if sl_side == 'buy' else round(sl_price * 1.01, 4), # Trigger price থেকে সামান্য দূরত্ব
            "leverage": LEVERAGE
        }
        sl_response = make_coindcx_request("/exchange/v1/futures/order/create", sl_payload)

        # TP অর্ডার (Limit)
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


        message = f"✅ LIVE ORDER SUCCESS | {pair} {side.upper()}\nEntry ID: {order_id}\nSL ID: {sl_response.get('orderId', 'N/A')} | TP ID: {tp_response.get('orderId', 'N/A')}"
        send_telegram_message(message)
        print(message)

        return order_response

    except Exception as e:
        error_message = f"❌ LIVE ORDER FAILED on {pair}: {e}"
        send_telegram_message(error_message)
        print(error_message)
        return None

# ===============================
# 🚀 অ্যালগো মেইন লুপ 
# ===============================

def run_algo_monitor_loop():
    global ACTIVE_ORDERS
    last_heartbeat_time = datetime.now() - timedelta(hours=2) 

    print(f"\n--- 🤖 CoinDCX 24/7 Algo Monitor Started ---")

    while True:
        current_time = datetime.now()

        if current_time - last_heartbeat_time >= timedelta(hours=1):
            status_msg = f"❤️ Algo Heartbeat - {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            status_msg += f"Monitor is running smoothly. Active Orders: {len(ACTIVE_ORDERS)}"
            send_telegram_message(status_msg)
            last_heartbeat_time = current_time

        start_date = (current_time - pd.Timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = current_time.strftime('%Y-%m-%d')

        for cdcx_pair in COINDCX_PAIRS:
            if cdcx_pair in ACTIVE_ORDERS and ACTIVE_ORDERS[cdcx_pair]['status'] == 'open':
                print(f"[{cdcx_pair}] Skipping check: Order already active.")
                continue

            yf_ticker = YF_TICKERS[cdcx_pair]

            # 1. ডেটা ফ্রেচ ও ইন্ডিকেটর গণনা
            try:
                df_dir = yf.download(yf_ticker, interval=TF_DIR, start=start_date, end=end_date, progress=False, auto_adjust=False).dropna()
                df_entry = yf.download(yf_ticker, interval=TF_ENTRY, start=start_date, end=end_date, progress=False, auto_adjust=False).dropna()
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
                print(f"  ✅ Signal Found: {sig['side'].upper()} @ {sig['entry']:.4f}")

                # 3. পজিশন সাইজিং
                position_value_inr, volume_to_trade = calculate_position_size(sig['entry'], sig['sl'], sig['entry'])

                # 4. লাইভ অর্ডার প্লেসমেন্ট (TP/SL সহ)
                order_response = live_place_order(
                    cdcx_pair, 
                    sig['side'].upper(), 
                    volume_to_trade, 
                    sig['sl'], 
                    sig['tp1']
                )

                if order_response and order_response.get('status') != 'rejected':
                    ACTIVE_ORDERS[cdcx_pair] = {
                        "id": order_response.get('orderId', 'N/A'),
                        "status": "open",
                        "entry": sig['entry'],
                        "sl": sig['sl'],
                        "tp1": sig['tp1']
                    }
            else:
                pass 

        time.sleep(15 * 60) 

# ===============================
# 🚀 মূল এক্সিকিউশন
# ===============================
if __name__ == "__main__":
    try:
        run_algo_monitor_loop()
    except KeyboardInterrupt:
        print("\nMonitor stopped manually.")
    except Exception as e:
        error_msg = f"CRITICAL ERROR: Algo crashed! {e}"
        print(error_msg)
        send_telegram_message(f"🚨 CRASH ALERT 🚨: {error_msg}")
    
