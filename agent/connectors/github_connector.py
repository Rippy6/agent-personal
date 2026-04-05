"""GitHub連携 — Issue/PR の自動処理エージェント

GitHub Webhook を受信し、Issue/PRの内容をゴールに変換。
結果をコメントとして書き戻す。

セットアップ:
1. GitHub リポジトリの Settings > Webhooks
2. Payload URL: https://your-server/api/github/webhook
3. Content type: application/json
4. Secret: GITHUB_WEBHOOK_SECRET
5. Events: Issues, Pull requests
6. 環境変数: GITHUB_TOKEN, GITHUB_WEBHOOK_SECRET
"""

import json
import hmac
import hashlib
import urllib.request
import urllib.error


class GitHubConnector:
    """GitHub Webhook を受信しゴールに変換、結果をコメント"""

    API_BASE = "https://api.github.com"

    def __init__(self, token: str, webhook_secret: str | None = None):
        self.token = token
        self.webhook_secret = webhook_secret
        self._on_issue = None
        self._on_pr = None

    def set_issue_handler(self, callback):
        """Issue受信時のコールバック: (action, issue_data, repo) -> None"""
        self._on_issue = callback

    def set_pr_handler(self, callback):
        """PR受信時のコールバック: (action, pr_data, repo) -> None"""
        self._on_pr = callback

    def verify_signature(self, body: bytes, signature: str) -> bool:
        """Webhook署名検証"""
        if not self.webhook_secret:
            return True  # シークレット未設定時は検証スキップ
        expected = "sha256=" + hmac.new(
            self.webhook_secret.encode(), body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected)

    def handle_webhook(self, body: bytes, event_type: str, signature: str = "") -> bool:
        """Webhookイベントを処理"""
        if not self.verify_signature(body, signature):
            return False

        try:
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False

        action = data.get("action", "")
        repo = data.get("repository", {}).get("full_name", "")

        if event_type == "issues" and self._on_issue:
            issue = data.get("issue", {})
            self._on_issue(action, issue, repo)
            return True
        elif event_type == "pull_request" and self._on_pr:
            pr = data.get("pull_request", {})
            self._on_pr(action, pr, repo)
            return True

        return False

    def add_comment(self, repo: str, issue_number: int, body: str) -> bool:
        """Issue/PR にコメントを追加"""
        return self._api_call(
            "POST",
            f"/repos/{repo}/issues/{issue_number}/comments",
            {"body": body},
        ) is not None

    def get_issue(self, repo: str, issue_number: int) -> dict | None:
        """Issue情報を取得"""
        return self._api_call("GET", f"/repos/{repo}/issues/{issue_number}")

    def list_issues(self, repo: str, state: str = "open", limit: int = 10) -> list[dict]:
        """Issue一覧を取得"""
        result = self._api_call("GET", f"/repos/{repo}/issues?state={state}&per_page={limit}")
        return result if isinstance(result, list) else []

    def _api_call(self, method: str, path: str, data: dict | None = None) -> dict | list | None:
        """GitHub API呼び出し"""
        url = f"{self.API_BASE}{path}"
        payload = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError):
            return None
