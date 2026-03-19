import requests
import time
import itertools
import threading
import websocket
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import pytz

USER_TOKEN = os.environ.get("DISCORD_TOKEN")

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

status_cycle = itertools.cycle(STATUSES)
current_status = STATUSES[0]()

def set_status_http(text):
    requests.patch(
        "https://discord.com/api/v9/users/@me/settings",
        headers={"Authorization": USER_TOKEN, "Content-Type": "application/json"},
        json={"status": "online", "custom_status": {"text": text}}
    )
    print(f"Status => {text}")

# ---- WebSocket da drži online ----
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

    if op == 10:  # Hello
        heartbeat_interval = data["d"]["heartbeat_interval"]
        threading.Thread(target=send_heartbeat, args=(ws,), daemon=True).start()
        # Identify
        ws.send(json.dumps({
            "op": 2,
            "d": {
                "token": USER_TOKEN,
                "properties": {"os": "windows", "browser": "chrome", "device": ""},
                "presence": {
                    "status": "online",
                    "activities": [{
                        "type": 4,
                        "name": "Custom Status",
                        "state": current_status
                    }],
                    "afk": False
                }
            }
        }))
        print("Konekcija uspostavljena! Online ✅")

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
    def log_message(self, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

threading.Thread(target=run_server, daemon=True).start()
threading.Thread(target=status_changer, daemon=True).start()
threading.Thread(target=start_ws, daemon=True).start()

print("Bot pokrenut! 🚀")
while True:
    time.sleep(60)

requests
pytz
websocket-client
