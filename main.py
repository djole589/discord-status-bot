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

# ---- Config ----
USER_TOKEN = os.environ.get("DISCORD_TOKEN")
MY_USER_ID = "705359620763287552"
SELF_PING_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:8080")

# ---- Globals ----
heartbeat_interval = None
current_ws = None
last_replied = {}
sequence = None

# ---- Statusi ----
def get_time_status():
    tz = pytz.timezone("Europe/Belgrade")
    now = datetime.now(tz)
    return f"🕐 CET (UTC+1) — {now.strftime('%H:%M')} Belgrade"

STATUSES = [
    lambda: get_time_status(),
    lambda: "👨‍💻 Programmer | C++ | C# | Python | Java",
    lambda: "🎮 Need game cheats? DM me",
    lambda: "🎮 If you need help building some game dm me",
    lambda: "🕹️ If you want cheats for games dm me",
    lambda: "🛠️ Building something cool...",
    lambda: "🇷🇸 Serbian Nationality",
    lambda: "💀 Yes I'm always online. No I'm not a bot.",
]

STREAMING_NAME = "guns.lol/djole_fg"
STREAMING_URL  = "https://guns.lol/djole_fg"

DM_REPLIES = [
    "hey {name}, im asleep rn, ill reply when i wake up 😴",
    "sleeping bro {name}, i will get back to you when i wake up 🌙",
    "zzz {name}... ill reply in the morning 😴",
]

# ---- Helpers ----
def is_sleeping():
    tz = pytz.timezone("Europe/Belgrade")
    now = datetime.now(tz)
    return 2 <= now.hour < 9

def get_username(user_id):
    try:
        r = requests.get(
            f"https://discord.com/api/v9/users/{user_id}",
            headers={"Authorization": USER_TOKEN},
            timeout=5
        )
        data = r.json()
        return data.get("global_name") or data.get("username") or "bro"
    except Exception:
        return "bro"

def send_dm(channel_id, text):
    try:
        requests.post(
            f"https://discord.com/api/v9/channels/{channel_id}/messages",
            headers={"Authorization": USER_TOKEN, "Content-Type": "application/json"},
            json={"content": text},
            timeout=5
        )
        print(f"[DM] => {text}")
    except Exception as e:
        print(f"[DM Error] {e}")

# ---- Presence ----
def build_presence(status_text):
    return {
        "op": 3,
        "d": {
            "since": None,
            "activities": [
                {
                    "type": 1,
                    "name": STREAMING_NAME,
                    "url": STREAMING_URL,
                },
                {
                    "type": 4,
                    "name": "Custom Status",
                    "state": status_text,
                    "emoji": None
                }
            ],
            "status": "online",
            "afk": False
        }
    }

def update_presence(ws_instance, status_text):
    try:
        ws_instance.send(json.dumps(build_presence(status_text)))
        print(f"[Presence] => {status_text}")
    except Exception as e:
        print(f"[Presence Error] {e}")

# ---- WebSocket ----
def send_heartbeat(ws):
    global sequence
    while True:
        if heartbeat_interval:
            time.sleep(heartbeat_interval / 1000)
            try:
                ws.send(json.dumps({"op": 1, "d": sequence}))
            except Exception:
                break

def on_open(ws):
    print("[WS] Konekcija otvorena")

def on_message(ws, message):
    global heartbeat_interval, current_ws, sequence

    data = json.loads(message)
    op   = data.get("op")
    t    = data.get("t")
    s    = data.get("s")

    if s:
        sequence = s

    if op == 10:
        heartbeat_interval = data["d"]["heartbeat_interval"]
        threading.Thread(target=send_heartbeat, args=(ws,), daemon=True).start()

        ws.send(json.dumps({
            "op": 2,
            "d": {
                "token": USER_TOKEN,
                "properties": {
                    "os": "windows",
                    "browser": "chrome",
                    "device": ""
                },
                "presence": build_presence(get_time_status())["d"]
            }
        }))

    if t == "READY":
        current_ws = ws
        print("[WS] ✅ Konektovan i online!")

    if t == "MESSAGE_CREATE":
        msg       = data.get("d", {})
        author    = msg.get("author", {})
        author_id = author.get("id")
        channel_id = msg.get("channel_id")
        guild_id   = msg.get("guild_id")

        if author.get("bot") or author_id == MY_USER_ID:
            return
        if guild_id is not None:
            return
        if not is_sleeping():
            return

        now = time.time()
        if now - last_replied.get(author_id, 0) < 120:
            return
        last_replied[author_id] = now

        name  = get_username(author_id)
        reply = random.choice(DM_REPLIES).format(name=name)
        send_dm(channel_id, reply)

def on_error(ws, error):
    print(f"[WS Error] {error}")

def on_close(ws, close_status_code, close_msg):
    global current_ws
    current_ws = None
    print(f"[WS] Zatvoren ({close_status_code}), restartujem za 5s...")
    time.sleep(5)
    threading.Thread(target=start_ws, daemon=True).start()

def start_ws():
    ws = websocket.WebSocketApp(
        "wss://gateway.discord.gg/?v=9&encoding=json",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

# ---- Status rotacija ----
def status_changer():
    for fn in itertools.cycle(STATUSES):
        status_text = fn()
        if current_ws:
            update_presence(current_ws, status_text)
        time.sleep(60)

# ---- Self-ping (sprečava Render spin-down) ----
def self_pinger():
    time.sleep(30)
    while True:
        try:
            requests.get(SELF_PING_URL, timeout=10)
            print("[Ping] Self-ping OK")
        except Exception as e:
            print(f"[Ping Error] {e}")
        time.sleep(240)  # svakih 4 minuta

# ---- HTTP server ----
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"[Server] Slusa na portu {port}")
    server.serve_forever()

# ---- Start ----
threading.Thread(target=run_server,     daemon=True).start()
threading.Thread(target=status_changer, daemon=True).start()
threading.Thread(target=self_pinger,    daemon=True).start()
threading.Thread(target=start_ws,       daemon=True).start()

print("🤖 Bot pokrenut | made by Djole_fg")
while True:
    time.sleep(60)
