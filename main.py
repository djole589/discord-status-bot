import requests
import time
import itertools
import threading
import websocket
import json
import os
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import pytz

USER_TOKEN = os.environ.get("DISCORD_TOKEN")
MY_USER_ID = "705359620763287552"
SPECIAL_USER_ID = "1278856941887684650"
SPECIAL_CHANNEL_ID = "1483260186817724576"

def get_timezone_status():
    tz = pytz.timezone("Europe/Belgrade")
    now = datetime.now(tz)
    return f"🕐 Time Zone: CET (UTC+1) — {now.strftime('%H:%M')}"

STATUSES = [
    lambda: get_timezone_status(),
    lambda: "🕹️ If you want cheats for games dm me",
    lambda: "👨‍💻 Programmer | C++ | C# | Py | Java",
    lambda: "🎮 If you need help building some game dm me",
    lambda: "💕 Taken by Ema ❤️",
]

GENERAL_REPLIES = [
    "hey, im asleep rn, ill reply when i wake up 😴",
    "sleeping bro, i will get back to you when i wake up 🌙",
]

current_status = STATUSES[0]()
last_replied = {}

def is_after_2am():
    tz = pytz.timezone("Europe/Belgrade")
    now = datetime.now(tz)
    return now.hour >= 2 and now.hour < 9

def get_username(user_id):
    r = requests.get(
        f"https://discord.com/api/v9/users/{user_id}",
        headers={"Authorization": USER_TOKEN}
    )
    data = r.json()
    return data.get("global_name") or data.get("username") or "bro"

def send_dm(channel_id, text):
    requests.post(
        f"https://discord.com/api/v9/channels/{channel_id}/messages",
        headers={"Authorization": USER_TOKEN, "Content-Type": "application/json"},
        json={"content": text}
    )
    print(f"Auto-reply => {text}")

def set_status_http(text):
    requests.patch(
        "https://discord.com/api/v9/users/@me/settings",
        headers={"Authorization": USER_TOKEN, "Content-Type": "application/json"},
        json={"status": "online", "custom_status": {"text": text}}
    )
    print(f"Status => {text}")

# ---- WebSocket ----
heartbeat_interval = None

def send_heartbeat(ws):
    while True:
        if heartbeat_interval:
            time.sleep(heartbeat_interval / 1000)
            ws.send(json.dumps({"op": 1, "d": None}))

def on_message(ws, message):
    global heartbeat_interval, current_status
    data = json.loads(message)
    op = data.get("op")
    t = data.get("t")

    if op == 10:
        heartbeat_interval = data["d"]["heartbeat_interval"]
        threading.Thread(target=send_heartbeat, args=(ws,), daemon=True).start()
        ws.send(json.dumps({
            "op": 2,
            "d": {
                "token": USER_TOKEN,
                "properties": {"os": "windows", "browser": "chrome", "device": ""},
                "presence": {
                    "status": "online",
                    "activities": [{"type": 4, "name": "Custom Status", "state": current_status}],
                    "afk": False
                }
            }
        }))
        print("Conected ✅")

    if t == "MESSAGE_CREATE":
        msg = data.get("d", {})
        author = msg.get("author", {})
        author_id = author.get("id")
        channel_id = msg.get("channel_id")
        guild_id = msg.get("guild_id")

        if author.get("bot") or author_id == MY_USER_ID:
            return
        if guild_id is not None:
            return
        if not is_after_2am():
            return

        now = time.time()
        if now - last_replied.get(author_id, 0) < 120:
            return

        last_replied[author_id] = now

        if author_id == SPECIAL_USER_ID:
            send_dm(SPECIAL_CHANNEL_ID, "Hello my love, im asleep rn 😴❤️ ill reply when i wake up!")
        else:
            name = get_username(author_id)
            reply = f"{name}, " + random.choice(GENERAL_REPLIES)
            send_dm(channel_id, reply)

def on_error(ws, error):
    print(f"WS Error: {error}")

def on_close(ws, *args):
    print("WS zatvoren, restartujem...")
    time.sleep(5)
    start_ws()

def start_ws():
    ws = websocket.WebSocketApp(
        "wss://gateway.discord.gg/?v=9&encoding=json",
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

# ---- Status menjač ----
def status_changer():
    global current_status
    for fn in itertools.cycle(STATUSES):
        current_status = fn()
        set_status_http(current_status)
        time.sleep(60)

# ---- Web server za UptimeRobot ----
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot alive!")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
    def log_message(self, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

threading.Thread(target=run_server, daemon=True).start()
threading.Thread(target=status_changer, daemon=True).start()
threading.Thread(target=start_ws, daemon=True).start()

print("Bot is up made by Djole_fg")
while True:
    time.sleep(60)
