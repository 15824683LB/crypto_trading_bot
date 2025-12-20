# ==========================================================
# Delta Exchange India - Login Module (Render Compatible)
# ==========================================================
# pip install delta-rest-client
# ==========================================================

from delta_rest_client import DeltaRestClient
import os

# ==========================================================
# LOGIN FUNCTION
# ==========================================================
def login():
    """
    Create and return Delta Exchange client
    Credentials loaded from ENV variables (Render compatible)
    """

    # Load ENV credentials
    api_key = os.getenv("DELTA_API_KEY")
    api_secret = os.getenv("DELTA_API_SECRET")

    if not api_key or not api_secret:
        raise Exception(
            "❌ ENV ERROR: DELTA_API_KEY / DELTA_API_SECRET not set"
        )

    # Delta Exchange India base URL
    base_url = "https://api.india.delta.exchange"

    # Create client
    client = DeltaRestClient(
        base_url=base_url,
        api_key=api_key,
        api_secret=api_secret
    )

    print("✅ Delta Exchange Login Successful")
    return client
