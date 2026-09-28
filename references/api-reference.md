# Telegram Bot API Reference

This reference covers the Telegram Bot API methods supported by the `telegram-bot-manager` skill and CLI.

---

## 1. Bot Identity & Configuration

### `getMe`
A simple method for testing your bot's authentication token. Requires no parameters.
- **CLI**: `python scripts/telegram_cli.py bot get-me`
- **Returns**: Basic information about the bot in form of a `User` object (ID, username, first_name, can_join_groups, can_read_all_group_messages, supports_inline_queries).

### `getMyName` / `setMyName`
Get or change the bot's display name.
- **CLI**: 
  - Read: `python scripts/telegram_cli.py bot name [--lang <ISO_CODE>]`
  - Set: `python scripts/telegram_cli.py bot name --set "My Bot Name" [--lang <ISO_CODE>]`

### `getMyDescription` / `setMyDescription`
Get or change the bot's description (shown in the chat with the bot if the chat is empty).
- **CLI**:
  - Read: `python scripts/telegram_cli.py bot description [--lang <ISO_CODE>]`
  - Set: `python scripts/telegram_cli.py bot description --set "Comprehensive description..." [--lang <ISO_CODE>]`

### `getMyShortDescription` / `setMyShortDescription`
Get or change the bot's short description (shown on the bot's profile page and when someone shares the bot).
- **CLI**:
  - Read: `python scripts/telegram_cli.py bot description --short [--lang <ISO_CODE>]`
  - Set: `python scripts/telegram_cli.py bot description --short --set "Short summary" [--lang <ISO_CODE>]`

### `getMyCommands` / `setMyCommands` / `deleteMyCommands`
Manage the list of the bot's commands displayed in the menu button.
- **CLI**:
  - List: `python scripts/telegram_cli.py bot commands`
  - Set: `python scripts/telegram_cli.py bot commands --set '[{"command":"start","description":"Start the bot"},{"command":"help","description":"Display help"}]'`
  - Delete: `python scripts/telegram_cli.py bot commands --delete`

---

## 2. Webhook & Polling Management

### `getWebhookInfo`
Get current webhook status, URL, pending update count, and recent delivery errors.
- **CLI**: `python scripts/telegram_cli.py webhook info`

### `setWebhook`
Specify a URL and receive incoming updates via an outgoing webhook.
- **Parameters**:
  - `--url`: HTTPS URL to send updates to.
  - `--secret-token`: Secret token (1-256 characters) sent in `X-Telegram-Bot-Api-Secret-Token` header.
  - `--max-connections`: Maximum allowed simultaneous HTTPS connections (1-100).
  - `--drop-pending`: Drop all pending updates before activating webhook.
- **CLI**: `python scripts/telegram_cli.py webhook set --url https://example.com/webhook --secret-token "my-secret" --drop-pending`

### `deleteWebhook`
Remove webhook integration to switch back to polling.
- **CLI**: `python scripts/telegram_cli.py webhook delete [--drop-pending]`

### `getUpdates`
Retrieve incoming updates using long polling.
- **Parameters**:
  - `--offset`: Identifier of the first update to return.
  - `--limit`: Number of updates to retrieve (1-100).
  - `--timeout`: Polling timeout in seconds.
- **CLI**: `python scripts/telegram_cli.py updates get --limit 10 --timeout 15`

---

## 3. Messaging & Media

### `sendMessage`
Send text messages to a user, group, channel, or forum topic.
- **Parameters**:
  - `--chat-id`: Target chat ID or channel username (`@channelname`).
  - `--text`: The text content.
  - `--parse-mode`: `HTML`, `MarkdownV2`, `Markdown`, or `none`. Default is `HTML`.
  - `--silent`: Send quietly without notification sound.
  - `--thread-id`: Target forum topic message thread ID.
  - `--reply-to`: Message ID to reply to.
- **CLI**:
  ```bash
  python scripts/telegram_cli.py send message \
    --chat-id "-1001234567890" \
    --text "<b>Deploy Alert</b>: Service updated successfully." \
    --parse-mode HTML
  ```

### `sendPhoto`
Send photo by URL or local file path (supports automatic multipart/form-data upload).
- **Parameters**:
  - `--chat-id`: Target chat ID.
  - `--photo`: Web URL or absolute/relative local file path.
  - `--caption`: Optional caption text.
- **CLI**:
  ```bash
  python scripts/telegram_cli.py send photo \
    --chat-id "-1001234567890" \
    --photo "./assets/screenshot.png" \
    --caption "Latest build preview"
  ```

### `sendDocument`
Send general file or document by URL or local file path.
- **Parameters**:
  - `--chat-id`: Target chat ID.
  - `--document`: Web URL or absolute/relative local file path.
  - `--caption`: Optional caption text.
- **CLI**:
  ```bash
  python scripts/telegram_cli.py send document \
    --chat-id "-1001234567890" \
    --document "./dist/report.pdf" \
    --caption "Weekly summary report"
  ```

### `sendChatAction`
Tell the user that something is happening on the bot's side.
- **Parameters**:
  - `--chat-id`: Target chat ID.
  - `--action`: `typing`, `upload_photo`, `record_video`, `upload_video`, `record_voice`, `upload_voice`, `upload_document`, `find_location`.
- **CLI**: `python scripts/telegram_cli.py send action --chat-id 123456789 --action typing`

---

## 4. Chat Administration

### `getChat`
Get up-to-date information about a chat or channel (title, description, permissions, pinned message, member count).
- **CLI**: `python scripts/telegram_cli.py chat info --chat-id "-1001234567890"`

### `getChatAdministrators`
Retrieve the list of administrators with their permissions and custom titles.
- **CLI**: `python scripts/telegram_cli.py chat admins --chat-id "-1001234567890"`

### `pinChatMessage` / `unpinChatMessage`
Pin or unpin a message in a supergroup or channel.
- **CLI**:
  - Pin: `python scripts/telegram_cli.py chat pin --chat-id "-1001234567890" --message-id 42 [--silent]`
  - Unpin: `python scripts/telegram_cli.py chat pin --chat-id "-1001234567890" --message-id 42 --unpin`
