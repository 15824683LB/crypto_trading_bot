# pip install delta-rest-client
from delta_rest_client import DeltaRestClient
import json
import time
from datetime import datetime
import os

"""
Delta Exchange India API Login Test - ENV VERSION
Render / Cloud Compatible
"""

# ================= ENV CREDENTIALS =================
def load_credentials():
    """Load API credentials from ENV variables (Render compatible)"""
    api_key = os.getenv("DELTA_API_KEY")
    api_secret = os.getenv("DELTA_API_SECRET")

    if not api_key or not api_secret:
        print("❌ ENV variables not found!")
        print("Please set DELTA_API_KEY and DELTA_API_SECRET in Render")
        return None, None

    return api_key, api_secret


# ================= CLIENT =================
def create_client(api_key, api_secret):
    """Create Delta Exchange client"""
    try:
        base_url = "https://api.india.delta.exchange"
        client = DeltaRestClient(
            base_url=base_url,
            api_key=api_key,
            api_secret=api_secret
        )
        return client
    except Exception as e:
        print(f"❌ Error creating client: {e}")
        return None


# ================= CONNECTION TEST =================
def check_delta_connection(client):
    try:
        print("🚀 Testing Delta Exchange India API connection...")
        print("-" * 50)

        # 1️⃣ Assets
        print("1. get_assets()")
        assets = client.get_assets()
        print(f"✓ Assets found: {len(assets)}")

        # 2️⃣ Ticker
        print("\n2. get_ticker(BTCUSD)")
        ticker = client.get_ticker("BTCUSD")
        print(f"✓ Price: {ticker.get('mark_price')}")

        # 3️⃣ Balance (BTC)
        print("\n3. get_balances(BTC)")
        btc_asset = next(a for a in assets if a["symbol"] == "BTC")
        balance = client.get_balances(btc_asset["id"])
        print(f"✓ BTC Balance: {balance}")

        # 4️⃣ Position
        print("\n4. get_position(BTCUSD)")
        product_id = ticker["product_id"]
        position = client.get_position(product_id)
        print(f"✓ Position: {position}")

        # 5️⃣ Live Orders
        print("\n5. get_live_orders()")
        orders = client.get_live_orders()
        print(f"✓ Live orders: {len(orders)}")

        # 6️⃣ Order History
        print("\n6. order_history()")
        history = client.order_history()
        print(f"✓ History fetched")

        print("\n🎉 ALL TESTS PASSED")
        return True

    except Exception as e:
        print(f"❌ Error during API test: {e}")
        return False


# ================= MAIN =================
def main():
    print("Delta Exchange India API Test (ENV VERSION)")
    print("=" * 60)

    api_key, api_secret = load_credentials()
    if not api_key:
        return

    print("✓ ENV credentials loaded")

    client = create_client(api_key, api_secret)
    if not client:
        return

    print("✓ Client created")

    check_delta_connection(client)


if __name__ == "__main__":
    main()
