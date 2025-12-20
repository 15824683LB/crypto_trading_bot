from delta_rest_client import DeltaRestClient
from delta_rest_client import OrderType, TimeInForce
import requests
import pandas as pd
import json
from datetime import datetime, timedelta
import pytz
#pip install delta-rest-client

def load_delta_credentials():
    base_url = 'https://api.india.delta.exchange'
    with open("delta_api_key.txt", 'r') as file:
        api_key = file.read().strip()
    with open("delta_api_secret.txt", 'r') as file:
        api_secret = file.read().strip()
    return api_key, api_secret


def create_client():
    """Create Delta Exchange client"""
    try:
        base_url = 'https://api.india.delta.exchange'
        api_key, api_secret = load_delta_credentials()
        client = DeltaRestClient(base_url=base_url, api_key=api_key, api_secret=api_secret)
        return client
    except Exception as e:
        print(f"❌ Error creating client: {e}")
        return None

def getSymbolList():
    response = requests.get('https://api.india.delta.exchange/v2/products')
    products = response.json()
    data = [{'id': item['id'], 'symbol': item['symbol']} for item in products['result']]
    df = pd.DataFrame(data)
    df.to_csv('products.csv', index=False)
    return df

def manualLTP(symbol, delta_client):
    response = delta_client.get_ticker(symbol)
    return float(response['close']) if response and 'close' in response else -1

def getAssets(delta_client):
    response = delta_client.get_assets()
    result = [{'id': item['id'], 'symbol': item['symbol']} for item in response]
    return result

def findProductId(symbol):
    df = pd.read_csv('products.csv')
    result = df.loc[df['symbol'] == symbol, 'id']
    return result.iloc[0] if not result.empty else None

def getOpenOrders(delta_client):
    orders = delta_client.get_live_orders()
    return orders

def getOrderBook(delta_client, symbol):
    product_id = findProductId(symbol)
    response = delta_client.get_l2_orderbook(product_id)
    return response


def placeOrder(inst ,t_type,qty,order_type,price,delta_client,papertrading=0):
    dt = datetime.now()

    product_id = findProductId(inst)
    print(product_id)
    if(t_type=="BUY"):
        side1='buy'
    elif(t_type=="SELL"):
        side1='sell'

    if(order_type=="MARKET"):
        type1 = OrderType.MARKET
        price = 0
    elif(order_type=="LIMIT"):
        type1 = OrderType.LIMIT

    try:
        if (papertrading == 1):
            order_response = delta_client.place_order(
                product_id=str(product_id),
                size=qty,
                side=side1,
                limit_price=str(price),
                time_in_force = None,
                order_type=type1,
                post_only = "false",
                client_order_id = None
            )
            print(dt.hour,":",dt.minute,":",dt.second ," ==> ", inst , order_response)
            return order_response
        else:
            return 0

    except Exception as e:
        print(dt.hour,":",dt.minute,":",dt.second ," => ", inst , "Failed : {} ".format(e))

def getTodayExpiryDate():
    """Returns today's date in DDMMYY format till 5:30 PM IST, otherwise returns tomorrow's date."""
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    cutoff_time = now.replace(hour=17, minute=30, second=0, microsecond=0)
    expiry_date = now if now < cutoff_time else now + timedelta(days=1)
    return expiry_date.strftime('%d%m%y')

def getTomorrowExpiryDate():
    """Returns tomorrow's date in DDMMYY format till 5:30 PM IST, otherwise returns day after tomorrow's date."""
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    cutoff_time = now.replace(hour=17, minute=30, second=0, microsecond=0)
    expiry_date = now + timedelta(days=1) if now < cutoff_time else now + timedelta(days=2)
    return expiry_date.strftime('%d%m%y')

def getIndexSpot(stock):
    if stock == "BTC":
        name = "BTCUSD"
    elif stock == "ETH":
        name = "ETHUSD"
    return name

def getOptionFormat(stock, intExpiry, strike, ce_pe):
    #BTC, today/tomorrow, strike, CE/PE
    if intExpiry == "today":
        ddmmyy = getTodayExpiryDate()
    elif intExpiry == "tomorrow":
        ddmmyy = getTomorrowExpiryDate()
    return ce_pe[0] + "-" + stock[:3] + "-" + str(strike) + "-" + str(ddmmyy)

def getHistorical(ticker,interval,duration):
    range_from = datetime.today()-timedelta(duration)
    range_to = datetime.today()

    start = int(range_from.timestamp())
    end = int(range_to.timestamp())

    params = {
        'resolution': "1m",
        'symbol': ticker,
        'start': start,
        'end': end
    }

    headers = {
        'Accept': 'application/json'
    }
    response = requests.get('https://api.india.delta.exchange/v2/history/candles', params=params, headers = headers)
    historical_data = response.json()
    #print(historical_data)

    # Create a DataFrame
    df = pd.DataFrame(historical_data['result'])
    df.rename(columns={"time": "Timestamp"}, inplace=True)
    df.sort_values(by="Timestamp", ascending=True, inplace=True)

    # Convert Timestamp to datetime in UTC
    df['Timestamp2'] = pd.to_datetime(df['Timestamp'],unit='s').dt.tz_localize(pytz.utc)

    # Convert Timestamp to IST
    ist = pytz.timezone('Asia/Kolkata')
    df['Timestamp2'] = df['Timestamp2'].dt.tz_convert(ist)

    filtered_df = df.copy()
    filtered_df['datetime2'] = filtered_df['Timestamp2'].copy()
    # Set 'Timestamp2' as the index
    filtered_df.set_index('Timestamp2', inplace=True)
    filtered_df.drop('datetime2', axis=1, inplace=True)
    filtered_df.drop('Timestamp', axis=1, inplace=True)
    filtered_df = filtered_df[['open', 'high', 'low', 'close', 'volume']]

    resampled_df = filtered_df.resample(f'{interval}min', label='left').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })

    print(resampled_df)

    return resampled_df

def getQuotes(instrument):
    try:
        with open("delta_data.json", "r") as f:
            result = json.load(f)
        return float(result.get(instrument, None))
    except (FileNotFoundError, ValueError, TypeError):
        return -1

