# Telegram Framework Integration Guides

This guide illustrates how to integrate common bot frameworks with the cached project token located in `.agent/telegram_bot.json` or `.env`.

---

## 1. Helper Function: Loading Cached Token

Regardless of framework, use this standard helper to load the project's cached token:

### Python Helper
```python
import json
import os
from pathlib import Path

def get_project_bot_token(profile: str = "default") -> str:
    # 1. Environment variable override
    env_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if env_token:
        return env_token.strip()

    # 2. Local project cache
    cache_path = Path(__file__).resolve().parent / ".agent" / "telegram_bot.json"
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            token = data.get("profiles", {}).get(profile, {}).get("token")
            if token:
                return token.strip()
        except Exception:
            pass

    # 3. Project .env
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                return line.split("=", 1)[1].strip().strip("'\"")

    raise RuntimeError(
        "Telegram bot token not found. Run 'python scripts/telegram_cli.py auth set --token <TOKEN>'"
    )
```

### TypeScript / Node.js Helper
```typescript
import * as fs from "fs";
import * as path from "path";

export function getProjectBotToken(profile = "default"): string {
  if (process.env.TELEGRAM_BOT_TOKEN) {
    return process.env.TELEGRAM_BOT_TOKEN.trim();
  }

  const cachePath = path.resolve(process.cwd(), ".agent", "telegram_bot.json");
  if (fs.existsSync(cachePath)) {
    try {
      const data = JSON.parse(fs.readFileSync(cachePath, "utf-8"));
      const token = data.profiles?.[profile]?.token;
      if (token) return token.trim();
    } catch {}
  }

  throw new Error("Telegram bot token not found in .agent/telegram_bot.json or environment");
}
```

---

## 2. Aiogram 3.x (Async Python)

Modern, fast, and feature-complete async framework.

```python
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode

token = get_project_bot_token()
bot = Bot(token=token, parse_mode=ParseMode.HTML)
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(msg: types.Message):
    await msg.answer(f"Hello, <b>{msg.from_user.full_name}</b>!")

@dp.message()
async def echo_handler(msg: types.Message):
    await msg.send_copy(chat_id=msg.chat.id)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 3. python-telegram-bot (v20+)

Battle-tested, typed Python framework.

```python
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

token = get_project_bot_token()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot initialized!")

def main():
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

if __name__ == "__main__":
    main()
```

---

## 4. grammY (TypeScript / Node.js)

Lightweight, modern Telegram bot framework for Node.js and Deno.

```typescript
import { Bot } from "grammy";
import { getProjectBotToken } from "./tokenHelper";

const bot = new Bot(getProjectBotToken());

bot.command("start", (ctx) => ctx.reply("Welcome!"));
bot.on("message", (ctx) => ctx.reply("Got your message!"));

bot.start();
```
