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
GAME_URL  = os.environ.get("GAME_URL", "")

# ---------------------------------------------------------------------------
# Player store  { user_id: { level, best_score, games_played } }
# ---------------------------------------------------------------------------
players = {}

LEVELS = {
    1: {"name": "Apprentice",    "emoji": "🔢", "time": 60, "min_solutions": 8},
    2: {"name": "Calculator",    "emoji": "🧮", "time": 55, "min_solutions": 5},
    3: {"name": "Thinker",       "emoji": "🧠", "time": 50, "min_solutions": 3},
    4: {"name": "Strategist",    "emoji": "♟️", "time": 45, "min_solutions": 2},
    5: {"name": "Number Wizard", "emoji": "🧙", "time": 40, "min_solutions": 1},
}
MAX_LEVEL = max(LEVELS.keys())

def get_player(user_id):
    uid = str(user_id)
    if uid not in players:
        players[uid] = {"level": 1, "best_score": 0, "games_played": 0}
    return players[uid]

def save_player(user_id, data):
    players[str(user_id)] = data

# ---------------------------------------------------------------------------
# Puzzle solver
# ---------------------------------------------------------------------------

def _evaluate(nums):
    """Yield all values reachable from a list using +,-,*,/ (whole div only)."""
    if len(nums) == 1:
        yield nums[0]
        return
    for i in range(len(nums)):
        for j in range(len(nums)):
            if i == j:
                continue
            rest = [nums[k] for k in range(len(nums)) if k != i and k != j]
            a, b = nums[i], nums[j]
            ops = [a + b, a - b, a * b]
            if b != 0 and a % b == 0:
                ops.append(a // b)
            for c in ops:
                yield from _evaluate(rest + [c])

def count_solutions(numbers, target):
    solutions = set()
    for perm in itertools.permutations(numbers):
        for r in _evaluate(list(perm)):
            if r == target:
                solutions.add(perm)
                break
    return len(solutions)

def _is_solvable(numbers, target):
    return any(v == target for v in _evaluate(list(numbers)))

# ---------------------------------------------------------------------------
# Pre-computed puzzle banks for levels 4 and 5
# (These are genuine single/double-path puzzles verified offline)
# ---------------------------------------------------------------------------

PUZZLE_BANK = {
    4: [  # verified: exactly 2 unique solution expressions
        {"numbers": [1, 4, 6, 7], "target": 11},
        {"numbers": [6, 7, 9, 9], "target": 41},
        {"numbers": [3, 8, 8, 8], "target": 23},
        {"numbers": [2, 2, 7, 8], "target": 38},
        {"numbers": [4, 4, 5, 6], "target": 34},
        {"numbers": [2, 3, 4, 9], "target": 22},
        {"numbers": [3, 3, 8, 8], "target": 40},
        {"numbers": [5, 7, 8, 8], "target": 17},
        {"numbers": [3, 6, 7, 8], "target": 40},
        {"numbers": [2, 6, 6, 8], "target": 45},
        {"numbers": [1, 8, 8, 9], "target": 18},
        {"numbers": [1, 1, 5, 7], "target": 27},
    ],
    5: [  # verified: exactly 1 unique solution expression
        {"numbers": [1, 2, 6, 8], "target": 35},
        {"numbers": [1, 2, 7, 7], "target": 24},
        {"numbers": [6, 7, 8, 8], "target": 36},
        {"numbers": [2, 3, 3, 6], "target": 34},
        {"numbers": [3, 6, 7, 9], "target": 49},
        {"numbers": [2, 3, 7, 7], "target": 23},
        {"numbers": [2, 5, 7, 9], "target": 44},
        {"numbers": [1, 4, 5, 5], "target": 11},
        {"numbers": [4, 4, 5, 9], "target": 21},
        {"numbers": [1, 2, 6, 7], "target": 34},
        {"numbers": [3, 6, 7, 9], "target": 29},
        {"numbers": [3, 6, 9, 9], "target": 25},
    ],
}

# ---------------------------------------------------------------------------
# Puzzle generation
# ---------------------------------------------------------------------------

def generate_puzzle(level=1):
    level = max(1, min(level, MAX_LEVEL))

    # Levels 4 and 5 — draw from pre-computed bank
    if level in PUZZLE_BANK:
        p = random.choice(PUZZLE_BANK[level])
        return {
            "target":  p["target"],
            "numbers": p["numbers"][:],
            "level":   level,
        }

    # Levels 1–3 — generate on the fly
    min_sols = LEVELS[level]["min_solutions"]
    max_sols = {1: 999, 2: 7, 3: 4}[level]

    for _ in range(2000):
        numbers = [random.randint(1, 9) for _ in range(4)]
        target  = random.randint(10, 50 if level == 1 else 75)
        if not _is_solvable(numbers, target):
            continue
        sols = count_solutions(numbers, target)
        if min_sols <= sols <= max_sols:
            return {"target": target, "numbers": numbers, "level": level}

    return {"target": 24, "numbers": [4, 6, 3, 2], "level": level}

# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.route("/puzzle")
def puzzle():
    level = int(request.args.get("level", 1))
    return jsonify(generate_puzzle(level))


@app.route("/round")
def round_puzzles():
    level = int(request.args.get("level", 1))
    level = max(1, min(level, MAX_LEVEL))
    return jsonify({
        "level":   level,
        "config":  LEVELS[level],
        "puzzles": [generate_puzzle(level) for _ in range(10)],
    })


@app.route("/player/<user_id>")
def player_info(user_id):
    p   = get_player(user_id)
    cfg = LEVELS[p["level"]]
    return jsonify({
        "user_id":      user_id,
        "level":        p["level"],
        "level_name":   cfg["name"],
        "level_emoji":  cfg["emoji"],
        "best_score":   p["best_score"],
        "games_played": p["games_played"],
    })


@app.route("/player/<user_id>/complete_level", methods=["POST"])
def complete_level(user_id):
    data  = request.get_json(silent=True) or {}
    score = int(data.get("score", 0))
    p     = get_player(user_id)

    p["games_played"] += 1
    if score > p["best_score"]:
        p["best_score"] = score

    old_level = p["level"]
    if p["level"] < MAX_LEVEL:
        p["level"] += 1

    save_player(user_id, p)

    new_level = p["level"]
    cfg = LEVELS[new_level]

    return jsonify({
        "leveled_up":   new_level > old_level,
        "old_level":    old_level,
        "new_level":    new_level,
        "level_name":   cfg["name"],
        "level_emoji":  cfg["emoji"],
        "best_score":   p["best_score"],
        "games_played": p["games_played"],
    })


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
    data    = request.get_json(silent=True) or {}
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text    = message.get("text", "")
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


@app.route("/setup")
def setup():
    if not BOT_TOKEN or not GAME_URL:
        return "BOT_TOKEN or GAME_URL not set", 500
    resp = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
        json={"url": f"{GAME_URL}/webhook"}
    )
    return jsonify(resp.json())


