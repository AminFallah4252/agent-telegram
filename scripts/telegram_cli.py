#!/usr/bin/env python3
"""
Telegram Bot Manager CLI & SDK (Cross-Platform)
-----------------------------------------------
Zero-dependency, cross-platform Telegram Bot management CLI and library.
Handles secure per-project token caching, Zero-Leak credential resolution,
bot configuration, messaging, webhooks, chat administration, and code scaffolding.
"""

from __future__ import annotations

import argparse
import datetime
import json
import mimetypes
import os
import re
import ssl
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Force UTF-8 stream encoding across all operating systems & Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

# API Base URL
TELEGRAM_API_BASE = "https://api.telegram.org"
TOKEN_REGEX = re.compile(r"^\d{8,12}:[A-Za-z0-9_-]{30,}$")
ENV_VAR_NAME = "TELEGRAM_BOT_TOKEN"
CACHE_DIR_NAME = ".agent"
CACHE_FILE_NAME = "telegram_bot.json"


# -----------------------------------------------------------------------------
# Security & Token Utility Functions
# -----------------------------------------------------------------------------

def mask_token(token: Optional[str]) -> str:
    """Safely mask a Telegram bot token to prevent leaks in logs and transcripts.
    
    Example: '123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567' -> '123456789:AB***567'
    """
    if not token:
        return "<no-token>"
    parts = token.split(":", 1)
    if len(parts) == 2:
        bot_id, secret = parts
        if len(secret) > 8:
            masked_secret = f"{secret[:2]}***{secret[-4:]}"
        else:
            masked_secret = "***"
        return f"{bot_id}:{masked_secret}"
    return token[:4] + "***" + token[-2:] if len(token) > 6 else "***"


def validate_token_format(token: str) -> bool:
    """Validate whether the token string matches Telegram's standard format."""
    if not token or not isinstance(token, str):
        return False
    return bool(TOKEN_REGEX.match(token.strip()))


def find_project_root(start_dir: Optional[Union[str, Path]] = None) -> Path:
    """Find the root directory of the current project by walking up the filesystem.
    
    Identifies root by the presence of .git, .agent, package.json, pyproject.toml, or .env.
    Falls back to current working directory if no root markers are detected.
    """
    current = Path(start_dir or os.getcwd()).resolve()
    markers = [".git", CACHE_DIR_NAME, ".agents", "pyproject.toml", "package.json", "go.mod", "Cargo.toml", ".env"]
    
    for parent in [current, *current.parents]:
        if any((parent / marker).exists() for marker in markers):
            return parent
            
    return current


def ensure_gitignore_protection(project_root: Path, entry: str = ".agent/") -> bool:
    """Ensure that the project's .gitignore exists and contains the credential cache entry.
    
    Enforces Priority 7: Zero-Leak Secret Security.
    """
    gitignore_path = project_root / ".gitignore"
    entry_clean = entry.strip()
    
    if gitignore_path.exists():
        try:
            content = gitignore_path.read_text(encoding="utf-8")
            lines = [line.strip() for line in content.splitlines()]
            # Check if entry or its parent folder is already ignored
            normalized_entry = entry_clean.rstrip("/")
            if any(line == entry_clean or line == normalized_entry or line == f"{normalized_entry}/*" for line in lines):
                return True
                
            # Append entry
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write(f"\n# Telegram bot credentials & cache (Auto-added by telegram-bot-manager)\n{entry_clean}\n")
            return True
        except Exception:
            return False
    else:
        # If in a git repository or project root, create a minimal .gitignore
        if (project_root / ".git").exists() or (project_root / CACHE_DIR_NAME).exists():
            try:
                with open(gitignore_path, "w", encoding="utf-8") as f:
                    f.write(f"# Telegram bot credentials & cache (Auto-added by telegram-bot-manager)\n{entry_clean}\n.env\n.env.*\n")
                return True
            except Exception:
                return False
    return False


def get_token_cache_path(project_root: Path) -> Path:
    """Return the absolute path to the project's token cache file."""
    return project_root / CACHE_DIR_NAME / CACHE_FILE_NAME


def read_token_from_env_file(env_path: Path) -> Optional[str]:
    """Parse a .env file for TELEGRAM_BOT_TOKEN without external dependencies."""
    if not env_path.exists() or not env_path.is_file():
        return None
    try:
        content = env_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key == ENV_VAR_NAME and val:
                    return val
    except Exception:
        pass
    return None


def resolve_token(
    project_root: Optional[Path] = None,
    profile: str = "default",
    explicit_token: Optional[str] = None
) -> Tuple[Optional[str], str]:
    """Resolve the Telegram bot token following the credential resolution ladder.
    
    Resolution Order:
    1. Explicit argument / flag
    2. Project cache: `<project_root>/.agent/telegram_bot.json`
    3. Project `.env` file: `TELEGRAM_BOT_TOKEN`
    4. Environment variable: `os.environ["TELEGRAM_BOT_TOKEN"]`
    5. Global user cache: `~/.gemini/config/telegram_bot.json`
    
    Returns:
        Tuple of (token_string, resolution_source)
    """
    if explicit_token and explicit_token.strip():
        return explicit_token.strip(), "explicit_argument"
        
    root = project_root or find_project_root()
    
    # 2. Check Project Cache
    cache_path = get_token_cache_path(root)
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            profiles = data.get("profiles", {})
            profile_data = profiles.get(profile, {})
            token = profile_data.get("token")
            if token and token.strip():
                return token.strip(), f"project_cache ({cache_path})"
        except Exception:
            pass

    # 3. Check Project .env
    env_token = read_token_from_env_file(root / ".env")
    if env_token:
        return env_token, f"project_env ({root / '.env'})"

    # 4. Check System Environment Variable
    env_sys = os.environ.get(ENV_VAR_NAME)
    if env_sys and env_sys.strip():
        return env_sys.strip(), "environment_variable"

    # 5. Check Global User Cache
    global_cache = Path.home() / ".gemini" / "config" / "telegram_bot.json"
    if global_cache.exists():
        try:
            data = json.loads(global_cache.read_text(encoding="utf-8"))
            token = data.get("profiles", {}).get(profile, {}).get("token")
            if token and token.strip():
                return token.strip(), f"global_cache ({global_cache})"
        except Exception:
            pass

    return None, "none"


