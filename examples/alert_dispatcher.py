#!/usr/bin/env python3
"""
Operational Alert Dispatcher Example
------------------------------------
Dispatches system status alerts, deployment notifications, or monitoring pings
to a Telegram channel, group, or admin chat using the cached bot token.
"""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path


def load_token(profile: str = "default") -> str:
    # 1. Environment
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        return token.strip()
    
    # 2. Project Cache
    root = Path(__file__).resolve().parent.parent
    cache_path = root / ".agent" / "telegram_bot.json"
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            token = data.get("profiles", {}).get(profile, {}).get("token")
            if token:
                return token.strip()
        except Exception:
            pass

    raise RuntimeError("Telegram token not configured. Run 'python scripts/telegram_cli.py auth set --token <TOKEN>'")


def dispatch_alert(chat_id: str, title: str, message: str, level: str = "INFO", thread_id: int = None) -> bool:
    token = load_token()
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    icons = {
        "INFO": "ℹ️",
        "SUCCESS": "✅",
        "WARNING": "⚠️",
        "CRITICAL": "🚨"
    }
    icon = icons.get(level.upper(), "📢")

    html_text = f"{icon} <b>{title}</b>\n\n{message}\n\n<i>Time: {os.uname().nodename if hasattr(os, 'uname') else 'host'}</i>"

    payload = {
        "chat_id": chat_id,
        "text": html_text,
        "parse_mode": "HTML"
    }
    if thread_id:
        payload["message_thread_id"] = thread_id

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res.get("ok", False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dispatch operational alert to Telegram")
    parser.add_argument("--chat-id", required=True, help="Target chat or channel ID")
    parser.add_argument("--title", required=True, help="Alert headline")
    parser.add_argument("--message", required=True, help="Detailed message body")
    parser.add_argument("--level", default="INFO", choices=["INFO", "SUCCESS", "WARNING", "CRITICAL"])
    parser.add_argument("--thread-id", type=int, help="Forum topic thread ID")
    args = parser.parse_args()

    try:
        ok = dispatch_alert(args.chat_id, args.title, args.message, args.level, args.thread_id)
        if ok:
            print("✅ Alert dispatched successfully.")
            sys.exit(0)
        else:
            print("❌ Failed to dispatch alert.", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
