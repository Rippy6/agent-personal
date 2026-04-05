"""Slack連携 — Slackボットとしてチャンネルに常駐

Slack Bot Token (xoxb-...) と App-Level Token で動作。
stdlib の urllib のみ使用（slack_sdk 不要）。

セットアップ:
1. Slack App を作成 (https://api.slack.com/apps)
2. Bot Token Scopes: chat:write, channels:history, channels:read
3. Event Subscriptions を有効化（Socket Mode推奨）
4. 環境変数: SLACK_BOT_TOKEN, SLACK_APP_TOKEN
"""

import json
import threading
import time
import urllib.request
import urllib.error


class SlackConnector:
    """Slack Botとしてメッセージを受信しゴールに変換"""

    API_BASE = "https://slack.com/api"

    def __init__(self, bot_token: str, channel: str | None = None):
        self.bot_token = bot_token
        self.channel = channel  # 監視対象チャンネル（Noneなら全チャンネル）
        self._running = False
        self._thread: threading.Thread | None = None
        self._on_message = None  # コールバック: (text, channel, user) -> None
        self._last_ts = str(time.time())

    def set_message_handler(self, callback):
        """メッセージ受信時のコールバックを設定"""
        self._on_message = callback

    def start(self):
        """バックグラウンドでポーリング開始"""
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def send_message(self, channel: str, text: str) -> bool:
        """メッセージ送信"""
        return self._api_call("chat.postMessage", {
            "channel": channel,
            "text": text,
        }) is not None

    def _poll_loop(self):
        """チャンネルのメッセージをポーリング"""
        while self._running:
            try:
                if self.channel:
                    self._check_channel(self.channel)
            except Exception:
                pass
            time.sleep(3)  # 3秒間隔

    def _check_channel(self, channel: str):
        """チャンネルの新しいメッセージを取得"""
        result = self._api_call("conversations.history", {
            "channel": channel,
            "oldest": self._last_ts,
            "limit": "10",
        })
        if not result or not result.get("ok"):
            return

        messages = result.get("messages", [])
        for msg in reversed(messages):
            # ボット自身のメッセージは無視
            if msg.get("bot_id") or msg.get("subtype"):
                continue
            ts = msg.get("ts", "")
            if float(ts) > float(self._last_ts):
                self._last_ts = ts
                text = msg.get("text", "")
                user = msg.get("user", "unknown")
                if self._on_message and text:
                    self._on_message(text, channel, user)

    def _api_call(self, method: str, params: dict) -> dict | None:
        """Slack API呼び出し"""
        url = f"{self.API_BASE}/{method}"
        payload = json.dumps(params).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {self.bot_token}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError):
            return None
