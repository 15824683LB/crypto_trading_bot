# =========================================================
# RSI + ATR MTF STRATEGY – DELTA EXCHANGE (FULL READY)
# লজিক: 15M RSI | 1:2 (50%), 1:5 (25%), 1:10 (25%) Exit
# =========================================================

import time
from datetime import datetime
import pandas as pd
import ta
import helper_delta as helper

# ===================== CONFIGURATION =====================
instrument = "BTCUSD"
qty = 1                # আপনার ট্রেডিং কোয়ান্টিটি
papertrading = 1        # 0 = PAPER | 1 = LIVE (সতর্কতার সাথে ব্যবহার করুন)
max_trade = 5
timeFrame = 15          # 15 Minute Candle

# RSI Levels
rsi_buy_level = 53
rsi_sell_level = 47

# Risk Reward Settings
rr1, rr2, rr3 = 2.0, 5.0, 10.0

delta_client = helper.create_client()

# ===================== STATE VARIABLES =====================
st = 0                  # 0=None, 1=Long, 2=Short
sl = 0
sl_initial = 0
tp1 = tp2 = tp3 = 0
entry_price = 0
trade_count = 0
last_candle_time = None
partial_1 = False       # For 1:2 exit
partial_2 = False       # For 1:5 exit

# ===================== UTILS =====================
def log(msg, emo="ℹ️"):
    print(f"{emo} [{datetime.now().strftime('%H:%M:%S')}] {msg}")

def get_data(symbol, tf):
    df = helper.getHistorical(symbol, tf, 200)
    if df is None or len(df) < 50: return None
    df.columns = [c.lower() for c in df.columns]
    return df

def place_order(side, order_qty):
    price = float(helper.manualLTP(instrument, delta_client))
    log(f"{side} ORDER | Qty: {order_qty} @ {price}", "🟢" if side=="BUY" else "🔴")
    return helper.placeOrder(instrument, side, order_qty, "MARKET", price, delta_client, papertrading)

# ===================== START =====================
log("STRATEGY STARTED - MTF RSI + ATR 🚀")
log(f"MODE: {'LIVE' if papertrading == 1 else 'PAPER'}")

while True:
    now = datetime.now()
    
    # 🕒 চেক হবে প্রতি ১৫ মিনিট ক্যান্ডেল ক্লোজে
    if now.minute % timeFrame == 0 and now.second <= 2:
        data = get_data(instrument, timeFrame)
        
        if data is not None and data.index[-1] != last_candle_time:
            last_candle_time = data.index[-1]
            
            # Indicators
            rsi = ta.momentum.RSIIndicator(data['close'], 14).rsi().iloc[-2]
            last_low = data['low'].iloc[-2]
            last_high = data['high'].iloc[-2]
            
            curr_price = float(helper.manualLTP(instrument, delta_client))

            # ================= ENTRY LOGIC =================
            if st == 0 and trade_count < max_trade:
                
                # --- LONG ENTRY ---
                if rsi > rsi_buy_level:
                    entry_price = curr_price
                    sl = last_low * (1 - 0.0006)
                    sl_initial = sl
                    risk = entry_price - sl
                    
                    # TP Calculation
                    tp1 = entry_price + (risk * rr1)
                    tp2 = entry_price + (risk * rr2)
                    tp3 = entry_price + (risk * rr3)
                    
                    place_order("BUY", qty)
                    st = 1
                    partial_1 = partial_2 = False
                    trade_count += 1
                    log(f"LONG ENTRY! SL: {round(sl,2)}, TP1: {round(tp1,2)}", "🚀")

                # --- SHORT ENTRY ---
                elif rsi < rsi_sell_level:
                    entry_price = curr_price
                    sl = last_high * (1 + 0.0006)
                    sl_initial = sl
                    risk = sl - entry_price
                    
                    # TP Calculation
                    tp1 = entry_price - (risk * rr1)
                    tp2 = entry_price - (risk * rr2)
                    tp3 = entry_price - (risk * rr3)
                    
                    place_order("SELL", qty)
                    st = 2
                    partial_1 = partial_2 = False
                    trade_count += 1
                    log(f"SHORT ENTRY! SL: {round(sl,2)}, TP1: {round(tp1,2)}", "📉")

        time.sleep(5)

    # ================= EXIT & TRAILING MANAGEMENT =================
    if st != 0:
        try:
            price = float(helper.manualLTP(instrument, delta_client))

            # ------ LONG MANAGEMENT ------
            if st == 1:
                # 1:2 TP - 50% Close & SL to Cost
                if price >= tp1 and not partial_1:
                    place_order("SELL", qty * 0.5)
                    sl = entry_price
                    partial_1 = True
                    log("TP1 HIT (1:2) - 50% Out, SL to Cost 🎯")

                # 1:5 TP - 25% Close & SL to 1:2
                elif price >= tp2 and not partial_2:
                    place_order("SELL", qty * 0.25)
                    sl = tp1
                    partial_2 = True
                    log("TP2 HIT (1:5) - 25% Out, SL to TP1 🎯")

                # 1:10 TP - Final Exit
                elif price >= tp3:
                    place_order("SELL", qty * 0.25)
                    st = 0
                    log("FINAL TP3 HIT (1:10)! Trade Closed 🏆")

                # SL/TSL Check
                elif price <= sl:
                    rem_qty = qty * 0.25 if partial_2 else (qty * 0.5 if partial_1 else qty)
                    place_order("SELL", rem_qty)
                    st = 0
                    log("LONG SL/TSL HIT 🛑")

            # ------ SHORT MANAGEMENT ------
            elif st == 2:
                if price <= tp1 and not partial_1:
                    place_order("BUY", qty * 0.5)
                    sl = entry_price
                    partial_1 = True
                    log("TP1 HIT (1:2) - 50% Out, SL to Cost 🎯")

                elif price <= tp2 and not partial_2:
                    place_order("BUY", qty * 0.25)
                    sl = tp1
                    partial_2 = True
                    log("TP2 HIT (1:5) - 25% Out, SL to TP1 🎯")

                elif price <= tp3:
                    place_order("BUY", qty * 0.25)
                    st = 0
                    log("FINAL TP3 HIT (1:10)! Trade Closed 🏆")

                elif price >= sl:
                    rem_qty = qty * 0.25 if partial_2 else (qty * 0.5 if partial_1 else qty)
                    place_order("BUY", rem_qty)
                    st = 0
                    log("SHORT SL/TSL HIT 🛑")

        except Exception as e:
            log(f"Management Error: {e}", "❌")
            
    time.sleep(1)
    
