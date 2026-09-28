#!/usr/bin/env python3
"""
Unit and Integration Tests for Telegram Bot Manager Skill
---------------------------------------------------------
Validates token masking, validation, safe caching, gitignore protection,
API client methods, and CLI command execution.
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add scripts directory to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import telegram_cli


class TestTelegramSecurityAndMasking(unittest.TestCase):
    """Test token masking and validation functions."""

    def test_mask_token(self):
        token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567"
        masked = telegram_cli.mask_token(token)
        self.assertTrue(masked.startswith("123456789:AB***"))
        self.assertTrue(masked.endswith("4567"))
        self.assertNotIn("cdefGHIjklMNOpqrsTUVwxyz123", masked)

    def test_mask_token_short_or_none(self):
        self.assertEqual(telegram_cli.mask_token(None), "<no-token>")
        self.assertEqual(telegram_cli.mask_token(""), "<no-token>")
        self.assertEqual(telegram_cli.mask_token("short"), "***")

    def test_validate_token_format(self):
        valid_token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567"
        invalid_tokens = [
            "invalid_string",
            "12345:short",
            "not_numbers:ABCdefGHIjklMNOpqrsTUVwxyz1234567",
            "",
            None
        ]
        self.assertTrue(telegram_cli.validate_token_format(valid_token))
        for inv in invalid_tokens:
            self.assertFalse(telegram_cli.validate_token_format(inv))


class TestSafeProjectCaching(unittest.TestCase):
    """Test per-project token caching and gitignore safety."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="tg_test_project_")
        self.project_path = Path(self.test_dir).resolve()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_and_resolve_token(self):
        token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567"
        bot_info = {
            "id": 123456789,
            "is_bot": True,
            "first_name": "Test Bot",
            "username": "test_bot"
        }

        # Save token to project
        cache_file = telegram_cli.save_token_to_cache(
            token=token,
            bot_info=bot_info,
            project_root=self.project_path,
            profile="default"
        )
        self.assertTrue(cache_file.exists())

        # Resolve token from project
        resolved, source = telegram_cli.resolve_token(project_root=self.project_path, profile="default")
        self.assertEqual(resolved, token)
        self.assertIn("project_cache", source)

        # Verify cached contents
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        profile_data = data["profiles"]["default"]
        self.assertEqual(profile_data["token"], token)
        self.assertEqual(profile_data["username"], "test_bot")
        self.assertEqual(profile_data["bot_id"], 123456789)

    def test_multi_profile_caching(self):
        tok1 = "111111111:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        tok2 = "222222222:BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"

        telegram_cli.save_token_to_cache(tok1, project_root=self.project_path, profile="default")
        telegram_cli.save_token_to_cache(tok2, project_root=self.project_path, profile="alerts")

        res1, _ = telegram_cli.resolve_token(project_root=self.project_path, profile="default")
        res2, _ = telegram_cli.resolve_token(project_root=self.project_path, profile="alerts")

        self.assertEqual(res1, tok1)
        self.assertEqual(res2, tok2)

    def test_auto_gitignore_protection(self):
        # 1. Existing gitignore without .agent/
        gitignore_path = self.project_path / ".gitignore"
        gitignore_path.write_text("*.log\nnode_modules/\n", encoding="utf-8")

        telegram_cli.ensure_gitignore_protection(self.project_path, ".agent/")
        content = gitignore_path.read_text(encoding="utf-8")
        self.assertIn(".agent/", content)

        # 2. Subsequent call does not duplicate entry
        telegram_cli.ensure_gitignore_protection(self.project_path, ".agent/")
        occurrences = content.count(".agent/")
        self.assertEqual(occurrences, 1)

    def test_remove_token(self):
        token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567"
        telegram_cli.save_token_to_cache(token, project_root=self.project_path, profile="default")
        self.assertTrue(telegram_cli.get_token_cache_path(self.project_path).exists())

        success = telegram_cli.remove_token_from_cache(project_root=self.project_path, profile="default")
        self.assertTrue(success)
        self.assertFalse(telegram_cli.get_token_cache_path(self.project_path).exists())

    def test_env_file_fallback(self):
        env_file = self.project_path / ".env"
        env_file.write_text("SOME_VAR=1\nTELEGRAM_BOT_TOKEN=999999999:ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ\n", encoding="utf-8")

        resolved, source = telegram_cli.resolve_token(project_root=self.project_path)
        self.assertEqual(resolved, "999999999:ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ")
        self.assertIn("project_env", source)


