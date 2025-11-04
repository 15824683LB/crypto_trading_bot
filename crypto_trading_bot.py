import yfinance as yf
import pandas as pd
import datetime
import requests
import numpy as np

# === Telegram Setup ===
TELEGRAM_TOKEN = "7615583534:AAHaKfWLN7NP83LdmR32i6BfNWqq73nBsAE"
CHAT_ID = "1002689167916"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print("✅ Telegram Alert Sent!")
        else:
            print("⚠️ Telegram Error:", response.text)
    except Exception as e:
        print("⚠️ Telegram Send Failed:", e)

# === Forex Pairs ===
pairs = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "USDCAD=X",
    "NZD/USD": "NZDUSD=X",
    "XAU/USD": "GC=F",
    "XAG/USD": "SI=F",
    "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X"
}

print(f"\n📈 Buy-the-Dip Scanner - Running at {datetime.datetime.utcnow():%Y-%m-%d %H:%M UTC}\n")

summary = []

# === Fetch & Analyze ===
for name, ticker in pairs.items():
    try:
        data = yf.download(ticker, period="30d", interval="1d", progress=False, auto_adjust=False)

        if data.empty:
            print(f"❌ No data for {name}")
            continue

        close = data["Close"]
        high = data["High"]
        low = data["Low"]

        drop_pc = ((high.max() - close.iloc[-1]) / high.max()) * 100

        # === RSI Calculation ===
        delta = close.diff()
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = pd.Series(gain).rolling(window=14).mean()
        avg_loss = pd.Series(loss).rolling(window=14).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = round(rsi.iloc[-1], 2)

        # === ATR (Volatility) ===
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean().iloc[-1]

        # === Buy Signal Logic ===
        signal = "WAIT ⚠️"
        if (drop_pc >= 2) and (current_rsi <= 45):
            signal = "BUY ZONE ✅"
            msg = (
                f"📊 *BUY ALERT!* {name}\n"
                f"Drop: {drop_pc:.2f}% | RSI: {current_rsi}\n"
                f"Current Price: {close.iloc[-1]:.5f}"
            )
            send_telegram_message(msg)

        summary.append([
            name, ticker, str(datetime.date.today()),
            round(close.iloc[-1], 5), round(high.max(), 5),
            round(drop_pc, 2), current_rsi, round(atr, 5), signal
        ])

    except Exception as e:
        print(f"❌ Error fetching {name}: {e}")

# === Summary Table ===
if len(summary) > 0:
    df = pd.DataFrame(summary, columns=["pair", "ticker", "date", "price", "swing_high", "drop_pc", "rsi", "atr", "signal"])
    print(df.to_string(index=False))
else:
    print("⚠️ No valid data received.")
