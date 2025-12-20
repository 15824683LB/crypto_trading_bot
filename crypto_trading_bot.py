import os
import time
import pandas as pd
import ta
from datetime import datetime
from dotenv import load_dotenv
from delta_rest_client import DeltaRestClient
from flask import Flask
from threading import Thread

# ===================== KEEP ALIVE SERVER =====================
# Render-এ ২৪/৭ সচল রাখার জন্য ছোট ওয়েব সার্ভার
app = Flask('')

@app.route('/')
def home():
    return "Bot is running 24/7!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ===================== CONFIGURATION =====================
load_dotenv()
API_KEY = os.getenv("DELTA_API_KEY")
API_SECRET = os.getenv("DELTA_API_SECRET")
BASE_URL = 'https://api.india.delta.exchange'

instrument = "BTCUSD"
qty = 1                
papertrading = 1 # 1 = LIVE TRADE        
max_trade = 5
timeFrame = 15          

rsi_buy_level = 53
rsi_sell_level = 47
rr1, rr2, rr3 = 2.0, 5.0, 10.0

# ===================== STATE VARIABLES =====================
st, sl, sl_initial = 0, 0, 0
tp1, tp2, tp3 = 0, 0, 0
entry_price, trade_count = 0, 0
last_candle_time = None
partial_1, partial_2 = False, False

# ===================== INITIALIZE =====================
client = DeltaRestClient(base_url=BASE_URL, api_key=API_KEY, api_secret=API_SECRET)

def log(msg, emo="ℹ️"):
    print(f"{emo} [{datetime.now().strftime('%H:%M:%S')}] {msg}")

def get_data(symbol, tf):
    # আপনার helper_delta.py ফাইলটি অবশ্যই এক ফোল্ডারে থাকতে হবে
    import helper_delta as helper
    df = helper.getHistorical(symbol, tf, 200)
    if df is None or len(df) < 50: return None
    df.columns = [c.lower() for c in df.columns]
    return df

def place_order(side, order_qty):
    ticker = client.get_ticker(instrument)
    price = float(ticker.get('mark_price'))
    log(f"{side.upper()} Order | Qty: {order_qty} @ {price}", "🔔")
    return client.place_order(
        product_id=ticker['product_id'],
        size=order_qty,
        side=side.lower(),
        order_type="market"
    )

# ===================== STRATEGY ENGINE =====================
def start_strategy():
    global st, sl, sl_initial, tp1, tp2, tp3, entry_price, trade_count, last_candle_time, partial_1, partial_2
    
    log("STRATEGY ENGINE ACTIVATED 🚀")
    
    while True:
        now = datetime.now()
        
        # ১৫ মিনিট অন্তর চেক
        if now.minute % timeFrame == 0 and now.second <= 2:
            data = get_data(instrument, timeFrame)
            
            if data is not None and data.index[-1] != last_candle_time:
                last_candle_time = data.index[-1]
                
                rsi = ta.momentum.RSIIndicator(data['close'], 14).rsi().iloc[-2]
                last_low, last_high = data['low'].iloc[-2], data['high'].iloc[-2]
                ticker = client.get_ticker(instrument)
                curr_price = float(ticker.get('mark_price'))

                if st == 0 and trade_count < max_trade:
                    # LONG ENTRY
                    if rsi > rsi_buy_level:
                        entry_price = curr_price
                        sl = last_low * (1 - 0.0006)
                        sl_initial = sl
                        risk = entry_price - sl
                        tp1, tp2, tp3 = entry_price+(risk*rr1), entry_price+(risk*rr2), entry_price+(risk*rr3)
                        place_order("buy", qty)
                        st, partial_1, partial_2 = 1, False, False
                        trade_count += 1
                        log(f"LONG ENTRY! SL: {round(sl,2)}, TP1: {round(tp1,2)}", "📈")

                    # SHORT ENTRY
                    elif rsi < rsi_sell_level:
                        entry_price = curr_price
                        sl = last_high * (1 + 0.0006)
                        sl_initial = sl
                        risk = sl - entry_price
                        tp1, tp2, tp3 = entry_price-(risk*rr1), entry_price-(risk*rr2), entry_price-(risk*rr3)
                        place_order("sell", qty)
                        st, partial_1, partial_2 = 2, False, False
                        trade_count += 1
                        log(f"SHORT ENTRY! SL: {round(sl,2)}, TP1: {round(tp1,2)}", "📉")

        # পজিশন ম্যানেজমেন্ট (SL, TP1, TP2, TP3)
        if st != 0:
            try:
                ticker = client.get_ticker(instrument)
                price = float(ticker.get('mark_price'))

                if st == 1: # Long
                    if price >= tp1 and not partial_1:
                        place_order("sell", qty * 0.5)
                        sl, partial_1 = entry_price, True
                        log("TP1 HIT (1:2) - 50% Out, SL to Entry 🎯")
                    elif price >= tp2 and not partial_2:
                        place_order("sell", qty * 0.25)
                        sl, partial_2 = tp1, True
                        log("TP2 HIT (1:5) - 25% Out, SL to TP1 🎯")
                    elif price >= tp3:
                        place_market_order("sell", qty * 0.25)
                        st = 0
                        log("FINAL TP3 HIT! 🏆")
                    elif price <= sl:
                        rem = qty * 0.25 if partial_2 else (qty * 0.5 if partial_1 else qty)
                        place_order("sell", rem)
                        st = 0
                        log("LONG SL/TSL HIT 🛑")

                elif st == 2: # Short
                    if price <= tp1 and not partial_1:
                        place_order("buy", qty * 0.5)
                        sl, partial_1 = entry_price, True
                        log("TP1 HIT (1:2) - 50% Out, SL to Entry 🎯")
                    elif price <= tp2 and not partial_2:
                        place_order("buy", qty * 0.25)
                        sl, partial_2 = tp1, True
                        log("TP2 HIT (1:5) - 25% Out, SL to TP1 🎯")
                    elif price <= tp3:
                        place_market_order("buy", qty * 0.25)
                        st = 0
                        log("FINAL TP3 HIT! 🏆")
                    elif price >= sl:
                        rem = qty * 0.25 if partial_2 else (qty * 0.5 if partial_1 else qty)
                        place_order("buy", rem)
                        st = 0
                        log("SHORT SL/TSL HIT 🛑")
            except Exception as e:
                log(f"Error: {e}", "❌")
        
        time.sleep(1)

if __name__ == "__main__":
    keep_alive() # ওয়েব সার্ভার চালু করবে
    start_strategy() # ট্রেডিং লজিক চালু করবে
    
