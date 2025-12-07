# delta_xrp_15m_bot.py
# XRP-PERP (Delta Exchange) | 15m candles | 5x leverage (position sizing logic)
# Strategy core: add_indicators() + detect_signal()
# Exits: TP/SL + 1:1 breakeven then EMA10 trailing (as you wanted)

import os
import time
import json
import hmac
import hashlib
import base64
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

# =========================
# 1) CONFIG (YOUR REQUIREMENTS)
# =========================
CAPITAL = 5000.0          # USDT-equivalent
CAPITAL_USE_PCT = 0.50    # 50% of capital allowed per trade
LEVERAGE = 5              # 5x leverage (used in sizing math)
RISK_PCT = 0.01           # risk % on allowed capital slice

SYMBOL = "XRPUSDT"       # Delta contract (perpetual)
TIMEFRAME = "15m"         # Delta resolution (1m / 5m / 15m / 1h ...)
SLEEP_SECONDS = 60        # main loop sleep

# Strategy params (your original)
EMA_PERIOD = 200
ATR_MULTIPLIER = 2.2
MAX_SL_PCT = 2.5          # max SL distance (as % of entry)
RR_MIN = 2.0              # 1:2 target (TP1)
EMA_TRAIL_PERIOD = 10
LOOKBACK_BARS = 520

ATR_PRICE_FLOOR_PCT = 0.005  # 0.5% floor for SL distance
LIVE_TRADING = True         # set True only after you confirm keys + behavior

# =========================
# 2) ENV CREDENTIALS (SET THESE BEFORE RUN)
# =========================
DELTA_KEY = os.getenv("DELTA_API_KEY", "")
DELTA_SECRET = os.getenv("DELTA_API_SECRET", "")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

DELTA_BASE_URL = "https://api.delta.exchange"
ORDER_CREATE_URL = f"{DELTA_BASE_URL}/v2/orders"
OHLC_URL = f"{DELTA_BASE_URL}/v2/history/candles"  # public candles

# =========================
# 3) UTIL: SAFE TIME + TELEGRAM
# =========================
def now_utc_seconds() -> int:
    """Return a safe 'now' in seconds (guards against accidental future clocks)."""
    t = int(time.time())
    # hard clamp: if system clock is somehow in future (rare), pull back to now
    # (we cannot query a remote time source here, so we keep it conservative)
    return t

def send_telegram(msg: str):
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=15,
        )
    except Exception as e:
        print("Telegram error:", e)

# =========================
# 4) DELTA AUTH (for /v2/orders)
# =========================
def _sign_delta(method: str, path: str, timestamp_ms: str, body: str = "") -> str:
    message = f"{method.upper()}{path}{timestamp_ms}{body}"
def get_klines(symbol="XRP-PERP", timeframe="15m", limit=200):
                    try:
                        end_ts = int(time.time())
                        tf_minutes = int(timeframe.replace("m", ""))
                        start_ts = end_ts - (limit * tf_minutes * 60)

                        url = (
                            f"https://api.delta.exchange/v2/history/candles?"
                            f"symbol={symbol}&resolution={timeframe}&start={start_ts}&end={end_ts}"
                        )

                        r = requests.get(url)
                        data = r.json()

                        # ❗ If API returns no candle data
                        if "result" not in data or not data["result"]:
                            print("❌ ERROR: No candles returned!", data)
                            return None

                        df = pd.DataFrame(data["result"])

                        # Delta API always sends: time, open, high, low, close, volume
                        rename_map = {
                            "open": "Open",
                            "high": "High",
                            "low": "Low",
                            "close": "Close",
                            "volume": "Volume"
                        }

                        df.rename(columns=rename_map, inplace=True)

                        df["time"] = pd.to_datetime(df["time"], unit="s")

                        return df

                    except Exception as e:
                        print("❌ ERROR get_klines:", e)
                        return None
