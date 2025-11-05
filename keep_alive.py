from flask import Flask
import threading

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Swing Bot is Running!"

def run():
    app.run(host='0.0.0.0', port=10000)

# === Keep Alive ===
threading.Thread(target=run).start()
