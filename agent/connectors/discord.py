"""Discord連携 — Discordボットとしてサーバーに常駐

Discord Bot Token で動作。Gateway (WebSocket) ではなく
REST API ポーリングで実装（外部依存なし）。

セットアップ:
1. Discord Developer Portal でBot作成
2. Bot Token 取得
3. サーバーに招待（permissions: Send Messages, Read Message History）
4. 環境変数: DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID
"""

import json
import threading
import time
import urllib.request
import urllib.error


class DiscordConnector:
    """Discord Botとしてメッセージを受信しゴールに変換"""

    API_BASE = "https://discord.com/api/v10"

    def __init__(self, bot_token: str, channel_id: str):
        self.bot_token = bot_token
        self.channel_id = channel_id
        self._running = False
        self._thread: threading.Thread | None = None
        self._on_message = None
        self._last_message_id: str | None = None
        self._bot_user_id: str | None = None

    def set_message_handler(self, callback):
        """メッセージ受信時のコ���ルバック: (text, channel_id, user) -> None"""
        self._on_message = callback

    def start(self):
        """バックグラウンドでポーリング開始"""
        self._running = True
        self._fetch_bot_info()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def send_message(self, channel_id: str, content: str) -> bool:
        """メッセージ送信"""
        result = self._api_call(
            "POST",
            f"/channels/{channel_id}/messages",
            {"content": content},
        )
        return result is not None

    def _fetch_bot_info(self):
        """ボット自身のユーザーIDを取得"""
        result = self._api_call("GET", "/users/@me")
        if result:
            self._bot_user_id = result.get("id")

    def _poll_loop(self):
        """チャンネルのメッセージをポーリング"""
        while self._running:
            try:
                self._check_messages()
            except Exception:
                pass
            time.sleep(3)

    def _check_messages(self):
        """チャンネルの新しいメッセージを取得"""
        params = "?limit=10"
        if self._last_message_id:
            params += f"&after={self._last_message_id}"
        result = self._api_call("GET", f"/channels/{self.channel_id}/messages{params}")
        if not result or not isinstance(result, list):
            return

        for msg in reversed(result):
            msg_id = msg.get("id", "")
            author = msg.get("author", {})

            # ボット自身のメッセージは無視
            if author.get("id") == self._bot_user_id or author.get("bot"):
                continue

            text = msg.get("content", "")
            user = author.get("username", "unknown")

            if self._last_message_id is None or msg_id > self._last_message_id:
                self._last_message_id = msg_id
                if self._on_message and text:
                    self._on_message(text, self.channel_id, user)

    def _api_call(self, method: str, path: str, data: dict | None = None) -> dict | list | None:
        """Discord API呼び出し"""
        url = f"{self.API_BASE}{path}"
        payload = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bot {self.bot_token}",
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError):
            return None