def save_token_to_cache(
    token: str,
    bot_info: Optional[Dict[str, Any]] = None,
    project_root: Optional[Path] = None,
    profile: str = "default"
) -> Path:
    """Save token and bot metadata safely to project cache with secure permissions.
    
    Enforces restricted file permissions (POSIX 0600) and ensures .gitignore protection.
    """
    root = project_root or find_project_root()
    cache_dir = root / CACHE_DIR_NAME
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Secure directory permissions on POSIX
    if os.name != "nt":
        try:
            os.chmod(cache_dir, stat.S_IRWXU)  # 0700
        except Exception:
            pass
            
    cache_path = get_token_cache_path(root)
    
    # Load existing cache if present
    data: Dict[str, Any] = {"version": "1.0", "profiles": {}}
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            if "profiles" not in data:
                data["profiles"] = {}
        except Exception:
            data = {"version": "1.0", "profiles": {}}
            
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    profile_entry: Dict[str, Any] = {
        "token": token.strip(),
        "updated_at": now
    }
    
    if bot_info:
        profile_entry.update({
            "bot_id": bot_info.get("id"),
            "is_bot": bot_info.get("is_bot", True),
            "first_name": bot_info.get("first_name"),
            "username": bot_info.get("username"),
            "can_join_groups": bot_info.get("can_join_groups"),
            "can_read_all_group_messages": bot_info.get("can_read_all_group_messages"),
            "supports_inline_queries": bot_info.get("supports_inline_queries"),
        })
        
    data["profiles"][profile] = profile_entry
    
    # Write cache file atomically
    temp_path = cache_path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        
    # Restrict permissions before replacing
    if os.name != "nt":
        try:
            os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
        except Exception:
            pass
            
    temp_path.replace(cache_path)
    
    # Ensure gitignore has entry
    ensure_gitignore_protection(root, f"{CACHE_DIR_NAME}/")
    
    return cache_path


def remove_token_from_cache(project_root: Optional[Path] = None, profile: str = "default") -> bool:
    """Remove a bot profile and its token from the project cache."""
    root = project_root or find_project_root()
    cache_path = get_token_cache_path(root)
    if not cache_path.exists():
        return False
        
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        profiles = data.get("profiles", {})
        if profile in profiles:
            del profiles[profile]
            if profiles:
                cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            else:
                cache_path.unlink()
            return True
    except Exception:
        pass
    return False


# -----------------------------------------------------------------------------
# Telegram Bot API Client (Pure Standard Library)
# -----------------------------------------------------------------------------

class TelegramApiError(Exception):
    """Exception raised when Telegram Bot API returns an error response."""
    def __init__(self, description: str, error_code: int = 500, parameters: Optional[Dict[str, Any]] = None):
        super().__init__(f"Telegram API Error [{error_code}]: {description}")
        self.description = description
        self.error_code = error_code
        self.parameters = parameters or {}


