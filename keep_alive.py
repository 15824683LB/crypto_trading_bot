import threading
from flask import Flask

# ---------------- FLASK APP ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Crypto Trading Bot is Running"

def run_flask():
    # Render gives PORT automatically
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# ---------------- MAIN ----------------
if __name__ == "__main__":
    # Start Flask server in background
    threading.Thread(target=run_flask).start()

    # Start your trading bot logic
    print("🚀 Trading bot started")
    main()   # তোমার existing main() function
