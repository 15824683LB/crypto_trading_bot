import yfinance as yf
import pandas as pd
import datetime
import requests

# === Telegram Setup ===
TELEGRAM_TOKEN = "7615583534:AAHaKfWLN7NP83LdmR32i6BfNWqq73nBsAE"
CHAT_ID = "1002689167916"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
        print("✅ Telegram Alert Sent!")
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

print(f"Buy-the-Dip Scanner - Running at {datetime.datetime.utcnow():%Y-%m-%d %H:%M UTC}\n")

summary = []

# === Fetch & Analyze ===
for name, ticker in pairs.items():
    try:
        data = yf.download(ticker, period="14d", interval="1d", progress=False)
        close = data["Close"]
        high = data["High"]
        low = data["Low"]
        drop_pc = ((high.max() - close.iloc[-1]) / high.max()) * 100

        # RSI Calculation
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = round(rsi.iloc[-1], 2)

        # ATR (Volatility)
        tr = high.combine(low, max) - low.combine(close.shift(), min)
        atr = tr.rolling(window=14).mean().iloc[-1]

        # Buy Signal Logic
        signal = "WAIT ⚠️"
        if drop_pc >= 2 and current_rsi <= 45:
            signal = "BUY ZONE ✅"
            msg = f"📊 *BUY ALERT!* {name}\nDrop: {drop_pc:.2f}% | RSI: {current_rsi}\nCurrent Price: {close.iloc[-1]:.5f}"
            send_telegram_message(msg)

        summary.append([name, ticker, str(datetime.date.today()), round(close.iloc[-1], 5),
                        round(high.max(), 5), round(drop_pc, 2), current_rsi, round(atr, 5), signal])
    except Exception as e:
        print(f"❌ Error fetching {name}: {e}")

# === Summary Table ===
df = pd.DataFrame(summary, columns=["pair", "ticker", "date", "price", "swing_high",
                                   "drop_pc", "rsi", "atr", "signal"])
print(df.to_string(index=False))
