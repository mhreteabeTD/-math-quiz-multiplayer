import os
import json
import random
import itertools
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_sock import Sock

app = Flask(__name__, static_folder="static")
sock = Sock(app)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GAME_URL = os.environ.get("GAME_URL", "")

# ---------------------------------------------------------------------------
# Puzzle generation
# ---------------------------------------------------------------------------

def can_make(target, numbers):
    """Return True if target can be made from numbers using +,-,*,/ ."""
    if len(numbers) == 1:
        return numbers[0] == target
    for i in range(len(numbers)):
        for j in range(len(numbers)):
            if i == j:
                continue
            rest = [numbers[k] for k in range(len(numbers)) if k != i and k != j]
            a, b = numbers[i], numbers[j]
            candidates = [a + b, a - b, b - a, a * b]
            if b != 0:
                candidates.append(a / b)
            if a != 0:
                candidates.append(b / a)
            for c in candidates:
                if can_make(target, rest + [c]):
                    return True
    return False


def generate_puzzle():
    """Generate a guaranteed-solvable puzzle with whole-number division."""
    for _ in range(1000):
        numbers = [random.randint(1, 9) for _ in range(4)]
        target = random.randint(10, 99)
        if can_make(target, [float(n) for n in numbers]):
            return {"target": target, "numbers": numbers}
    # Fallback: a trivially solvable puzzle
    a, b, c, d = 2, 3, 4, 5
    return {"target": a + b + c + d, "numbers": [a, b, c, d]}


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ---------------------------------------------------------------------------
# Telegram webhook
# ---------------------------------------------------------------------------

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if chat_id and text == "/start":
        _send_start_message(chat_id)

    return jsonify({"ok": True})


def _send_start_message(chat_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": chat_id,
        "text": "Welcome to Make a Number! 🎯\nTap below to play:",
        "reply_markup": {
            "inline_keyboard": [[{
                "text": "🎮 Play now",
                "web_app": {"url": GAME_URL}
            }]]
        }
    })


# ---------------------------------------------------------------------------
# Setup route — registers the webhook
# ---------------------------------------------------------------------------

@app.route("/setup")
def setup():
    if not BOT_TOKEN or not GAME_URL:
        return "BOT_TOKEN or GAME_URL not set", 500
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    resp = requests.post(url, json={"url": f"{GAME_URL}/webhook"})
    return jsonify(resp.json())


# ---------------------------------------------------------------------------
# Puzzle API
# ---------------------------------------------------------------------------

@app.route("/puzzle")
def puzzle():
    return jsonify(generate_puzzle())


# ---------------------------------------------------------------------------
# WebSocket — multiplayer matchmaking (placeholder, expanded later)
# ---------------------------------------------------------------------------

waiting_players = []


@sock.route("/ws")
def ws_handler(ws):
    user_id = None
    try:
        raw = ws.receive()
        data = json.loads(raw)
        user_id = data.get("user_id")
        username = data.get("username", "Player")

        waiting_players.append({"ws": ws, "user_id": user_id, "username": username})

        if len(waiting_players) >= 2:
            p1 = waiting_players.pop(0)
            p2 = waiting_players.pop(0)
            puzzle = generate_puzzle()

            for player, opponent in [(p1, p2), (p2, p1)]:
                player["ws"].send(json.dumps({
                    "type": "match_found",
                    "puzzle": puzzle,
                    "opponent": opponent["username"]
                }))

            # Keep connections alive until one closes
            while True:
                msg = ws.receive()
                if msg is None:
                    break
                # relay to opponent
                other = p2 if ws is p1["ws"] else p1
                try:
                    other["ws"].send(msg)
                except Exception:
                    break
        else:
            ws.send(json.dumps({"type": "waiting"}))
            # Hold connection open
            while True:
                msg = ws.receive()
                if msg is None:
                    break

    except Exception as e:
        print(f"WS error: {e}")
    finally:
        # Clean up waiting list if still there
        global waiting_players
        waiting_players = [p for p in waiting_players if p.get("user_id") != user_id]


if __name__ == "__main__":
    app.run(debug=True)
