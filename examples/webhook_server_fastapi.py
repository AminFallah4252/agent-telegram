#!/usr/bin/env python3
"""
Production Webhook Server Example with FastAPI
----------------------------------------------
Receives Telegram updates securely using the X-Telegram-Bot-Api-Secret-Token header.
"""

import json
import os
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Request, Response, status
import uvicorn

app = FastAPI(title="Telegram Webhook Receiver", version="1.0.0")

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
    return ""

WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "custom-verification-secret")

@app.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None)
):
    """Secure endpoint for Telegram updates."""
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid secret token"
        )

    update = await request.json()
    update_id = update.get("update_id")
    print(f"📥 Received Update #{update_id}")

    # Process message in background or queue
    message = update.get("message")
    if message:
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text")
        print(f"   Chat: {chat_id} | Text: {text}")

    return {"ok": True}

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("webhook_server_fastapi:app", host="0.0.0.0", port=8080, reload=True)
