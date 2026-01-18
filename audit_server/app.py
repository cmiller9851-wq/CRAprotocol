# audit_server/app.py
from flask import Flask, request, jsonify
from pathlib import Path
import json

app = Flask(__name__)
AUDIT_ROOT = Path("./audit_logs")

@app.route("/audit/run", methods=["GET"])
def run_audit():
    model_id = request.args.get("model_id")
    if not model_id:
        return jsonify({"error": "model_id required"}), 400

    # locate latest log for that model
    logs = sorted(AUDIT_ROOT.glob(f"*_{model_id}_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        return jsonify({"error": "no logs found"}), 404

    latest = logs[0]
    with open(latest) as f:
        data = json.load(f)

    # compute a simple integrity score (e.g., proportion of successful events)
    total = len(data["payload"].get("events", []))
    success = sum(1 for e in data["payload"].get("events", []) if e["status"] == "ok")
    score = success / total if total else 0

    return jsonify({
        "audit_hash": latest.stem,
        "model_id": model_id,
        "integrity_score": round(score, 3),
        "timestamp": data["timestamp"]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
