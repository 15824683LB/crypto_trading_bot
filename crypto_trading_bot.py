from flask import Flask
import threading
from delta_login import login
from strategy import run_strategy
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Trading Bot is Running"

def start_bot():
    client = login()
    run_strategy(client)

if __name__ == "__main__":
    # Start bot in background thread
    threading.Thread(target=start_bot, daemon=True).start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