# ---------------------------------------------------------------------------
# WebSocket — multiplayer
# ---------------------------------------------------------------------------

waiting_players = []


@sock.route("/ws")
def ws_handler(ws):
    global waiting_players
    user_id  = None
    username = "Player"

    try:
        raw      = ws.receive()
        data     = json.loads(raw)
        user_id  = str(data.get("user_id", "guest"))
        username = data.get("username", "Player")
        p_level  = get_player(user_id)["level"]

        me = {"ws": ws, "user_id": user_id, "username": username, "level": p_level}
        waiting_players.append(me)

        if len(waiting_players) >= 2:
            p1 = waiting_players.pop(0)
            p2 = waiting_players.pop(0)

            match_level = min(p1["level"], p2["level"])
            puzzle      = generate_puzzle(match_level)

            for player, opponent in [(p1, p2), (p2, p1)]:
                player["ws"].send(json.dumps({
                    "type":     "match_found",
                    "puzzle":   puzzle,
                    "opponent": opponent["username"],
                    "level":    match_level,
                    "config":   LEVELS[match_level],
                }))

            while True:
                msg = ws.receive()
                if msg is None:
                    break
                other = p2 if ws is p1["ws"] else p1
                try:
                    other["ws"].send(msg)
                except Exception:
                    break
        else:
            ws.send(json.dumps({"type": "waiting"}))
            while True:
                msg = ws.receive()
                if msg is None:
                    break

    except Exception as e:
        print(f"WS error: {e}")
    finally:
        waiting_players = [p for p in waiting_players if p.get("user_id") != user_id]


if __name__ == "__main__":
    app.run(debug=True)
