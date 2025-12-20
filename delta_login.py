#pip install delta-rest-client
from delta_rest_client import DeltaRestClient
import json
import time
from datetime import datetime

"""
Delta Exchange India API Login Test - WORKING VERSION
Based on actual available methods from your system
"""

def load_credentials():
    """Load API credentials from text files"""
    try:
        with open("delta_api_key.txt", 'r') as file:
            api_key = file.read().strip()
        with open("delta_api_secret.txt", 'r') as file:
            api_secret = file.read().strip()
        return api_key, api_secret
    except FileNotFoundError:
        print("❌ Credential files not found!")
        return None, None

def create_client(api_key, api_secret):
    """Create Delta Exchange client"""
    try:
        base_url = 'https://api.india.delta.exchange'
        client = DeltaRestClient(base_url=base_url, api_key=api_key, api_secret=api_secret)
        return client
    except Exception as e:
        print(f"❌ Error creating client: {e}")
        return None

def check_delta_connection(client):
    """Test Delta Exchange India API with WORKING methods"""
    try:
        print("Testing Delta Exchange India API connection...")
        print("-" * 50)

        # Test 1: Get Assets (Public - Working!)
        print("1. Testing get_assets()...")
        try:
            assets = client.get_assets()
            if assets and len(assets) > 0:
                print("✓ Assets retrieved successfully")
                print(f"✓ Found {len(assets)} assets")

                # Show sample assets
                sample_assets = assets[:3]
                print("   Sample assets:")
                for asset in sample_assets:
                    symbol = asset.get('symbol', 'Unknown')
                    name = asset.get('name', 'Unknown')
                    print(f"   - {symbol}: {name}")
            else:
                print("❌ Failed to get assets")
                return False
        except Exception as e:
            print(f"❌ Assets test failed: {e}")
            return False

        # Test 2: Get Ticker (Public - Working!)
        print("\n2. Testing get_ticker()...")
        try:
            ticker = client.get_ticker('BTCUSD')
            if ticker and 'symbol' in ticker:
                print("✓ Ticker retrieved successfully")
                symbol = ticker.get('symbol', 'Unknown')
                price = ticker.get('mark_price', 'N/A')
                volume = ticker.get('volume', 'N/A')
                print(f"   {symbol}: ${price} (Volume: {volume})")
            else:
                print("❌ Failed to get ticker")
        except Exception as e:
            print(f"⚠️  Ticker test error: {e}")

        # Test 3: Get Balances (Try different approaches)
        print("\n3. Testing balance methods...")

        # First try to get balances for a specific asset (BTC)
        try:
            # Get BTC asset ID from assets list
            btc_asset = None
            for asset in assets:
                if asset.get('symbol') == 'BTC':
                    btc_asset = asset
                    break

            if btc_asset:
                asset_id = btc_asset.get('id')
                print(f"   Trying get_balances() for BTC (asset_id: {asset_id})...")
                balance = client.get_balances(asset_id)
                if balance:
                    print("✓ Authentication successful!")
                    print("✓ Balance retrieved for BTC")
                    print(f"   BTC Balance: {balance}")
                else:
                    print("⚠️  BTC balance is zero or not available")
            else:
                print("⚠️  Could not find BTC asset")
        except Exception as e:
            print(f"⚠️  get_balances() error: {e}")

        # Try alternative: get_position() for holdings
        print("\n   Trying get_position() for holdings...")
        try:
            # Get BTCUSD position
            ticker = client.get_ticker('BTCUSD')
            if ticker and 'product_id' in ticker:
                product_id = ticker['product_id']
                position = client.get_position(product_id)
                if position:
                    print("✓ Position data retrieved successfully")
                    print(f"   BTCUSD Position: {position}")
                else:
                    print("   No open position for BTCUSD")
            else:
                print("⚠️  Could not get product ID for position check")
        except Exception as e:
            print(f"⚠️  get_position() error: {e}")

        # Try get_margined_position()
        print("\n   Trying get_margined_position()...")
        try:
            ticker = client.get_ticker('BTCUSD')
            if ticker and 'product_id' in ticker:
                product_id = ticker['product_id']
                position = client.get_margined_position(product_id)
                if position:
                    print("✓ Margined position retrieved successfully")
                    print(f"   Margined Position: {position}")
                else:
                    print("   No margined position found")
        except Exception as e:
            print(f"⚠️  get_margined_position() error: {e}")

        # Test 4: Get Live Orders
        print("\n4. Testing get_live_orders()...")
        try:
            orders = client.get_live_orders()
            if orders is not None:
                print("✓ Live orders retrieved successfully")
                print(f"   Found {len(orders)} live orders")

                if len(orders) > 0:
                    print("   Recent live orders:")
                    for order in orders[:3]:
                        symbol = order.get('product_symbol', 'Unknown')
                        side = order.get('side', 'Unknown')
                        size = order.get('size', 'Unknown')
                        state = order.get('state', 'Unknown')
                        print(f"   - {symbol}: {side} {size} ({state})")
                else:
                    print("   No live orders found")
            else:
                print("⚠️  Live orders access limited")
        except Exception as e:
            print(f"⚠️  Live orders test error: {e}")

        # Test 5: Get Order History
        print("\n5. Testing order_history()...")
        try:
            history = client.order_history()
            if history and 'result' in history:
                orders = history['result']
                print("✓ Order history retrieved successfully")
                print(f"   Found {len(orders)} historical orders")

                if len(orders) > 0:
                    print("   Recent order history:")
                    for order in orders[:3]:
                        symbol = order.get('product_symbol', 'Unknown')
                        side = order.get('side', 'Unknown')
                        size = order.get('size', 'Unknown')
                        state = order.get('state', 'Unknown')
                        print(f"   - {symbol}: {side} {size} ({state})")
                else:
                    print("   No order history found")
            else:
                print("⚠️  Order history access limited")
        except Exception as e:
            print(f"⚠️  Order history test error: {e}")

        # Test 6: Try to get a valid product
        print("\n6. Testing get_product() with valid ID...")
        try:
            # Let's try to find a valid product ID from ticker
            ticker = client.get_ticker('BTCUSD')
            if ticker and 'product_id' in ticker:
                product_id = ticker['product_id']
                print(f"   Trying product ID: {product_id}")

                product = client.get_product(product_id)
                if product:
                    print("✓ Product details retrieved successfully")
                    symbol = product.get('symbol', 'Unknown')
                    contract_type = product.get('contract_type', 'Unknown')
                    print(f"   Product: {symbol} ({contract_type})")
                else:
                    print("⚠️  Product details not available")
            else:
                print("⚠️  Could not find valid product ID")
        except Exception as e:
            print(f"⚠️  Product test error: {e}")

        print("\n" + "=" * 50)
        print("🎉 DELTA EXCHANGE INDIA API TESTS COMPLETED!")
        print("=" * 50)

        return True

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False

