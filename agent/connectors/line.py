"""LINE連携 — LINE Messaging API でメッセージを受信・送信

Webhook受信型。DashboardサーバーのHTTPハンドラーに組み込んで使う。

セットアップ:
1. LINE Developers Console でチャネル作成
2. Channel Secret と Channel Access Token を取得
3. Webhook URL を設定（例: https://your-server/api/line/webhook）
4. 環境変数: LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN
"""

import json
import hmac
import hashlib
import base64
import urllib.request
import urllib.error


class LINEConnector:
    """LINE Messaging APIでメッセージ受信・送信"""

    API_BASE = "https://api.line.me/v2/bot"

    def __init__(self, channel_secret: str, channel_access_token: str):
        self.channel_secret = channel_secret
        self.channel_access_token = channel_access_token
        self._on_message = None

    def set_message_handler(self, callback):
        """メッセージ受信時のコールバック: (text, reply_token, user_id) -> None"""
        self._on_message = callback

    def verify_signature(self, body: bytes, signature: str) -> bool:
        """Webhook署名を検証"""
        expected = base64.b64encode(
            hmac.new(
                self.channel_secret.encode(), body, hashlib.sha256
            ).digest()
        ).decode()
        return hmac.compare_digest(signature, expected)

    def handle_webhook(self, body: bytes, signature: str) -> bool:
        """Webhookイベントを処理"""
        if not self.verify_signature(body, signature):
            return False

        try:
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False

        for event in data.get("events", []):
            if event.get("type") != "message":
                continue
            msg = event.get("message", {})
            if msg.get("type") != "text":
                continue

            text = msg.get("text", "")
            reply_token = event.get("replyToken", "")
            user_id = event.get("source", {}).get("userId", "unknown")

            if self._on_message and text:
                self._on_message(text, reply_token, user_id)

        return True

    def reply(self, reply_token: str, text: str) -> bool:
        """リプライメッセージ送信"""
        return self._api_call("message/reply", {
            "replyToken": reply_token,
            "messages": [{"type": "text", "text": text}],
        })

    def push(self, to: str, text: str) -> bool:
        """プッシュメッセージ送信"""
        return self._api_call("message/push", {
            "to": to,
            "messages": [{"type": "text", "text": text}],
        })

    def _api_call(self, endpoint: str, data: dict) -> bool:
        """LINE API呼び出し"""
        url = f"{self.API_BASE}/{endpoint}"
        payload = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.channel_access_token}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except urllib.error.URLError:
            return False