class TestTelegramApiClient(unittest.TestCase):
    """Test TelegramApiClient with mocked network calls."""

    def setUp(self):
        self.token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567"
        self.client = telegram_cli.TelegramApiClient(self.token)

    @patch("urllib.request.urlopen")
    def test_get_me_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.headers.get_content_charset.return_value = "utf-8"
        mock_resp.read.return_value = json.dumps({
            "ok": True,
            "result": {
                "id": 123456789,
                "is_bot": True,
                "first_name": "AntigravityBot",
                "username": "antigravity_bot"
            }
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        res = self.client.get_me()
        self.assertEqual(res["username"], "antigravity_bot")
        self.assertEqual(res["id"], 123456789)

    @patch("urllib.request.urlopen")
    def test_send_message(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.headers.get_content_charset.return_value = "utf-8"
        mock_resp.read.return_value = json.dumps({
            "ok": True,
            "result": {
                "message_id": 42,
                "text": "Hello World"
            }
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        res = self.client.send_message(chat_id=123, text="Hello World", parse_mode="HTML")
        self.assertEqual(res["message_id"], 42)

    @patch("urllib.request.urlopen")
    def test_webhook_methods(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.headers.get_content_charset.return_value = "utf-8"
        mock_resp.read.return_value = json.dumps({
            "ok": True,
            "result": True
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        ok = self.client.set_webhook(url="https://example.com/wh", secret_token="sec123")
        self.assertTrue(ok)

        ok_del = self.client.delete_webhook()
        self.assertTrue(ok_del)

    @patch("urllib.request.urlopen")
    def test_api_error_handling(self, mock_urlopen):
        import urllib.error
        from io import BytesIO

        err_response = BytesIO(json.dumps({
            "ok": False,
            "error_code": 401,
            "description": "Unauthorized"
        }).encode("utf-8"))

        http_err = urllib.error.HTTPError(
            url="https://api.telegram.org",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=err_response
        )
        mock_urlopen.side_effect = http_err

        with self.assertRaises(telegram_cli.TelegramApiError) as ctx:
            self.client.get_me()
        self.assertEqual(ctx.exception.error_code, 401)
        self.assertIn("Unauthorized", ctx.exception.description)


class TestScaffolding(unittest.TestCase):
    """Test project starter scaffolding templates."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="tg_scaffold_")
        self.target_dir = Path(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_scaffold_all_frameworks(self):
        frameworks = ["python-native", "aiogram", "python-telegram-bot", "fastapi-webhook", "grammy-node"]
        for fw in frameworks:
            out_file = telegram_cli.scaffold_project(framework=fw, target_dir=self.target_dir)
            self.assertTrue(out_file.exists(), f"Failed for framework {fw}")
            content = out_file.read_text(encoding="utf-8")
            self.assertIn("telegram_bot.json", content)


class TestCLIExecution(unittest.TestCase):
    """Test CLI commands end-to-end via subprocess."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="tg_cli_test_")
        self.cli_py = str(SCRIPT_DIR / "telegram_cli.py")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_cli_auth_set_and_status(self):
        token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567"

        # 1. auth set --no-verify
        cmd_set = [
            sys.executable, self.cli_py,
            "--project-dir", self.test_dir,
            "auth", "set",
            "--token", token,
            "--no-verify",
            "--json"
        ]
        res = subprocess.run(cmd_set, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Error: {res.stderr}")
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "cached")

        # 2. auth status --offline --json
        cmd_status = [
            sys.executable, self.cli_py,
            "--project-dir", self.test_dir,
            "auth", "status",
            "--offline",
            "--json"
        ]
        res_stat = subprocess.run(cmd_status, capture_output=True, text=True)
        self.assertEqual(res_stat.returncode, 0, f"Error: {res_stat.stderr}")
        stat_data = json.loads(res_stat.stdout)
        self.assertTrue(stat_data["configured"])
        self.assertIn("***", stat_data["masked_token"])
        self.assertNotIn("cdefGHIjklMNOpqrsTUVwxyz123", stat_data["masked_token"])

        # 3. auth remove
        cmd_rm = [
            sys.executable, self.cli_py,
            "--project-dir", self.test_dir,
            "auth", "remove",
            "--json"
        ]
        res_rm = subprocess.run(cmd_rm, capture_output=True, text=True)
        self.assertEqual(res_rm.returncode, 0)
        self.assertTrue(json.loads(res_rm.stdout)["removed"])


if __name__ == "__main__":
    unittest.main()