class TelegramApiClient:
    """High-level client for Telegram Bot API using Python's standard library."""

    def __init__(self, token: str, timeout: int = 30):
        if not token:
            raise ValueError("Token must not be empty")
        self.token = token.strip()
        self.timeout = timeout
        self.base_url = f"{TELEGRAM_API_BASE}/bot{self.token}"

    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create a secure SSL context for cross-platform HTTPS calls."""
        ctx = ssl.create_default_context()
        return ctx

    def request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute a Telegram API method with JSON payload."""
        url = f"{self.base_url}/{method}"
        headers = {"User-Agent": "Antigravity-TelegramBotManager/1.0"}
        data = None

        if params is not None:
            # Filter None values
            filtered_params = {k: v for k, v in params.items() if v is not None}
            data = json.dumps(filtered_params).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self._create_ssl_context()) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                body = resp.read().decode(charset)
                res_json = json.loads(body)
                if not res_json.get("ok"):
                    raise TelegramApiError(
                        description=res_json.get("description", "Unknown error"),
                        error_code=res_json.get("error_code", resp.status),
                        parameters=res_json.get("parameters")
                    )
                return res_json.get("result")
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8", errors="replace")
                err_json = json.loads(err_body)
                raise TelegramApiError(
                    description=err_json.get("description", str(e)),
                    error_code=err_json.get("error_code", e.code),
                    parameters=err_json.get("parameters")
                ) from None
            except json.JSONDecodeError:
                raise TelegramApiError(description=str(e), error_code=e.code) from None
        except urllib.error.URLError as e:
            raise TelegramApiError(description=f"Network error: {e.reason}", error_code=0) from None

    def request_multipart(self, method: str, fields: Dict[str, Any], files: Dict[str, Union[str, Path]]) -> Any:
        """Execute a multipart/form-data upload request (photos, documents) without third-party deps."""
        url = f"{self.base_url}/{method}"
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        body_parts: List[bytes] = []

        # Add regular fields
        for key, val in fields.items():
            if val is None:
                continue
            if isinstance(val, (dict, list)):
                val = json.dumps(val)
            else:
                val = str(val)
            body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
            body_parts.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
            body_parts.append(f"{val}\r\n".encode("utf-8"))

        # Add files
        for field_name, file_source in files.items():
            file_path = Path(file_source)
            if not file_path.exists() or not file_path.is_file():
                raise FileNotFoundError(f"File not found: {file_source}")

            filename = file_path.name
            mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            file_bytes = file_path.read_bytes()

            body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
            body_parts.append(
                f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8")
            )
            body_parts.append(f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"))
            body_parts.append(file_bytes)
            body_parts.append(b"\r\n")

        body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        payload = b"".join(body_parts)

        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(payload)),
            "User-Agent": "Antigravity-TelegramBotManager/1.0"
        }

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self._create_ssl_context()) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                res_json = json.loads(resp.read().decode(charset))
                if not res_json.get("ok"):
                    raise TelegramApiError(
                        description=res_json.get("description", "Unknown error"),
                        error_code=res_json.get("error_code", resp.status)
                    )
                return res_json.get("result")
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8", errors="replace")
                err_json = json.loads(err_body)
                raise TelegramApiError(
                    description=err_json.get("description", str(e)),
                    error_code=err_json.get("error_code", e.code)
                ) from None
            except Exception:
                raise TelegramApiError(description=str(e), error_code=e.code) from None

    # --- Bot Lifecycle & Config ---

    def get_me(self) -> Dict[str, Any]:
        """A simple method for testing your bot's auth token."""
        return self.request("getMe")

    def get_my_name(self, language_code: Optional[str] = None) -> Dict[str, Any]:
        """Get the current bot name."""
        return self.request("getMyName", {"language_code": language_code})

    def set_my_name(self, name: str, language_code: Optional[str] = None) -> bool:
        """Change the bot's name."""
        return bool(self.request("setMyName", {"name": name, "language_code": language_code}))

    def get_my_description(self, language_code: Optional[str] = None) -> Dict[str, Any]:
        """Get the bot description."""
        return self.request("getMyDescription", {"language_code": language_code})

    def set_my_description(self, description: str, language_code: Optional[str] = None) -> bool:
        """Change the bot's description (shown before starting the bot)."""
        return bool(self.request("setMyDescription", {"description": description, "language_code": language_code}))

    def get_my_short_description(self, language_code: Optional[str] = None) -> Dict[str, Any]:
        """Get the bot short description."""
        return self.request("getMyShortDescription", {"language_code": language_code})

    def set_my_short_description(self, short_description: str, language_code: Optional[str] = None) -> bool:
        """Change the bot's short description (shown in profile and link shares)."""
        return bool(self.request("setMyShortDescription", {"short_description": short_description, "language_code": language_code}))

    def get_my_commands(self, scope: Optional[Dict[str, Any]] = None, language_code: Optional[str] = None) -> List[Dict[str, str]]:
        """Get the current list of the bot's commands."""
        return self.request("getMyCommands", {"scope": scope, "language_code": language_code}) or []

    def set_my_commands(self, commands: List[Dict[str, str]], scope: Optional[Dict[str, Any]] = None, language_code: Optional[str] = None) -> bool:
        """Change the list of the bot's commands."""
        return bool(self.request("setMyCommands", {"commands": commands, "scope": scope, "language_code": language_code}))

    def delete_my_commands(self, scope: Optional[Dict[str, Any]] = None, language_code: Optional[str] = None) -> bool:
        """Delete the list of the bot's commands."""
        return bool(self.request("deleteMyCommands", {"scope": scope, "language_code": language_code}))

    # --- Webhooks & Polling ---

    def get_webhook_info(self) -> Dict[str, Any]:
        """Get current webhook status."""
        return self.request("getWebhookInfo")

    def set_webhook(
        self,
        url: str,
        secret_token: Optional[str] = None,
        max_connections: Optional[int] = None,
        allowed_updates: Optional[List[str]] = None,
        drop_pending_updates: Optional[bool] = None
    ) -> bool:
        """Specify a URL and receive incoming updates via an outgoing webhook."""
        params = {
            "url": url,
            "secret_token": secret_token,
            "max_connections": max_connections,
            "allowed_updates": allowed_updates,
            "drop_pending_updates": drop_pending_updates
        }
        return bool(self.request("setWebhook", params))

    def delete_webhook(self, drop_pending_updates: Optional[bool] = None) -> bool:
        """Remove webhook integration if you decide to switch back to getUpdates."""
        return bool(self.request("deleteWebhook", {"drop_pending_updates": drop_pending_updates}))

    def get_updates(
        self,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        timeout: Optional[int] = None,
        allowed_updates: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Use this method to receive incoming updates using long polling."""
        params = {
            "offset": offset,
            "limit": limit,
            "timeout": timeout,
            "allowed_updates": allowed_updates
        }
        return self.request("getUpdates", params) or []

    # --- Messaging & Media ---

    def send_message(
        self,
        chat_id: Union[int, str],
        text: str,
        parse_mode: Optional[str] = "HTML",
        disable_web_page_preview: Optional[bool] = None,
        disable_notification: Optional[bool] = None,
        message_thread_id: Optional[int] = None,
        reply_to_message_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Send a text message to a Telegram chat, channel, or topic."""
        params = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
            "disable_notification": disable_notification,
            "message_thread_id": message_thread_id,
            "reply_to_message_id": reply_to_message_id
        }
        return self.request("sendMessage", params)

    def send_photo(
        self,
        chat_id: Union[int, str],
        photo: Union[str, Path],
        caption: Optional[str] = None,
        parse_mode: Optional[str] = "HTML",
        disable_notification: Optional[bool] = None,
        message_thread_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Send a photo by URL or local file path."""
        photo_str = str(photo)
        fields = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": parse_mode,
            "disable_notification": disable_notification,
            "message_thread_id": message_thread_id
        }

        # Check if photo is a local file or remote URL/file_id
        if Path(photo_str).exists() and Path(photo_str).is_file():
            return self.request_multipart("sendPhoto", fields, {"photo": Path(photo_str)})
        else:
            fields["photo"] = photo_str
            return self.request("sendPhoto", fields)

    def send_document(
        self,
        chat_id: Union[int, str],
        document: Union[str, Path],
        caption: Optional[str] = None,
        parse_mode: Optional[str] = "HTML",
        disable_notification: Optional[bool] = None,
        message_thread_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Send a general file/document by URL or local file path."""
        doc_str = str(document)
        fields = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": parse_mode,
            "disable_notification": disable_notification,
            "message_thread_id": message_thread_id
        }

        if Path(doc_str).exists() and Path(doc_str).is_file():
            return self.request_multipart("sendDocument", fields, {"document": Path(doc_str)})
        else:
            fields["document"] = doc_str
            return self.request("sendDocument", fields)

    def send_chat_action(
        self,
        chat_id: Union[int, str],
        action: str = "typing",
        message_thread_id: Optional[int] = None
    ) -> bool:
        """Send a status indicator (e.g. typing, upload_photo, record_video)."""
        params = {
            "chat_id": chat_id,
            "action": action,
            "message_thread_id": message_thread_id
        }
        return bool(self.request("sendChatAction", params))

    # --- Chat Administration ---

    def get_chat(self, chat_id: Union[int, str]) -> Dict[str, Any]:
        """Get up to date information about the chat."""
        return self.request("getChat", {"chat_id": chat_id})

    def get_chat_administrators(self, chat_id: Union[int, str]) -> List[Dict[str, Any]]:
        """Get a list of administrators in a chat."""
        return self.request("getChatAdministrators", {"chat_id": chat_id}) or []

    def get_chat_member_count(self, chat_id: Union[int, str]) -> int:
        """Get the number of members in a chat."""
        return int(self.request("getChatMemberCount", {"chat_id": chat_id}) or 0)

    def pin_chat_message(
        self,
        chat_id: Union[int, str],
        message_id: int,
        disable_notification: Optional[bool] = None
    ) -> bool:
        """Pin a message in a group, supergroup, or channel."""
        return bool(self.request("pinChatMessage", {
            "chat_id": chat_id,
            "message_id": message_id,
            "disable_notification": disable_notification
        }))

    def unpin_chat_message(self, chat_id: Union[int, str], message_id: Optional[int] = None) -> bool:
        """Unpin a message in a chat."""
        return bool(self.request("unpinChatMessage", {"chat_id": chat_id, "message_id": message_id}))


