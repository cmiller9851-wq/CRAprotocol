from flask import Flask
app = Flask(__name__)

@app.route("/")
def home():
    return "<h1>CRAprotocol LIVE — 0618 Fibonacci cadence active</h1><p>Deployed from iPhone. The ledger walks.</p>"

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
