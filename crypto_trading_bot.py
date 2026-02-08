# ===============================
# NIFTY OPTION SIGNAL BOT
# TradingView Data → Python Bot → Telegram
# ===============================

from flask import Flask, request
import pandas as pd
import requests
from datetime import datetime
import os

# ===============================
# CONFIG
# ===============================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

QTY_PER_LOT = 65
LOTS = 2
MAX_TRADES_PER_DAY = 2

EXIT_TIME = "15:15"   # future use

# ===============================
# APP INIT
# ===============================

app = Flask(__name__)

data = []
trades_today = 0
active_trade = None
first_trade_result = None   # "PROFIT" / "LOSS"

# ===============================
# TELEGRAM FUNCTION
# ===============================

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg
    })

# ===============================
# INDICATORS
# ===============================

def bollinger_band(df, length=20, mult=2):
    df["MB"] = df["close"].rolling(length).mean()
    df["STD"] = df["close"].rolling(length).std()
    df["UB"] = df["MB"] + mult * df["STD"]
    df["LB"] = df["MB"] - mult * df["STD"]
    return df

def heikin_ashi(df):
    ha = df.copy()
    ha["HA_Close"] = (df["open"] + df["high"] + df["low"] + df["close"]) / 4

    ha_open = [(df["open"].iloc[0] + df["close"].iloc[0]) / 2]
    for i in range(1, len(df)):
        ha_open.append((ha_open[i-1] + ha["HA_Close"].iloc[i-1]) / 2)

    ha["HA_Open"] = ha_open
    ha["HA_High"] = ha[["HA_Open", "HA_Close", "high"]].max(axis=1)
    ha["HA_Low"] = ha[["HA_Open", "HA_Close", "low"]].min(axis=1)

    return ha

# ===============================
# TRADE CONTROL
# ===============================

def can_trade():
    global trades_today, active_trade, first_trade_result
    if trades_today >= MAX_TRADES_PER_DAY:
        return False
    if active_trade is not None:
        return False
    if first_trade_result == "PROFIT":
        return False
    return True

# ===============================
# WEBHOOK (TradingView → Bot)
# ===============================

@app.route("/webhook", methods=["POST"])
def webhook():
    global data, trades_today, active_trade

    candle = request.json
    data.append(candle)

    df = pd.DataFrame(data)

    if len(df) < 25:
        return "OK"

    df = bollinger_band(df)
    df = heikin_ashi(df)

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # ===============================
    # CE LOGIC
    # BB Upper + HA Red + Low Break
    # ===============================

    if can_trade():
        if (
            prev["HA_Close"] < prev["HA_Open"] and
            prev["high"] >= prev["UB"] and
            last["low"] < prev["low"]
        ):
            trades_today += 1
            active_trade = {
                "side": "CE",
                "entry": last["close"],
                "sl": prev["high"]
            }

            send_telegram(
                f"🔴 CE ENTRY\n"
                f"Entry: {last['close']:.2f}\n"
                f"SL: {prev['high']:.2f}\n"
                f"Qty: {LOTS} × {QTY_PER_LOT}"
            )

    # ===============================
    # PE LOGIC
    # BB Lower + HA Green + High Break
    # ===============================

    if can_trade():
        if (
            prev["HA_Close"] > prev["HA_Open"] and
            prev["low"] <= prev["LB"] and
            last["high"] > prev["high"]
        ):
            trades_today += 1
            active_trade = {
                "side": "PE",
                "entry": last["close"],
                "sl": prev["low"]
            }

            send_telegram(
                f"🟢 PE ENTRY\n"
                f"Entry: {last['close']:.2f}\n"
                f"SL: {prev['low']:.2f}\n"
                f"Qty: {LOTS} × {QTY_PER_LOT}"
            )

    return "OK"

# ===============================
# RUN SERVER
# ===============================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000)
