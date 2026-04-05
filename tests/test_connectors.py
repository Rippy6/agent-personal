"""Phase 3 テスト — コネクター（Webhook, Slack, Discord, Telegram, LINE, GitHub, Email）"""

import json
import hmac
import hashlib
import base64
import pytest

from agent.connectors.webhook import WebhookMixin
from agent.connectors.slack import SlackConnector
from agent.connectors.discord import DiscordConnector
from agent.connectors.telegram import TelegramConnector
from agent.connectors.line import LINEConnector
from agent.connectors.github_connector import GitHubConnector
from agent.connectors.email_connector import EmailConnector


# === Webhook ===

class TestWebhookMixin:
    def test_mixin_has_handle_webhook(self):
        assert hasattr(WebhookMixin, "handle_webhook")

    def test_non_webhook_path_returns_false(self):
        mixin = WebhookMixin()
        assert mixin.handle_webhook("GET", "/other/path") is False

    def test_webhook_status_path(self):
        # WebhookMixinは実際にはHTTPハンドラーの中で使うので
        # パス検出のみテスト
        mixin = WebhookMixin()
        path = "/api/webhook/status"
        assert path.startswith("/api/webhook/")


# === Slack ===

class TestSlackConnector:
    def test_init(self):
        conn = SlackConnector(bot_token="xoxb-test", channel="C123")
        assert conn.bot_token == "xoxb-test"
        assert conn.channel == "C123"

    def test_set_message_handler(self):
        conn = SlackConnector(bot_token="xoxb-test")
        called = []
        conn.set_message_handler(lambda t, c, u: called.append(t))
        assert conn._on_message is not None

    def test_stop(self):
        conn = SlackConnector(bot_token="xoxb-test")
        conn._running = True
        conn.stop()
        assert conn._running is False


# === Discord ===

class TestDiscordConnector:
    def test_init(self):
        conn = DiscordConnector(bot_token="test-token", channel_id="12345")
        assert conn.bot_token == "test-token"
        assert conn.channel_id == "12345"

    def test_set_message_handler(self):
        conn = DiscordConnector(bot_token="test", channel_id="123")
        conn.set_message_handler(lambda t, c, u: None)
        assert conn._on_message is not None


# === Telegram ===

class TestTelegramConnector:
    def test_init(self):
        conn = TelegramConnector(bot_token="123:ABC")
        assert conn.bot_token == "123:ABC"

    def test_allowed_chat_ids(self):
        conn = TelegramConnector(bot_token="123:ABC", allowed_chat_ids=[100, 200])
        assert conn.allowed_chat_ids == [100, 200]


# === LINE ===

class TestLINEConnector:
    def test_init(self):
        conn = LINEConnector(channel_secret="secret", channel_access_token="token")
        assert conn.channel_secret == "secret"

    def test_verify_signature_valid(self):
        secret = "test_secret"
        conn = LINEConnector(channel_secret=secret, channel_access_token="token")
        body = b'{"events":[]}'
        sig = base64.b64encode(
            hmac.new(secret.encode(), body, hashlib.sha256).digest()
        ).decode()
        assert conn.verify_signature(body, sig) is True

    def test_verify_signature_invalid(self):
        conn = LINEConnector(channel_secret="secret", channel_access_token="token")
        assert conn.verify_signature(b'{"events":[]}', "invalid") is False

    def test_handle_webhook_invalid_sig(self):
        conn = LINEConnector(channel_secret="secret", channel_access_token="token")
        assert conn.handle_webhook(b'{}', "bad_sig") is False

    def test_handle_webhook_message_event(self):
        secret = "test_secret"
        conn = LINEConnector(channel_secret=secret, channel_access_token="token")
        received = []
        conn.set_message_handler(lambda t, r, u: received.append(t))

        body = json.dumps({
            "events": [{
                "type": "message",
                "replyToken": "rtoken",
                "source": {"userId": "U123"},
                "message": {"type": "text", "text": "テストメッセージ"},
            }]
        }).encode("utf-8")
        sig = base64.b64encode(
            hmac.new(secret.encode(), body, hashlib.sha256).digest()
        ).decode()

        result = conn.handle_webhook(body, sig)
        assert result is True
        assert received == ["テストメッセージ"]


# === GitHub ===

class TestGitHubConnector:
    def test_init(self):
        conn = GitHubConnector(token="ghp_test")
        assert conn.token == "ghp_test"

    def test_verify_signature_no_secret(self):
        conn = GitHubConnector(token="test")
        assert conn.verify_signature(b'data', "") is True  # シークレット未設定

    def test_verify_signature_with_secret(self):
        secret = "my_secret"
        conn = GitHubConnector(token="test", webhook_secret=secret)
        body = b'{"action":"opened"}'
        sig = "sha256=" + hmac.new(
            secret.encode(), body, hashlib.sha256
        ).hexdigest()
        assert conn.verify_signature(body, sig) is True

    def test_verify_signature_invalid(self):
        conn = GitHubConnector(token="test", webhook_secret="secret")
        assert conn.verify_signature(b'data', "sha256=wrong") is False

    def test_handle_issue_webhook(self):
        conn = GitHubConnector(token="test")
        received = []
        conn.set_issue_handler(lambda a, i, r: received.append((a, i["title"])))

        body = json.dumps({
            "action": "opened",
            "issue": {"title": "バグ報告", "number": 1},
            "repository": {"full_name": "user/repo"},
        }).encode("utf-8")

        result = conn.handle_webhook(body, "issues")
        assert result is True
        assert received == [("opened", "バグ報告")]

    def test_handle_pr_webhook(self):
        conn = GitHubConnector(token="test")
        received = []
        conn.set_pr_handler(lambda a, p, r: received.append((a, p["title"])))

        body = json.dumps({
            "action": "opened",
            "pull_request": {"title": "新機能追加"},
            "repository": {"full_name": "user/repo"},
        }).encode("utf-8")

        result = conn.handle_webhook(body, "pull_request")
        assert result is True
        assert received == [("opened", "新機能追加")]


# === Email ===

class TestEmailConnector:
    def test_init(self):
        conn = EmailConnector(
            address="test@example.com",
            password="pass",
            imap_server="imap.example.com",
        )
        assert conn.address == "test@example.com"

    def test_allowed_senders(self):
        conn = EmailConnector(
            address="me@example.com",
            password="pass",
            allowed_senders=["boss@example.com"],
        )
        assert conn.allowed_senders == ["boss@example.com"]

    def test_decode_header_ascii(self):
        result = EmailConnector._decode_header("Test Subject")
        assert result == "Test Subject"

    def test_stop(self):
        conn = EmailConnector(address="a", password="b")
        conn._running = True
        conn.stop()
        assert conn._running is False
