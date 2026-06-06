import requests
import time
import threading
import websocket
import json
import os
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import pytz

# ---- Config ----
TOKEN    = os.environ.get("DISCORD_TOKEN", "")
MY_ID    = "705359620763287552"
SELF_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:10000")

# ---- State ----
ws_global          = None
heartbeat_interval = None
sequence           = None
last_replied       = {}
status_index       = 0

# ---- Statusi ----
def belgrade_time():
    tz  = pytz.timezone("Europe/Belgrade")
    now = datetime.now(tz)
    return f"🕐 {now.strftime('%H:%M')} — Belgrade"

STATUSES = [
    belgrade_time,
    lambda: "👨‍💻 Programmer | C++ | C# | Python | Java",
    lambda: "🎮 Need game cheats? DM me",
    lambda: "🎮 If you need help building some game dm me",
    lambda: "🕹️ If you want cheats for games dm me",
    lambda: "🛠️ Building something cool...",
    lambda: "🇷🇸 Serbian Nationality",
    lambda: "💀 Yes I'm always online. No I'm not a bot.",
]

DM_REPLIES = [
    "hey {name}, im asleep rn, ill reply when i wake up 😴",
    "sleeping bro {name}, ill get back to you when i wake up 🌙",
    "zzz {name}... ill reply in the morning 😴",
]

# ---- Helpers ----
def is_sleeping():
    tz  = pytz.timezone("Europe/Belgrade")
    now = datetime.now(tz)
    return 2 <= now.hour < 9

def get_username(user_id):
    try:
        r = requests.get(
            f"https://discord.com/api/v9/users/{user_id}",
            headers={"Authorization": TOKEN},
            timeout=5
        )
        d = r.json()
        return d.get("global_name") or d.get("username") or "bro"
    except:
        return "bro"

def send_dm(channel_id, text):
    try:
        requests.post(
            f"https://discord.com/api/v9/channels/{channel_id}/messages",
            headers={"Authorization": TOKEN, "Content-Type": "application/json"},
            json={"content": text},
            timeout=5
        )
        print(f"[DM] {text}")
    except Exception as e:
        print(f"[DM Error] {e}")

# ---- Custom status preko HTTP API (ovo zaista menja status) ----
def set_custom_status(text):
    try:
        r = requests.patch(
            "https://discord.com/api/v9/users/@me/settings",
            headers={"Authorization": TOKEN, "Content-Type": "application/json"},
            json={"custom_status": {"text": text, "emoji_name": None}},
            timeout=5
        )
        if r.status_code == 200:
            print(f"[Status OK] {text}")
        else:
            print(f"[Status Error] {r.status_code} {r.text}")
    except Exception as e:
        print(f"[Status Exception] {e}")

# ---- Presence WS (drzi online + streaming) ----
def make_presence(status_text):
    return {
        "op": 3,
        "d": {
            "since": None,
            "activities": [
                {
                    "type": 1,
                    "name": "guns.lol/djole_fg",
                    "url": "https://guns.lol/djole_fg"
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

def send_ws_presence(status_text):
    global ws_global
    if ws_global:
        try:
            ws_global.send(json.dumps(make_presence(status_text)))
        except Exception as e:
            print(f"[WS Presence Error] {e}")

# ---- Status loop — menja i preko API i preko WS ----
def status_loop():
    global status_index
    time.sleep(15)
    while True:
        fn          = STATUSES[status_index % len(STATUSES)]
        status_text = fn()
        set_custom_status(status_text)
        send_ws_presence(status_text)
        status_index += 1
        time.sleep(60)

# ---- Heartbeat ----
def heartbeat_loop(ws):
    global sequence
    while True:
        if not heartbeat_interval:
            time.sleep(1)
            continue
        time.sleep(heartbeat_interval / 1000)
        try:
            ws.send(json.dumps({"op": 1, "d": sequence}))
        except:
            break

# ---- Self ping ----
def ping_loop():
    time.sleep(60)
    while True:
        try:
            requests.get(SELF_URL, timeout=10)
            print("[Ping] OK")
        except Exception as e:
            print(f"[Ping Error] {e}")
        time.sleep(4 * 60)

# ---- WS callbacks ----
def on_open(ws):
    print("[WS] Otvorena konekcija")

def on_message(ws, message):
    global heartbeat_interval, ws_global, sequence

    data = json.loads(message)
    op   = data.get("op")
    t    = data.get("t")
    s    = data.get("s")

    if s:
        sequence = s

    if op == 10:
        heartbeat_interval = data["d"]["heartbeat_interval"]
        threading.Thread(target=heartbeat_loop, args=(ws,), daemon=True).start()
        ws.send(json.dumps({
            "op": 2,
            "d": {
                "token": TOKEN,
                "properties": {
                    "os": "windows",
                    "browser": "chrome",
                    "device": ""
                },
                "presence": make_presence(belgrade_time())["d"]
            }
        }))

    if t == "READY":
        ws_global = ws
        print("[WS] Konektovan!")

    if t == "MESSAGE_CREATE":
        msg        = data.get("d", {})
        author     = msg.get("author", {})
        author_id  = author.get("id")
        channel_id = msg.get("channel_id")
        guild_id   = msg.get("guild_id")

        if author.get("bot") or author_id == MY_ID or guild_id is not None:
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

def on_close(ws, code, msg):
    global ws_global, heartbeat_interval
    ws_global          = None
    heartbeat_interval = None
    print(f"[WS] Zatvoren ({code}), restart za 5s...")
    time.sleep(5)
    start_ws()

def start_ws():
    ws = websocket.WebSocketApp(
        "wss://gateway.discord.gg/?v=9&encoding=json",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever(ping_interval=30, ping_timeout=10)

# ---- HTTP server ----
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"alive")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
    def log_message(self, *args):
        pass

def run_server():
    port   = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"[Server] Port {port}")
    server.serve_forever()

# ---- Start ----
print("🤖 Bot pokrenut!")
threading.Thread(target=run_server,  daemon=True).start()
threading.Thread(target=status_loop, daemon=True).start()
threading.Thread(target=ping_loop,   daemon=True).start()
start_ws()
