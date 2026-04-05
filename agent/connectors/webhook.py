"""Webhook API — 外部サービスからHTTPでゴールを投入

既存のDashboardサーバーにWebhookエンドポイントを追加。
任意のHTTPクライアントからエージェントを操作可能。

エンドポイント:
  POST /api/webhook/goal    — ゴール追加
  POST /api/webhook/message — メッセージ送信（ログに表示）
  GET  /api/webhook/status  — エージェント状態取得
  POST /api/webhook/stop    — エージェント停止要求
"""

import json
import hmac
import hashlib
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse


class WebhookMixin:
    """DashboardHandlerに組み込むWebhookハンドラー

    使い方:
      class Handler(WebhookMixin, DashboardHandler):
          pass
    """

    webhook_secret: str | None = None  # 設定すれば署名検証を有効化
    _agent_stop_callback = None  # Agent停止用コールバック

    def handle_webhook(self, method: str, path: str) -> bool:
        """Webhookリクエストを処理。処理した場合True"""
        if not path.startswith("/api/webhook/"):
            return False

        endpoint = path[len("/api/webhook/"):]

        if method == "GET" and endpoint == "status":
            self._webhook_status()
            return True
        elif method == "POST":
            body = self._read_body()
            if body is None:
                return True  # エラーレスポンス済み

            if endpoint == "goal":
                self._webhook_goal(body)
                return True
            elif endpoint == "message":
                self._webhook_message(body)
                return True
            elif endpoint == "stop":
                self._webhook_stop()
                return True

        return False

    def _read_body(self) -> dict | None:
        """リクエストボディを読み取り、署名検証も行う"""
        content_length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_length)

        # 署名検証（秘密鍵が設定されている場合）
        if self.webhook_secret:
            sig_header = self.headers.get("X-Webhook-Signature", "")
            expected = hmac.new(
                self.webhook_secret.encode(), raw, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(sig_header, expected):
                self._respond(403, "application/json", '{"error":"invalid signature"}')
                return None

        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._respond(400, "application/json", '{"error":"invalid json"}')
            return None

    def _webhook_goal(self, data: dict):
        """ゴール追加 Webhook"""
        from agent.web.server import dashboard_state
        goal = data.get("goal", "").strip()
        priority = data.get("priority", 5)
        if not goal:
            self._respond(400, "application/json", '{"error":"empty goal"}')
            return
        dashboard_state.add_goal_from_ui(goal)
        dashboard_state.add_log("system", f"Webhook: ゴール追加「{goal}」")
        self._respond(200, "application/json", json.dumps({
            "ok": True, "goal": goal, "priority": priority,
        }, ensure_ascii=False))

    def _webhook_message(self, data: dict):
        """メッセージ送信 Webhook"""
        from agent.web.server import dashboard_state
        message = data.get("message", "").strip()
        source = data.get("source", "webhook")
        if not message:
            self._respond(400, "application/json", '{"error":"empty message"}')
            return
        dashboard_state.add_log("system", f"[{source}] {message}")
        self._respond(200, "application/json", '{"ok":true}')

    def _webhook_status(self):
        """状態取得 Webhook"""
        from agent.web.server import dashboard_state
        data = dashboard_state.to_dict()
        self._respond(200, "application/json", json.dumps(data, ensure_ascii=False))

    def _webhook_stop(self):
        """停止要求 Webhook"""
        from agent.web.server import dashboard_state
        dashboard_state.add_log("system", "Webhook: 停止要求を受信")
        if self._agent_stop_callback:
            self._agent_stop_callback()
        self._respond(200, "application/json", '{"ok":true,"message":"stop requested"}')
