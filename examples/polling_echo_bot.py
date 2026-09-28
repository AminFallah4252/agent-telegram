#!/usr/bin/env python3
"""
Lightweight Polling Echo Bot Example
------------------------------------
Runs a self-contained polling loop using the cached project token with zero dependencies.
"""

import json
import os
import sys
import time
import urllib.request
from pathlib import Path


def load_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        return token.strip()
    root = Path(__file__).resolve().parent.parent
    cache_path = root / ".agent" / "telegram_bot.json"
    if cache_path.exists():
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        token = data.get("profiles", {}).get("default", {}).get("token")
        if token:
            return token.strip()
    raise RuntimeError("Telegram bot token not found in .agent/telegram_bot.json or environment")


def api_request(token: str, method: str, params: dict = None) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(params).encode("utf-8") if params else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=35) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    token = load_token()
    me = api_request(token, "getMe")["result"]
    print(f"🤖 Connected as @{me['username']} ({me['first_name']})")
    print("📡 Polling for updates (Ctrl+C to stop)...")

    offset = None
    while True:
        try:
            params = {"timeout": 30}
            if offset:
                params["offset"] = offset
            res = api_request(token, "getUpdates", params)
            updates = res.get("result", [])
            for u in updates:
                offset = u["update_id"] + 1
                msg = u.get("message")
                if not msg:
                    continue
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")
                user_name = msg.get("from", {}).get("first_name", "Friend")

                if text == "/start":
                    reply = f"👋 Hello <b>{user_name}</b>! Send me any text and I will echo it back."
                elif text:
                    reply = f"Echo: {text}"
                else:
                    reply = "Received media/attachment."

                api_request(token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": reply,
                    "parse_mode": "HTML"
                })
        except KeyboardInterrupt:
            print("\n🛑 Polling stopped.")
            break
        except Exception as e:
            print(f"Polling warning: {e}", file=sys.stderr)
            time.sleep(2)


if __name__ == "__main__":
    main()
