from flask import Flask
import threading
import time
import os

from delta_login import login
from strategy import run_strategy

# ================= FLASK APP =================
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Trading Bot is Running"

@app.route("/health")
def health():
    return {"status": "ok"}

# ================= BOT THREAD =================
def start_bot():
    while True:
        try:
            print("🔐 Logging into Delta Exchange...")
            client = login()
            print("🚀 Strategy started")
            run_strategy(client)

        except Exception as e:
            print(f"❌ Bot error: {e}")
            print("🔄 Restarting bot in 10 seconds...")
            time.sleep(10)

# ================= HEARTBEAT =================
def heartbeat():
    while True:
        print("💓 Bot heartbeat... alive")
        time.sleep(300)  # 5 minutes

# ================= MAIN =================
if __name__ == "__main__":
    # Start bot thread
    threading.Thread(target=start_bot, daemon=True).start()

    # Heartbeat log thread
    threading.Thread(target=heartbeat, daemon=True).start()

    # Start Flask server (Render needs open port)
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
