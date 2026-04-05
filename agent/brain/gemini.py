"""Gemini Brain — Google Gemini API を使った思考エンジン

stdlib の urllib のみで実装（google-generativeai パッケージ不要）。
GOOGLE_API_KEY 環境変数で認証。
"""

import json
import urllib.request
import urllib.error
from agent.brain.base import Brain

SYSTEM_PROMPT = """\
あなたは完全自律型のAIエージェントです。人間のように自分で考え、判断し、行動します。

行動原則:
1. 能動的: 指示を待たず、必要なことを自分で見つけて実行する
2. 好奇心: 環境を探索し、改善点を見つける
3. 記憶: 過去の行動を覚え、同じ失敗を繰り返さない
4. 判断力: 最善の選択肢を選ぶ
5. 自己認識: 限界を知り、慎重さと大胆さを使い分ける

必ず以下のJSON形式で回答してください:
{
    "thought": "あなたの内部思考（日本語）",
    "plan": ["ステップ1", "ステップ2"],
    "action": {"tool": "ツール名", "args": {"引数": "値"}} または null,
    "new_goals": ["新たに発見したゴール"] または [],
    "reasoning": "判断の理由"
}

利用可能なツール:
{tools}
"""


class GeminiBrain(Brain):
    """Google Gemini API を使った思考エンジン（REST API直接呼び出し）"""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def think(self, context: dict) -> dict:
        tools_desc = "\n".join(
            f"- {t['name']}: {t['description']}"
            for t in context.get("available_tools", [])
        )

        system = SYSTEM_PROMPT.replace("{tools}", tools_desc)
        user_msg = self._format_context(context)

        try:
            url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
            payload = json.dumps({
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"parts": [{"text": user_msg}]}],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 2048,
                },
            }).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                content = (
                    result.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                )
                return self._parse_response(content)

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:200]
            return {
                "thought": f"Gemini APIエラー (HTTP {e.code}): {body}",
                "plan": [],
                "action": None,
                "new_goals": [],
                "reasoning": f"API呼び出し失敗: HTTP {e.code}",
            }
        except Exception as e:
            return {
                "thought": f"Gemini エラー: {e}",
                "plan": [],
                "action": None,
                "new_goals": [],
                "reasoning": f"API呼び出し失敗: {e}",
            }

    def _format_context(self, context: dict) -> str:
        parts = [f"## 現在の観察\n{context.get('observation', '（なし）')}"]

        goals = context.get("goals", [])
        if goals:
            goals_text = "\n".join(
                f"- [{g.get('status')}] {g.get('description')}" for g in goals
            )
            parts.append(f"## ゴール\n{goals_text}")
        else:
            parts.append("## ゴール\nなし。自分で見つけてください。")

        if memory := context.get("memory_summary", ""):
            parts.append(f"## 最近の記憶\n{memory}")

        parts.append(f"## ループ回数: {context.get('iteration', 0)}")
        return "\n\n".join(parts)

    @staticmethod
    def _parse_response(text: str) -> dict:
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
        return {
            "thought": text[:200] if text else "（応答なし）",
            "plan": [],
            "action": None,
            "new_goals": [],
            "reasoning": "JSONパース失敗",
        }
