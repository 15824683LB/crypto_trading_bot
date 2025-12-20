# delta_rest_client.py
# Render Compatible Delta Exchange Client

import time
import hmac
import hashlib
import requests
import json
from enum import Enum


# ================= ENUMS =================
class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class TimeInForce(str, Enum):
    GTC = "gtc"      # Good Till Cancel
    IOC = "ioc"      # Immediate Or Cancel
    FOK = "fok"      # Fill Or Kill


# ================= CLIENT =================
class DeltaRestClient:
    def __init__(self, api_key, api_secret, base_url="https://api.delta.exchange"):
        self.api_key = api_key
        self.api_secret = api_secret.encode()
        self.base_url = base_url

    def _headers(self, method, path, payload=""):
        timestamp = str(int(time.time()))
        message = method + timestamp + path + payload
        signature = hmac.new(
            self.api_secret, message.encode(), hashlib.sha256
        ).hexdigest()

        return {
            "api-key": self.api_key,
            "timestamp": timestamp,
            "signature": signature,
            "Content-Type": "application/json",
        }

    def get(self, path):
        url = self.base_url + path
        headers = self._headers("GET", path)
        return requests.get(url, headers=headers, timeout=10).json()

    def post(self, path, data):
        payload = json.dumps(data)
        url = self.base_url + path
        headers = self._headers("POST", path, payload)
        return requests.post(
            url, headers=headers, data=payload, timeout=10
        ).json()
