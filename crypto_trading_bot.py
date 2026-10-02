import ccxt
import time
import pandas as pd
import numpy as np
from telegram import Bot

# --- CONFIGURATION ---
TELEGRAM_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'  # Apnar Bot Token ekhane din
CHAT_ID = 'YOUR_TELEGRAM_CHAT_ID'           # Apnar Chat ID ekhane din
bot = Bot(token=TELEGRAM_TOKEN)

def get_exchange():
    # Prothome CoinDCX try korbe, kono error hole Binance-e fallback korbe
    try:
        print("Initializing CoinDCX...")
        ex = ccxt.coindcx({'enableRateLimit': True})
        ex.load_markets()
        return ex, "CoinDCX"
    except Exception as e:
        print(f"CoinDCX initialization failed: {e}. Falling back to Binance.")
        ex = ccxt.binance({'enableRateLimit': True})
        ex.load_markets()
        return ex, "Binance"

exchange, exchange_name = get_exchange()
print(f"Using exchange: {exchange_name}")

def calculate_bollinger_bands(closes, length=20, std_dev=2):
    df = pd.DataFrame({'close': closes})
    sma = df['close'].rolling(window=length).mean()
    std = df['close'].rolling(window=length).std()
    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)
    return upper_band, lower_band, sma

def check_parallel_bands(upper, lower, threshold=0.003):
    widths = (upper - lower) / lower
    recent_widths = widths.iloc[-4:]
    if recent_widths.mean() < threshold and recent_widths.std() < 0.001:
        return True
    return False

def scan_market():
    global exchange, exchange_name
    try:
        print(f"Scanning {exchange_name} market for Bollinger Band breakout/breakdown...")
        try:
            tickers = exchange.fetch_tickers()
        except Exception as ticker_err:
            print(f"Ticker fetch error on {exchange_name}: {ticker_err}. Switching to Binance fallback.")
            exchange = ccxt.binance({'enableRateLimit': True})
            exchange.load_markets()
            exchange_name = "Binance"
            tickers = exchange.fetch_tickers()

        # Valid USDT/INR pairs filtering and sorting by percentage
        valid_tickers = {symbol: data for symbol, data in tickers.items() if ('/USDT' in symbol or '/INR' in symbol) and data.get('percentage') is not None}
        sorted_tickers = sorted(valid_tickers.items(), key=lambda x: x[1]['percentage'], reverse=True)
        
        # Top 20 Gainers and Top 20 Losers
        top_gainers = sorted_tickers[:20]
        top_losers = sorted_tickers[-20:]
        
        alerts = []

        # 1. Top Gainers check (Buy Setup)
        for symbol, data in top_gainers:
            try:
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=35)
                if len(ohlcv) < 30: continue
                closes = pd.Series([x[4] for x in ohlcv])
                
                upper, lower, sma = calculate_bollinger_bands(closes)
                
                if check_parallel_bands(upper, lower):
                    current_price = closes.iloc[-1]
                    prev_price = closes.iloc[-2]
                    prev_upper = upper.iloc[-2]
                    curr_upper = upper.iloc[-1]
                    
                    if prev_price <= prev_upper and current_price > curr_upper:
                        high_val = max([x[2] for x in ohlcv[-3:]])
                        low_val = min([x[3] for x in ohlcv[-3:]])
                        msg = (
                            f"🚀 *{exchange_name}: TOP GAINER BREAKOUT (BUY)*\n"
                            f"• Coin: `{symbol}`\n"
                            f"• Price: `{current_price}`\n"
                            f"• Strategy: 5M Parallel BB Breakout\n"
                            f"• Entry (High): `{high_val}`\n"
                            f"• Stop Loss (Low): `{low_val}`"
                        )
                        alerts.append(msg)
            except Exception as e:
                continue

        # 2. Top Losers check (Short Setup)
        for symbol, data in top_losers:
            try:
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=35)
                if len(ohlcv) < 30: continue
                closes = pd.Series([x[4] for x in ohlcv])
                
                upper, lower, sma = calculate_bollinger_bands(closes)
                
                if check_parallel_bands(upper, lower):
                    current_price = closes.iloc[-1]
                    prev_price = closes.iloc[-2]
                    prev_lower = lower.iloc[-2]
                    curr_lower = lower.iloc[-1]
                    
                    if prev_price >= prev_lower and current_price < curr_lower:
                        high_val = max([x[2] for x in ohlcv[-3:]])
                        low_val = min([x[3] for x in ohlcv[-3:]])
                        msg = (
                            f"🔻 *{exchange_name}: TOP LOSER BREAKDOWN (SHORT)*\n"
                            f"• Coin: `{symbol}`\n"
                            f"• Price: `{current_price}`\n"
                            f"• Strategy: 5M Parallel BB Breakdown\n"
                            f"• Entry (Low): `{low_val}`\n"
                            f"• Stop Loss (High): `{high_val}`"
                        )
                        alerts.append(msg)
            except Exception as e:
                continue

        # Send alerts via Telegram
        for alert in alerts:
            bot.send_message(chat_id=CHAT_ID, text=alert, parse_mode='Markdown')
            time.sleep(1)

    except Exception as e:
        print(f"Scanner Loop Error: {e}")

if __name__ == "__main__":
    print("Bollinger Band Telegram Scanner with Fallback Started...")
    while True:
        scan_market()
        time.sleep(300) # Every 5 minutes scan