# =========================
# 6) INDICATORS (YOUR ORIGINAL LOGIC)
# =========================
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    dfc = df.copy()

    dfc["ema200"] = dfc["Close"].ewm(span=EMA_PERIOD, adjust=False).mean()
    dfc["ema12"] = dfc["Close"].ewm(span=12, adjust=False).mean()
    dfc["ema26"] = dfc["Close"].ewm(span=26, adjust=False).mean()

    dfc["macd_line"] = dfc["ema12"] - dfc["ema26"]
    dfc["macd_signal"] = dfc["macd_line"].ewm(span=9, adjust=False).mean()

    high_low = dfc["High"] - dfc["Low"]
    high_close = (dfc["High"] - dfc["Close"].shift()).abs()
    low_close = (dfc["Low"] - dfc["Close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    dfc["atr"] = tr.ewm(span=14, adjust=False).mean()

    delta = dfc["Close"].diff()
    gain = (delta.where(delta > 0, 0)).ewm(com=13, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(com=13, adjust=False).mean()
    rs = gain / loss
    dfc["rsi"] = 100 - (100 / (1 + rs))

    dfc["close"] = dfc["Close"]
    return dfc.dropna()

def detect_signal(df_dir_slice: pd.DataFrame, df_entry_slice: pd.DataFrame):
    if len(df_dir_slice) < EMA_PERIOD or len(df_entry_slice) < 14:
        return None

    trend = "bull" if df_dir_slice["close"].iloc[-1] > df_dir_slice["ema200"].iloc[-1] else "bear"

    ob_candles = df_dir_slice.iloc[-5:-1]
    ob_low = ob_candles["Low"].min()
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

    entry = None
    side = None
    sl = None

    if trend == "bull" and macd_bullish and (ob_low <= price <= ob_high) and rsi_val > 55:
        entry = price
        side = "long"
        sl = entry - sl_distance

    if trend == "bear" and macd_bearish and (ob_low <= price <= ob_high) and rsi_val < 45:
        entry = price
        side = "short"
        sl = entry + sl_distance

    if entry is None:
        return None

    sl_pct = abs((entry - sl) / entry * 100)
    if sl_pct > MAX_SL_PCT:
        sl = entry * (1 - MAX_SL_PCT / 100) if side == "long" else entry * (1 + MAX_SL_PCT / 100)

    risk_distance = abs(entry - sl)
    rr = RR_MIN
    tp1 = entry + (risk_distance * rr) if side == "long" else entry - (risk_distance * rr)

    if (side == "long" and (sl >= entry or tp1 <= entry)) or (side == "short" and (sl <= entry or tp1 >= entry)):
        print("❌ Signal Rejected: SL/TP calculation error.")
        return None

    return {"side": side, "entry": entry, "sl": sl, "tp1": tp1, "risk_distance": risk_distance}

def ema10_last(df: pd.DataFrame) -> float:
    return df["Close"].ewm(span=EMA_TRAIL_PERIOD, adjust=False).mean().iloc[-1]

# =========================
# 7) POSITION MANAGER (YOUR EXIT RULES)
# =========================
class PositionManager:
    def __init__(self):
        self.pos = None

    def is_open(self) -> bool:
        return self.pos is not None

    def open(self, signal: dict, qty: float, df: pd.DataFrame):
        entry = float(signal["entry"])
        side = signal["side"]

        atr_from_df = float(df["atr"].iloc[-1]) if "atr" in df.columns else 0.0
        atr_floor = entry * ATR_PRICE_FLOOR_PCT
        sl_dist = max(atr_from_df, atr_floor)

        if side == "long":
            sl = entry - sl_dist
            risk = abs(entry - sl)
            tp = entry + (2.0 * risk)
            rr1 = entry + (1.0 * risk)
        else:
            sl = entry + sl_dist
            risk = abs(entry - sl)
            tp = entry - (2.0 * risk)
            rr1 = entry - (1.0 * risk)

        self.pos = {
            "side": side,
            "entry": entry,
            "qty": qty,
            "sl": sl,
            "tp": tp,
            "rr1": rr1,
            "breakeven_done": False,
            "trail_active": False,
        }

    def update(self, last_price: float, df: pd.DataFrame):
        if self.pos is None:
            return "hold", None

        p = self.pos
        side = p["side"]

        # hard exits
        if side == "long":
            if last_price >= p["tp"]:
                closed = self.pos; self.pos = None; return "close_tp", closed
            if last_price <= p["sl"]:
                closed = self.pos; self.pos = None; return "close_sl", closed
        else:
            if last_price <= p["tp"]:
                closed = self.pos; self.pos = None; return "close_tp", closed
            if last_price >= p["sl"]:
                closed = self.pos; self.pos = None; return "close_sl", closed

        # breakeven + trail enable
        if not p["breakeven_done"]:
            if (side == "long" and last_price >= p["rr1"]) or (side == "short" and last_price <= p["rr1"]):
                p["sl"] = p["entry"]
                p["breakeven_done"] = True
                p["trail_active"] = True

        # EMA10 trailing (after breakeven)
        if p["trail_active"]:
            e10 = float(ema10_last(df))
            if side == "long":
                p["sl"] = max(p["sl"], min(e10, last_price * 0.999))
            else:
                p["sl"] = min(p["sl"], max(e10, last_price * 1.001))

        self.pos = p
        return "hold", p

# =========================
# 8) POSITION SIZE (YOUR RULES)
# =========================
def compute_qty(signal: dict) -> float:
    allowed_capital = CAPITAL * CAPITAL_USE_PCT
    risk_amount = allowed_capital * RISK_PCT
    dist = float(signal.get("risk_distance", 0.0))
    if dist <= 0:
        return 0.0

    raw_qty = (risk_amount / dist) * LEVERAGE
    max_notional = allowed_capital * LEVERAGE
    max_qty = max_notional / float(signal["entry"])
    return max(0.0, min(raw_qty, max_qty))

# =========================
# 9) ORDER EXECUTION (PAPER BY DEFAULT)
# =========================
def send_market_order_delta(side: str, qty: float):
    side = side.lower()
    if side not in ("buy", "sell"):
        raise ValueError("side must be 'buy' or 'sell'")

    payload = {
        "symbol": SYMBOL,              # kept as your current field (if your Delta account expects 'contract', update here)
        "side": side,
        "order_type": "market_order",
        "order_quantity": round(qty, 2),
        "time_in_force": "GTC",
        "is_reduce_only": False,
        "is_post_only": False,
        "limit_price": None,
        "stop_price": None,
    }

    if not LIVE_TRADING:
        print("PAPER ORDER:", payload)
        return {"status": "paper", "payload": payload}

    path = "/v2/orders"
    r = requests.post(ORDER_CREATE_URL, headers=delta_auth_headers("POST", path, payload), json=payload, timeout=25)
    r.raise_for_status()
    return r.json()

def entry_order(side: str, qty: float):
    return send_market_order_delta("buy" if side == "long" else "sell", qty)

def exit_order(side: str, qty: float):
    return send_market_order_delta("sell" if side == "long" else "buy", qty)

# =========================
# 10) MAIN LOOP (CANDLE-BASED)
# =========================
def run():
    pm = PositionManager()
    last_candle_ts = None

    print("=== XRP-PERP DELTA FUTURES BOT (LIVE) ===")
    print(f"SYMBOL: {SYMBOL} | TIMEFRAME: {TIMEFRAME} | LEVERAGE: {LEVERAGE}x | CAPITAL: {CAPITAL} | USE: {CAPITAL_USE_PCT*100:.0f}% per trade")

    while True:
        try:
            end_sec = now_utc_seconds()
            tf_minutes = int(TIMEFRAME.replace("m", ""))
            start_sec = end_sec - (LOOKBACK_BARS * tf_minutes * 60)

            df = get_klines(SYMBOL, TIMEFRAME, LOOKBACK_BARS)
            if df is None or df.empty:
                time.sleep(SLEEP_SECONDS)
                continue

            df = add_indicators(df)
            current_candle_ts = int(df["time"].iloc[-1].timestamp())

            # wait until a new 15m candle closes
            if last_candle_ts is not None and current_candle_ts == last_candle_ts:
                time.sleep(SLEEP_SECONDS)
                continue

            last_candle_ts = current_candle_ts
            last_price = float(df["Close"].iloc[-1])

            # if in position -> manage
            if pm.is_open():
                state, closed = pm.update(last_price, df)

                if state in ("close_tp", "close_sl"):
                    exit_order(closed["side"], closed["qty"])
                    msg_type = "🎯 <b>TP HIT</b>" if state == "close_tp" else "❌ <b>SL HIT</b>"
                    exit_level = closed["tp"] if state == "close_tp" else closed["sl"]
                    send_telegram(
                        f"{msg_type}\n"
                        f"Pair: {SYMBOL}\n"
                        f"Side: {closed['side'].upper()}\n"
                        f"Exit: {last_price:.6f}\n"
                        f"Level: {exit_level:.6f}\n"
                    )

                # optional: notify trailing updates (low noise)
                if pm.is_open() and pm.pos.get("trail_active"):
                    current_sl = pm.pos["sl"]
                    if not hasattr(pm, "_last_sent_sl") or abs(current_sl - getattr(pm, "_last_sent_sl")) > (abs(current_sl) * 0.001):
                        send_telegram(
                            f"📉 <b>Trailing SL Updated</b>\n"
                            f"Pair: {SYMBOL}\n"
                            f"Side: {pm.pos['side'].upper()}\n"
                            f"New SL: {current_sl:.6f}\n"
                            f"Price: {last_price:.6f}\n"
                        )
                        setattr(pm, "_last_sent_sl", current_sl)

            # no position -> look for entry
            else:
                df_dir = df.iloc[-EMA_PERIOD:]
                df_entry = df.iloc[-30:]
                sig = detect_signal(df_dir, df_entry)

                if sig is None:
                    print(datetime.now(timezone.utc).isoformat(), "No signal.")
                else:
                    qty = compute_qty(sig)
                    if qty <= 0:
                        print(datetime.now(timezone.utc).isoformat(), "Signal but qty=0 (skip).")
                    else:
                        sig["entry"] = last_price
                        pm.open(sig, qty, df)
                        entry_order(sig["side"], qty)

                        send_telegram(
                            f"🚀 <b>NEW SIGNAL</b>\n"
                            f"Pair: {SYMBOL}\n"
                            f"TF: {TIMEFRAME}\n"
                            f"Side: {sig['side'].upper()}\n"
                            f"Entry: {pm.pos['entry']:.6f}\n"
                            f"SL: {pm.pos['sl']:.6f}\n"
                            f"TP: {pm.pos['tp']:.6f}\n"
                            f"Leverage: {LEVERAGE}x\n"
                        )

        except Exception as e:
            print(f"ERROR at {datetime.now(timezone.utc).isoformat()}:", e)

        time.sleep(SLEEP_SECONDS)

if __name__ == "__main__":
    if LIVE_TRADING and not (DELTA_KEY and DELTA_SECRET):
        print("!!! FATAL: LIVE_TRADING is True but DELTA_API_KEY / DELTA_API_SECRET is missing.")
    else:
        run()
