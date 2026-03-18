import requests
import time
import itertools
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
from datetime import datetime
import pytz

USER_TOKEN = os.environ.get("DISCORD_TOKEN")

def get_timezone_status():
    tz = pytz.timezone("Europe/Belgrade")
    now = datetime.now(tz)
    return f"🕐 Time Zone: CET (UTC+1) — {now.strftime('%H:%M')}"

STATUSES = [
    lambda: {"text": get_timezone_status(), "emoji_name": "clock1"},
    lambda: {"text": "🕹️ If you want cheats for game dm me", "emoji_name": "joystick"},
    lambda: {"text": "👨‍💻 Programmer | C++ | C# | Py | Java", "emoji_name": "computer"},
    lambda: {"text": "🎮 Intense Gamer Mode ON 😤🔥", "emoji_name": "video_game"},
    lambda: {"text": "💕 Taken by Ema ❤️", "emoji_name": "heart"},
]

HEADERS = {
    "Authorization": USER_TOKEN,
    "Content-Type": "application/json"
}

def set_status(text, emoji_name=None):
    payload = {
        "status": "online",
        "custom_status": {
            "text": text,
            "emoji_name": emoji_name
        }
    }
    r = requests.patch(
        "https://discord.com/api/v9/users/@me/settings",
        headers=HEADERS,
        json=payload
    )
    print(f"[{r.status_code}] => {text}")

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

print("Bot pokrenut 🚀")
for status_fn in itertools.cycle(STATUSES):
    s = status_fn()
    set_status(s["text"], s.get("emoji_name"))
    time.sleep(60)
```

**`requirements.txt`**
```
requests
pytz