# -----------------------------------------------------------------------------
# Project Scaffolding Generator
# -----------------------------------------------------------------------------

SCAFFOLD_TEMPLATES = {
    "python-native": {
        "filename": "bot_native.py",
        "content": '''#!/usr/bin/env python3
"""Lightweight, zero-dependency Telegram polling bot."""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

# Resolve token safely from project cache or environment
def get_bot_token() -> str:
    env_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if env_token:
        return env_token.strip()
    cache_path = Path(__file__).resolve().parent / ".agent" / "telegram_bot.json"
    if cache_path.exists():
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        token = data.get("profiles", {}).get("default", {}).get("token")
        if token:
            return token.strip()
    raise RuntimeError("No Telegram bot token found in .agent/telegram_bot.json or TELEGRAM_BOT_TOKEN")

TOKEN = get_bot_token()
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

def api_call(method: str, params: dict = None) -> dict:
    url = f"{BASE_URL}/{method}"
    data = json.dumps(params).encode("utf-8") if params else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    bot = api_call("getMe")["result"]
    print(f"🤖 Started native bot @{bot['username']} (ID: {bot['id']})")
    
    offset = None
    while True:
        try:
            params = {"timeout": 30}
            if offset:
                params["offset"] = offset
            res = api_call("getUpdates", params)
            updates = res.get("result", [])
            for u in updates:
                offset = u["update_id"] + 1
                msg = u.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")
                if not chat_id:
                    continue
                if text == "/start":
                    api_call("sendMessage", {
                        "chat_id": chat_id,
                        "text": f"👋 Hello! I am <b>{bot['first_name']}</b>, ready to assist you.",
                        "parse_mode": "HTML"
                    })
                elif text:
                    api_call("sendMessage", {
                        "chat_id": chat_id,
                        "text": f"Echo: {text}"
                    })
        except KeyboardInterrupt:
            print("\\n🛑 Stopping bot...")
            break
        except Exception as e:
            print(f"Error during polling: {e}", file=sys.stderr)
            time.sleep(2)

if __name__ == "__main__":
    main()
'''
    },
    "aiogram": {
        "filename": "bot_aiogram.py",
        "content": '''#!/usr/bin/env python3
"""Production-grade Telegram Bot using Aiogram 3.x."""
import asyncio
import json
import logging
import os
from pathlib import Path
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_bot_token() -> str:
    env_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if env_token:
        return env_token.strip()
    cache_path = Path(__file__).resolve().parent / ".agent" / "telegram_bot.json"
    if cache_path.exists():
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        token = data.get("profiles", {}).get("default", {}).get("token")
        if token:
            return token.strip()
    raise RuntimeError("No Telegram bot token found in .agent/telegram_bot.json or TELEGRAM_BOT_TOKEN")

bot = Bot(token=get_bot_token(), parse_mode=ParseMode.HTML)
dp = Dispatcher()

@dp.message(CommandStart())
async def handle_start(message: types.Message):
    await message.answer(f"👋 Welcome <b>{message.from_user.first_name}</b>! Send me a message or /help.")

@dp.message(Command("help"))
async def handle_help(message: types.Message):
    await message.answer("ℹ️ <b>Available Commands:</b>\\n/start - Start the bot\\n/help - View help information\\n/status - Health status")

@dp.message(Command("status"))
async def handle_status(message: types.Message):
    await message.answer("✅ Bot service is active and operating normally.")

@dp.message()
async def handle_echo(message: types.Message):
    if message.text:
        await message.reply(f"Received: {message.text}")

async def main():
    me = await bot.get_me()
    logging.info(f"Bot @{me.username} running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
'''
    },
    "python-telegram-bot": {
        "filename": "bot_ptb.py",
        "content": '''#!/usr/bin/env python3
"""Async Telegram Bot using python-telegram-bot (v20+)."""
import json
import logging
import os
from pathlib import Path
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

def get_bot_token() -> str:
    env_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if env_token:
        return env_token.strip()
    cache_path = Path(__file__).resolve().parent / ".agent" / "telegram_bot.json"
    if cache_path.exists():
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        token = data.get("profiles", {}).get("default", {}).get("token")
        if token:
            return token.strip()
    raise RuntimeError("No token found")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_html(rf"Hi {user.mention_html()}! Bot is operational.")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Echo: {update.message.text}")

def main():
    token = get_bot_token()
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    app.run_polling()

if __name__ == "__main__":
    main()
'''
    },
    "fastapi-webhook": {
        "filename": "server_fastapi.py",
        "content": '''#!/usr/bin/env python3
"""Production-grade Webhook receiver with FastAPI and Telegram Secret Verification."""
import json
import os
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Request, Response, status
import uvicorn

app = FastAPI(title="Telegram Webhook Service")

def get_bot_token() -> str:
    env_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if env_token:
        return env_token.strip()
    cache_path = Path(__file__).resolve().parent / ".agent" / "telegram_bot.json"
    if cache_path.exists():
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        token = data.get("profiles", {}).get("default", {}).get("token")
        if token:
            return token.strip()
    raise RuntimeError("Bot token not configured")

WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "super-secret-token")

@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None)
):
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret token")
        
    payload = await request.json()
    # Process update asynchronously
    print(f"Received Telegram Update ID: {payload.get('update_id')}")
    return {"ok": True}

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''
    },
    "grammy-node": {
        "filename": "bot_grammy.ts",
        "content": '''import { Bot } from "grammy";
import * as fs from "fs";
import * as path from "path";

function resolveToken(): string {
  if (process.env.TELEGRAM_BOT_TOKEN) {
    return process.env.TELEGRAM_BOT_TOKEN.trim();
  }
  const cachePath = path.resolve(__dirname, ".agent", "telegram_bot.json");
  if (fs.existsSync(cachePath)) {
    const raw = fs.readFileSync(cachePath, "utf-8");
    const data = JSON.parse(raw);
    const token = data.profiles?.default?.token;
    if (token) return token.trim();
  }
  throw new Error("No Telegram bot token found in .agent/telegram_bot.json or TELEGRAM_BOT_TOKEN");
}

const bot = new Bot(resolveToken());

bot.command("start", (ctx) => ctx.reply("👋 Hello from grammY bot!"));
bot.on("message:text", (ctx) => ctx.reply(`Echo: ${ctx.message.text}`));

bot.start();
console.log("🚀 grammY bot started!");
'''
    }
}


def scaffold_project(framework: str, target_dir: Optional[Path] = None) -> Path:
    """Generate starter template files for a given Telegram framework."""
    if framework not in SCAFFOLD_TEMPLATES:
        available = ", ".join(SCAFFOLD_TEMPLATES.keys())
        raise ValueError(f"Unknown framework '{framework}'. Available: {available}")
        
    dest_dir = target_dir or find_project_root()
    template = SCAFFOLD_TEMPLATES[framework]
    target_file = dest_dir / template["filename"]
    
    target_file.write_text(template["content"], encoding="utf-8")
    
    # Set executable permissions on posix
    if os.name != "nt":
        try:
            target_file.chmod(0o755)
        except Exception:
            pass
            
    return target_file


# -----------------------------------------------------------------------------
# CLI Subcommand Handlers
# -----------------------------------------------------------------------------

def cmd_auth_set(args: argparse.Namespace) -> int:
    """Set and cache Telegram bot token for the project."""
    token = args.token.strip()
    if not validate_token_format(token):
        if not args.force:
            print(f"❌ Error: Invalid token format '{mask_token(token)}'. Telegram tokens match '123456789:ABC...'", file=sys.stderr)
            return 1

    project_root = Path(args.project_dir).resolve() if args.project_dir else find_project_root()
    bot_info = None

    if not args.no_verify:
        print(f"🔍 Validating bot token via Telegram API...")
        try:
            client = TelegramApiClient(token)
            bot_info = client.get_me()
            print(f"✅ Verified Bot: @{bot_info.get('username')} ({bot_info.get('first_name')}, ID: {bot_info.get('id')})")
        except TelegramApiError as e:
            print(f"❌ Verification failed: {e.description}", file=sys.stderr)
            if not args.force:
                print("Tip: Use --force or --no-verify to cache without live verification.", file=sys.stderr)
                return 1

    cache_path = save_token_to_cache(
        token=token,
        bot_info=bot_info,
        project_root=project_root,
        profile=args.profile
    )

    masked = mask_token(token)
    if args.json:
        res = {
            "status": "cached",
            "profile": args.profile,
            "cache_path": str(cache_path),
            "project_root": str(project_root),
            "masked_token": masked,
            "bot_info": bot_info
        }
        print(json.dumps(res, indent=2))
    else:
        print(f"🔒 Token cached securely in: {cache_path}")
        print(f"🛡️  Profile: '{args.profile}' | Token: {masked}")
        print(f"🛡️  Zero-Leak: Verified .gitignore protection for '{project_root / '.gitignore'}'")
    return 0


def cmd_auth_status(args: argparse.Namespace) -> int:
    """Inspect the status and source of the current bot token."""
    project_root = Path(args.project_dir).resolve() if args.project_dir else find_project_root()
    token, source = resolve_token(project_root=project_root, profile=args.profile, explicit_token=args.token)

    if not token:
        if args.json:
            print(json.dumps({"configured": False, "source": "none"}, indent=2))
        else:
            print("⚠️  No Telegram bot token found for this project.")
            print(f"   Project Root: {project_root}")
            print(f"   Run: python telegram_cli.py auth set --token <BOT_TOKEN>")
        return 1

    masked = mask_token(token)
    bot_info = None
    api_status = "unverified"
    error_msg = None

    if not args.offline:
        try:
            client = TelegramApiClient(token)
            bot_info = client.get_me()
            api_status = "connected"
        except TelegramApiError as e:
            api_status = "error"
            error_msg = e.description

    if args.json:
        out = {
            "configured": True,
            "profile": args.profile,
            "source": source,
            "masked_token": masked,
            "token": token if args.unmask else masked,
            "project_root": str(project_root),
            "api_status": api_status,
            "bot_info": bot_info,
            "error": error_msg
        }
        print(json.dumps(out, indent=2))
    else:
        print(f"🤖 Telegram Bot Configuration:")
        print(f"   • Project Root: {project_root}")
        print(f"   • Profile:      {args.profile}")
        print(f"   • Token Source: {source}")
        print(f"   • Token:        {token if args.unmask else masked}")
        print(f"   • API Status:   {api_status.upper()}")
        if bot_info:
            print(f"   • Bot ID:       {bot_info.get('id')}")
            print(f"   • Username:     @{bot_info.get('username')}")
            print(f"   • Name:         {bot_info.get('first_name')}")
            print(f"   • Groups:       {'Allowed' if bot_info.get('can_join_groups') else 'Disabled'}")
        if error_msg:
            print(f"   • Error:        {error_msg}")
    return 0


def cmd_auth_remove(args: argparse.Namespace) -> int:
    """Remove bot profile token from project cache."""
    project_root = Path(args.project_dir).resolve() if args.project_dir else find_project_root()
    success = remove_token_from_cache(project_root=project_root, profile=args.profile)
    if args.json:
        print(json.dumps({"removed": success, "profile": args.profile}, indent=2))
    else:
        if success:
            print(f"🗑️  Removed profile '{args.profile}' from project cache.")
        else:
            print(f"⚠️  Profile '{args.profile}' was not found in cache.")
    return 0 if success else 1


def _get_client_or_exit(args: argparse.Namespace) -> TelegramApiClient:
    project_root = Path(args.project_dir).resolve() if getattr(args, "project_dir", None) else find_project_root()
    token, source = resolve_token(
        project_root=project_root,
        profile=getattr(args, "profile", "default"),
        explicit_token=getattr(args, "token", None)
    )
    if not token:
        print("❌ Error: No Telegram bot token found. Run 'auth set --token <TOKEN>' first.", file=sys.stderr)
        sys.exit(1)
    return TelegramApiClient(token)


def cmd_bot_get_me(args: argparse.Namespace) -> int:
    client = _get_client_or_exit(args)
    res = client.get_me()
    print(json.dumps(res, indent=2))
    return 0


def cmd_bot_name(args: argparse.Namespace) -> int:
    client = _get_client_or_exit(args)
    if args.set:
        ok = client.set_my_name(name=args.set, language_code=args.lang)
        print(json.dumps({"success": ok, "name": args.set, "language_code": args.lang}, indent=2))
    else:
        res = client.get_my_name(language_code=args.lang)
        print(json.dumps(res, indent=2))
    return 0


def cmd_bot_description(args: argparse.Namespace) -> int:
    client = _get_client_or_exit(args)
    if args.short:
        if args.set:
            ok = client.set_my_short_description(short_description=args.set, language_code=args.lang)
            print(json.dumps({"success": ok, "short_description": args.set}, indent=2))
        else:
            res = client.get_my_short_description(language_code=args.lang)
            print(json.dumps(res, indent=2))
    else:
        if args.set:
            ok = client.set_my_description(description=args.set, language_code=args.lang)
            print(json.dumps({"success": ok, "description": args.set}, indent=2))
        else:
            res = client.get_my_description(language_code=args.lang)
            print(json.dumps(res, indent=2))
    return 0


def cmd_bot_commands(args: argparse.Namespace) -> int:
    client = _get_client_or_exit(args)
    if args.delete:
        ok = client.delete_my_commands(language_code=args.lang)
        print(json.dumps({"success": ok, "deleted": True}, indent=2))
    elif args.set:
        try:
            raw_cmds = json.loads(args.set)
            if not isinstance(raw_cmds, list):
                raise ValueError("Commands must be a JSON array")
        except Exception as e:
            print(f"❌ Error parsing commands JSON: {e}", file=sys.stderr)
            return 1
        ok = client.set_my_commands(commands=raw_cmds, language_code=args.lang)
        print(json.dumps({"success": ok, "commands": raw_cmds}, indent=2))
    else:
        res = client.get_my_commands(language_code=args.lang)
        print(json.dumps(res, indent=2))
    return 0


def cmd_webhook_info(args: argparse.Namespace) -> int:
    client = _get_client_or_exit(args)
    res = client.get_webhook_info()
    print(json.dumps(res, indent=2))
    return 0


def cmd_webhook_set(args: argparse.Namespace) -> int:
    client = _get_client_or_exit(args)
    ok = client.set_webhook(
        url=args.url,
        secret_token=args.secret_token,
        max_connections=args.max_connections,
        drop_pending_updates=args.drop_pending
    )
    print(json.dumps({"success": ok, "url": args.url}, indent=2))
    return 0


def cmd_webhook_delete(args: argparse.Namespace) -> int:
    client = _get_client_or_exit(args)
    ok = client.delete_webhook(drop_pending_updates=args.drop_pending)
    print(json.dumps({"success": ok, "deleted": True}, indent=2))
    return 0


def cmd_updates_get(args: argparse.Namespace) -> int:
    client = _get_client_or_exit(args)
    res = client.get_updates(offset=args.offset, limit=args.limit, timeout=args.timeout)
    print(json.dumps(res, indent=2))
    return 0


def cmd_send_message(args: argparse.Namespace) -> int:
    client = _get_client_or_exit(args)
    res = client.send_message(
        chat_id=args.chat_id,
        text=args.text,
        parse_mode=args.parse_mode if args.parse_mode != "none" else None,
        disable_notification=args.silent,
        message_thread_id=args.thread_id,
        reply_to_message_id=args.reply_to
    )
    print(json.dumps(res, indent=2))
    return 0


def cmd_send_photo(args: argparse.Namespace) -> int:
    client = _get_client_or_exit(args)
    res = client.send_photo(
        chat_id=args.chat_id,
        photo=args.photo,
        caption=args.caption,
        parse_mode=args.parse_mode if args.parse_mode != "none" else None,
        disable_notification=args.silent,
        message_thread_id=args.thread_id
    )
    print(json.dumps(res, indent=2))
    return 0


def cmd_send_document(args: argparse.Namespace) -> int:
    client = _get_client_or_exit(args)
    res = client.send_document(
        chat_id=args.chat_id,
        document=args.document,
        caption=args.caption,
        parse_mode=args.parse_mode if args.parse_mode != "none" else None,
        disable_notification=args.silent,
        message_thread_id=args.thread_id
    )
    print(json.dumps(res, indent=2))
    return 0


def cmd_send_action(args: argparse.Namespace) -> int:
    client = _get_client_or_exit(args)
    ok = client.send_chat_action(chat_id=args.chat_id, action=args.action, message_thread_id=args.thread_id)
    print(json.dumps({"success": ok, "chat_id": args.chat_id, "action": args.action}, indent=2))
    return 0


def cmd_chat_info(args: argparse.Namespace) -> int:
    client = _get_client_or_exit(args)
    res = client.get_chat(chat_id=args.chat_id)
    print(json.dumps(res, indent=2))
    return 0


def cmd_chat_admins(args: argparse.Namespace) -> int:
    client = _get_client_or_exit(args)
    res = client.get_chat_administrators(chat_id=args.chat_id)
    print(json.dumps(res, indent=2))
    return 0


def cmd_chat_pin(args: argparse.Namespace) -> int:
    client = _get_client_or_exit(args)
    if args.unpin:
        ok = client.unpin_chat_message(chat_id=args.chat_id, message_id=args.message_id)
        print(json.dumps({"success": ok, "unpinned": True}, indent=2))
    else:
        if not args.message_id:
            print("❌ Error: --message-id is required to pin a message.", file=sys.stderr)
            return 1
        ok = client.pin_chat_message(chat_id=args.chat_id, message_id=args.message_id, disable_notification=args.silent)
        print(json.dumps({"success": ok, "pinned": True, "message_id": args.message_id}, indent=2))
    return 0


def cmd_scaffold(args: argparse.Namespace) -> int:
    target_dir = Path(args.target_dir).resolve() if args.target_dir else find_project_root()
    created_file = scaffold_project(framework=args.framework, target_dir=target_dir)
    if args.json:
        print(json.dumps({"framework": args.framework, "file": str(created_file)}, indent=2))
    else:
        print(f"✨ Successfully generated '{args.framework}' template at: {created_file}")
    return 0


# -----------------------------------------------------------------------------
# Main CLI Parser Construction
# -----------------------------------------------------------------------------

def add_common_args(p: argparse.ArgumentParser, include_token: bool = True) -> None:
    p.add_argument("--profile", default=argparse.SUPPRESS, help="Bot profile name (default: 'default')")
    p.add_argument("--project-dir", default=argparse.SUPPRESS, help="Explicit project directory path")
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output results in JSON format")
    if include_token:
        p.add_argument("--token", default=argparse.SUPPRESS, help="Explicit bot token (bypasses cache lookup)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="telegram_cli",
        description="Cross-Platform Telegram Bot Manager & Safe Project Cache"
    )
    parser.add_argument("--token", default=None, help="Explicit bot token (bypasses cache lookup)")
    parser.add_argument("--profile", default="default", help="Bot profile name (default: 'default')")
    parser.add_argument("--project-dir", default=None, help="Explicit project directory path")
    parser.add_argument("--json", action="store_true", default=False, help="Output results in JSON format")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- auth ---
    p_auth = subparsers.add_parser("auth", help="Manage bot token & project credentials cache")
    s_auth = p_auth.add_subparsers(dest="subcommand", required=True)

    p_auth_set = s_auth.add_parser("set", help="Save and verify bot token for current project")
    add_common_args(p_auth_set, include_token=False)
    p_auth_set.add_argument("--token", required=True, help="Telegram bot token")
    p_auth_set.add_argument("--no-verify", action="store_true", help="Skip live API validation")
    p_auth_set.add_argument("--force", action="store_true", help="Force saving even if format/verify fails")
    p_auth_set.set_defaults(func=cmd_auth_set)

    p_auth_status = s_auth.add_parser("status", help="Inspect configured token and connectivity")
    add_common_args(p_auth_status, include_token=True)
    p_auth_status.add_argument("--offline", action="store_true", help="Do not make live network call")
    p_auth_status.add_argument("--unmask", action="store_true", help="Reveal unmasked token (CAUTION)")
    p_auth_status.set_defaults(func=cmd_auth_status)

    p_auth_remove = s_auth.add_parser("remove", help="Remove cached token for this project")
    add_common_args(p_auth_remove, include_token=False)
    p_auth_remove.set_defaults(func=cmd_auth_remove)

    # --- bot ---
    p_bot = subparsers.add_parser("bot", help="Bot identity and profile management")
    s_bot = p_bot.add_subparsers(dest="subcommand", required=True)

    p_bot_get_me = s_bot.add_parser("get-me", help="Retrieve bot info via getMe")
    add_common_args(p_bot_get_me, include_token=True)
    p_bot_get_me.set_defaults(func=cmd_bot_get_me)

    p_bot_name = s_bot.add_parser("name", help="Get or set bot display name")
    add_common_args(p_bot_name, include_token=True)
    p_bot_name.add_argument("--set", help="New bot display name")
    p_bot_name.add_argument("--lang", help="Two-letter language code")
    p_bot_name.set_defaults(func=cmd_bot_name)

    p_bot_desc = s_bot.add_parser("description", help="Get or set bot description")
    add_common_args(p_bot_desc, include_token=True)
    p_bot_desc.add_argument("--set", help="New description text")
    p_bot_desc.add_argument("--short", action="store_true", help="Target short description instead of full")
    p_bot_desc.add_argument("--lang", help="Two-letter language code")
    p_bot_desc.set_defaults(func=cmd_bot_description)

    p_bot_cmds = s_bot.add_parser("commands", help="Get, set, or delete bot commands")
    add_common_args(p_bot_cmds, include_token=True)
    p_bot_cmds.add_argument("--set", help='JSON array of commands: [{"command":"start","description":"Start"}]')
    p_bot_cmds.add_argument("--delete", action="store_true", help="Delete all commands")
    p_bot_cmds.add_argument("--lang", help="Two-letter language code")
    p_bot_cmds.set_defaults(func=cmd_bot_commands)

    # --- webhook ---
    p_webhook = subparsers.add_parser("webhook", help="Webhook configuration")
    s_webhook = p_webhook.add_subparsers(dest="subcommand", required=True)

    p_wh_info = s_webhook.add_parser("info", help="Get webhook info and status")
    add_common_args(p_wh_info, include_token=True)
    p_wh_info.set_defaults(func=cmd_webhook_info)

    p_wh_set = s_webhook.add_parser("set", help="Set webhook URL")
    add_common_args(p_wh_set, include_token=True)
    p_wh_set.add_argument("--url", required=True, help="HTTPS webhook URL")
    p_wh_set.add_argument("--secret-token", help="Secret token for X-Telegram-Bot-Api-Secret-Token")
    p_wh_set.add_argument("--max-connections", type=int, help="Max simultaneous connections (1-100)")
    p_wh_set.add_argument("--drop-pending", action="store_true", help="Drop pending updates")
    p_wh_set.set_defaults(func=cmd_webhook_set)

    p_wh_del = s_webhook.add_parser("delete", help="Delete webhook")
    add_common_args(p_wh_del, include_token=True)
    p_wh_del.add_argument("--drop-pending", action="store_true", help="Drop pending updates")
    p_wh_del.set_defaults(func=cmd_webhook_delete)

    # --- updates ---
    p_upd = subparsers.add_parser("updates", help="Polling updates")
    s_upd = p_upd.add_subparsers(dest="subcommand", required=True)

    p_upd_get = s_upd.add_parser("get", help="Get recent updates via long polling")
    add_common_args(p_upd_get, include_token=True)
    p_upd_get.add_argument("--offset", type=int, help="Identifier of the first update to return")
    p_upd_get.add_argument("--limit", type=int, default=10, help="Number of updates to retrieve (1-100)")
    p_upd_get.add_argument("--timeout", type=int, default=0, help="Polling timeout in seconds")
    p_upd_get.set_defaults(func=cmd_updates_get)

    # --- send ---
    p_send = subparsers.add_parser("send", help="Send messages, media, or actions")
    s_send = p_send.add_subparsers(dest="subcommand", required=True)

    p_send_msg = s_send.add_parser("message", help="Send a text message")
    add_common_args(p_send_msg, include_token=True)
    p_send_msg.add_argument("--chat-id", required=True, help="Target chat or channel ID")
    p_send_msg.add_argument("--text", required=True, help="Message text")
    p_send_msg.add_argument("--parse-mode", default="HTML", choices=["HTML", "MarkdownV2", "Markdown", "none"], help="Parse mode")
    p_send_msg.add_argument("--silent", action="store_true", help="Send without notification")
    p_send_msg.add_argument("--thread-id", type=int, help="Forum topic message thread ID")
    p_send_msg.add_argument("--reply-to", type=int, help="Reply to message ID")
    p_send_msg.set_defaults(func=cmd_send_message)

    p_send_photo = s_send.add_parser("photo", help="Send a photo (URL or local file path)")
    add_common_args(p_send_photo, include_token=True)
    p_send_photo.add_argument("--chat-id", required=True, help="Target chat ID")
    p_send_photo.add_argument("--photo", required=True, help="Photo URL or local file path")
    p_send_photo.add_argument("--caption", help="Photo caption text")
    p_send_photo.add_argument("--parse-mode", default="HTML", choices=["HTML", "MarkdownV2", "Markdown", "none"], help="Parse mode")
    p_send_photo.add_argument("--silent", action="store_true", help="Send without notification")
    p_send_photo.add_argument("--thread-id", type=int, help="Forum topic message thread ID")
    p_send_photo.set_defaults(func=cmd_send_photo)

    p_send_doc = s_send.add_parser("document", help="Send a file document (URL or local path)")
    add_common_args(p_send_doc, include_token=True)
    p_send_doc.add_argument("--chat-id", required=True, help="Target chat ID")
    p_send_doc.add_argument("--document", required=True, help="Document URL or local file path")
    p_send_doc.add_argument("--caption", help="Document caption text")
    p_send_doc.add_argument("--parse-mode", default="HTML", choices=["HTML", "MarkdownV2", "Markdown", "none"], help="Parse mode")
    p_send_doc.add_argument("--silent", action="store_true", help="Send without notification")
    p_send_doc.add_argument("--thread-id", type=int, help="Forum topic message thread ID")
    p_send_doc.set_defaults(func=cmd_send_document)

    p_send_act = s_send.add_parser("action", help="Send chat action status indicator")
    add_common_args(p_send_act, include_token=True)
    p_send_act.add_argument("--chat-id", required=True, help="Target chat ID")
    p_send_act.add_argument("--action", default="typing", choices=["typing", "upload_photo", "record_video", "upload_video", "record_voice", "upload_voice", "upload_document", "find_location"], help="Action type")
    p_send_act.add_argument("--thread-id", type=int, help="Forum topic message thread ID")
    p_send_act.set_defaults(func=cmd_send_action)

    # --- chat ---
    p_chat = subparsers.add_parser("chat", help="Chat and channel administration")
    s_chat = p_chat.add_subparsers(dest="subcommand", required=True)

    p_chat_info = s_chat.add_parser("info", help="Get chat metadata and settings")
    add_common_args(p_chat_info, include_token=True)
    p_chat_info.add_argument("--chat-id", required=True, help="Target chat or channel ID")
    p_chat_info.set_defaults(func=cmd_chat_info)

    p_chat_admins = s_chat.add_parser("admins", help="List administrators of a chat")
    add_common_args(p_chat_admins, include_token=True)
    p_chat_admins.add_argument("--chat-id", required=True, help="Target chat or channel ID")
    p_chat_admins.set_defaults(func=cmd_chat_admins)

    p_chat_pin = s_chat.add_parser("pin", help="Pin or unpin a message in chat")
    add_common_args(p_chat_pin, include_token=True)
    p_chat_pin.add_argument("--chat-id", required=True, help="Target chat ID")
    p_chat_pin.add_argument("--message-id", type=int, help="Message ID to pin/unpin")
    p_chat_pin.add_argument("--unpin", action="store_true", help="Unpin instead of pin")
    p_chat_pin.add_argument("--silent", action="store_true", help="Pin without sending notification")
    p_chat_pin.set_defaults(func=cmd_chat_pin)

    # --- scaffold ---
    p_scaffold = subparsers.add_parser("scaffold", help="Generate Telegram bot code template")
    add_common_args(p_scaffold, include_token=False)
    p_scaffold.add_argument(
        "--framework",
        default="python-native",
        choices=["python-native", "aiogram", "python-telegram-bot", "fastapi-webhook", "grammy-node"],
        help="Bot framework template to generate"
    )
    p_scaffold.add_argument("--target-dir", help="Destination folder for scaffolded code")
    p_scaffold.set_defaults(func=cmd_scaffold)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        exit_code = args.func(args)
        sys.exit(exit_code or 0)
    except TelegramApiError as e:
        if getattr(args, "json", False):
            print(json.dumps({"error": True, "description": e.description, "error_code": e.error_code}, indent=2))
        else:
            print(f"❌ Telegram API Error [{e.error_code}]: {e.description}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        if getattr(args, "json", False):
            print(json.dumps({"error": True, "message": str(e)}, indent=2))
        else:
            print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
