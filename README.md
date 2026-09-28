# Telegram Bot Manager (Antigravity Skill & CLI)

A cross-platform, enterprise-grade skill and zero-dependency CLI for managing Telegram bots across projects. Features secure per-project token caching, automated `.gitignore` protection, Zero-Leak credential resolution, messaging, webhooks, chat administration, and code scaffolding.

---

## 🚀 Features

- **Cross-Platform**: Pure Python 3.8+ implementation with zero external dependencies. Runs identically on Windows, Linux, and macOS. Includes PowerShell (`run.ps1`) and Bash (`run.sh`) wrappers.
- **Safe Per-Project Caching**: Automatically isolates bot credentials into `<project_root>/.agent/telegram_bot.json`.
- **Zero-Leak Credential Security**: Enforces file permissions (`chmod 0600` on POSIX / ACL hardening on Windows), automatically verifies/updates `.gitignore`, and masks tokens (`123456789:AB***xyz`) across all logs.
- **Multi-Profile Support**: Cache and manage multiple bot instances per project (e.g. `default`, `alerts`, `dev`, `prod`).
- **Comprehensive Telegram Bot API Suite**:
  - `auth`: Safe caching, validation with `getMe`, status checks, profile switching.
  - `bot`: Identity, description, commands menu, profile updates.
  - `send`: HTML/Markdown text, attachments (photos, documents with native multipart upload), typing indicators.
  - `webhook`: Webhook status, configuration with secret tokens, and deletion.
  - `updates`: Long-polling updates retrieval for triage and debugging.
  - `chat`: Chat info, administrators inspection, message pinning.
  - `scaffold`: Generate ready-to-run starter code for Aiogram, python-telegram-bot, native Python, FastAPI webhooks, or grammY (Node.js).

---

## 📦 Quick Start

### 1. Configure Bot Token for a Project
```bash
python scripts/telegram_cli.py auth set --token "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567"
```

### 2. Check Bot Status
```bash
python scripts/telegram_cli.py auth status
```

### 3. Send a Message
```bash
python scripts/telegram_cli.py send message --chat-id "-1001234567890" --text "<b>Deploy Notification</b>: Release complete!"
```

### 4. Scaffold a Starter Bot
```bash
python scripts/telegram_cli.py scaffold --framework aiogram
```

---

## 🔒 Credential Resolution Order

1. CLI flag: `--token <TOKEN>`
2. Project cache: `.agent/telegram_bot.json`
3. Project `.env`: `TELEGRAM_BOT_TOKEN=<TOKEN>`
4. Environment variable: `os.environ["TELEGRAM_BOT_TOKEN"]`
5. Global cache: `~/.gemini/config/telegram_bot.json`

---

## 🧪 Testing

Run the full automated test suite:
```bash
python -m unittest tests/test_telegram_cli.py
```

---

## 📖 Documentation & References

- [Main Skill Documentation](SKILL.md)
- [API Reference](references/api-reference.md)
- [Security & Caching Guide](references/security-and-caching.md)
- [Framework Integration Guide](references/framework-guides.md)
