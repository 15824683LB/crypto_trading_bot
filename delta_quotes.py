import time
import json
import helper_delta as helper
from datetime import datetime


##############################################
#                   INPUT's                  #
##############################################

# Initialize Delta Exchange client
with open("delta_api_key.txt", 'r') as file:
    api_key = file.read().strip()
with open("delta_api_secret.txt", 'r') as file:
    api_secret = file.read().strip()

client = helper.create_client()
if not client:
    print("❌ Failed to create Delta Exchange client. Check your credential files.")
    exit()

print("✓ Delta Exchange client created successfully")

# Define instrument lists
instrumentList = []

##############################################
#              MAJOR CRYPTOCURRENCIES        #
##############################################

# Top cryptocurrencies available on Delta Exchange India
major_cryptos = [
    'BTCUSD',     # Bitcoin USD
    'ETHUSD',     # Ethereum USD
    'ADAUSD',     # Cardano USD
    'SOLUSDT',    # Solana USDT
    'DOTUSD',     # Polkadot USD
    'AVAXUSD',    # Avalanche USD
    'XRPUSD',
]

##############################################
#              BUILD INSTRUMENT LIST         #
##############################################

# Combine all categories and remove duplicates
instrumentList = sorted(list(set(major_cryptos)))

print("BELOW IS THE COMPLETE INSTRUMENT LIST")
print(instrumentList)

##############################################
#              PRICE FETCHING LOOP           #
##############################################

print("!! Started delta_quotes.py !!")

while(True):
    try:
        # Get tickers for our symbols from Delta Exchange
        result = {}

        for symbol in instrumentList:
            try:
                # Get ticker data for each symbol
                ticker = client.get_ticker(symbol)
                if ticker and 'mark_price' in ticker:
                    result[symbol] = float(ticker['mark_price'])
                else:
                    result[symbol] = 0.0  # Set to 0 if not found or no price

                # Small delay to avoid rate limits
                time.sleep(0.1)

            except Exception as e:
                print(f"Error getting ticker for {symbol}: {e}")
                result[symbol] = 0.0  # Set to 0 if error

        print(result)

        # Write to a JSON file
        with open("delta_data.json", "w") as f:
            json.dump(result, f)
            print("updated json at " + time.strftime("%Y-%m-%d %H:%M:%S"))

    except Exception as e:
        print(f"Error fetching prices: {e}")

    time.sleep(5)