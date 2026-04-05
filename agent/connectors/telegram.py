"""Telegram連携 — Telegram Botとしてメッセージを受信

Bot Token で動作（BotFather で取得）。
Long Polling で受信。外部依存なし。

セットアップ:
1. BotFather (@BotFather) でボット作成
2. Bot Token 取得
3. ボットにメッ���ージを送信（チャットIDを取得するため）
4. 環境変数: TELEGRAM_BOT_TOKEN
"""

import json
import threading
import time
import urllib.request
import urllib.error


class TelegramConnector:
    """Telegram Botとしてメッセージを受信しゴールに変換"""

    API_BASE = "https://api.telegram.org/bot"

    def __init__(self, bot_token: str, allowed_chat_ids: list[int] | None = None):
        self.bot_token = bot_token
        self.allowed_chat_ids = allowed_chat_ids  # Noneなら全チャットを受信
        self._running = False
        self._thread: threading.Thread | None = None
        self._on_message = None
        self._offset = 0

    def set_message_handler(self, callback):
        """メッセージ受信時のコールバック: (text, chat_id, user) -> None"""
        self._on_message = callback

    def start(self):
        """バックグラウンドでlong polling開始"""
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def send_message(self, chat_id: int, text: str) -> bool:
        """メッセージ送信"""
        result = self._api_call("sendMessage", {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        })
        return result is not None and result.get("ok", False)

    def _poll_loop(self):
        """long pollingでメッセージ受信"""
        while self._running:
            try:
                self._get_updates()
            except Exception:
                time.sleep(5)

    def _get_updates(self):
        """新しいメッセージを取得"""
        result = self._api_call("getUpdates", {
            "offset": self._offset,
            "timeout": 30,
            "allowed_updates": ["message"],
        })
        if not result or not result.get("ok"):
            return

        for update in result.get("result", []):
            update_id = update.get("update_id", 0)
            self._offset = update_id + 1

            msg = update.get("message", {})
            text = msg.get("text", "")
            chat_id = msg.get("chat", {}).get("id")
            user = msg.get("from", {}).get("username", "unknown")

            if not text or not chat_id:
                continue

            # チャットID制限
            if self.allowed_chat_ids and chat_id not in self.allowed_chat_ids:
                continue

            if self._on_message:
                self._on_message(text, chat_id, user)

    def _api_call(self, method: str, params: dict) -> dict | None:
        """Telegram Bot API呼び出し"""
        url = f"{self.API_BASE}{self.bot_token}/{method}"
        payload = json.dumps(params).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=35) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError):
            return None