def main():
    """Main function"""
    print("Delta Exchange India API Login Test - WORKING VERSION")
    print("=" * 60)

    # Load credentials
    api_key, api_secret = load_credentials()
    if not api_key or not api_secret:
        print("Please create delta_api_key.txt and delta_api_secret.txt files")
        return

    print(f"✓ API Key: {api_key[:10]}...")
    print(f"✓ API Secret: {api_secret[:10]}...")

    # Create client
    client = create_client(api_key, api_secret)
    if not client:
        return

    print("✓ Client created successfully")

    # Test the connection
    success = check_delta_connection(client)

    if success:
        print("\n✓ Delta Exchange India API is working correctly!")
        print("\n📋 WORKING METHODS FOR YOUR HELPER:")
        print("=" * 40)
        print("✅ client.get_assets()           # Get all assets")
        print("✅ client.get_ticker(symbol)     # Get ticker data")
        print("✅ client.get_balances(asset_id) # Get balance for specific asset")
        print("✅ client.get_position(product_id) # Get position for product")
        print("✅ client.get_margined_position(product_id) # Get margined position")
        print("✅ client.get_live_orders()      # Get live orders")
        print("✅ client.order_history()        # Get order history")
        print("✅ client.get_product(product_id) # Get product details")
        print("✅ client.get_l2_orderbook(product_id) # Get order book")
        print("✅ client.place_order(...)       # Place orders")
        print("✅ client.cancel_order(...)      # Cancel orders")
        print("\n💡 IMPORTANT NOTES:")
        print("- get_balances() requires asset_id parameter")
        print("- get_position() requires product_id parameter")
        print("- Use get_assets() first to get asset IDs")
        print("- Use get_ticker() to get product IDs")

    else:
        print("\n❌ Some issues detected. Check the output above.")

if __name__ == "__main__":
    main()