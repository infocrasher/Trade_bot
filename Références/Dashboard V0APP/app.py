"""
AlgoTrader Dashboard — Flask application
"""
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# In-memory settings store (replace with DB in production)
_settings: dict = {}


# ── Routes ────────────────────────────────────────────

@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/performance")
def performance():
    return render_template("performance.html")


@app.route("/settings")
def settings():
    return render_template("settings.html")


@app.route("/postmortem")
def postmortem():
    return render_template("postmortem.html")


# ── API ───────────────────────────────────────────────

@app.route("/api/settings/save", methods=["POST"])
def settings_save():
    """Persist a single setting key/value pair."""
    data = request.get_json(silent=True)
    if not data or "key" not in data:
        return jsonify({"ok": False, "error": "Missing key"}), 400

    key   = str(data["key"])
    value = data.get("value")
    _settings[key] = value
    return jsonify({"ok": True, "key": key, "value": value})


@app.route("/api/settings", methods=["GET"])
def settings_get():
    """Return all current settings."""
    return jsonify(_settings)


# ── Dev server ────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5001)
