"""Ollama Brain — ローカルLLM を使った思考エンジン

Ollamaがローカルで動いていれば、インターネット接続もAPIキーも不要。
完全オフラインで自律エージェントが動く。
"""

import json
import urllib.request
import urllib.error
from agent.brain.base import Brain

SYSTEM_PROMPT = """\
あなたは完全自律型のAIエージェントです。人間のように自分で考え、判断し、行動します。

必ず以下のJSON形式で回答してください:
{
    "thought": "あなたの内部思考",
    "plan": ["ステップ1", "ステップ2"],
    "action": {"tool": "ツール名", "args": {"引数": "値"}} または null,
    "new_goals": ["新たに発見したゴール"] または [],
    "reasoning": "判断の理由"
}

利用可能なツール:
{tools}
"""


class OllamaBrain(Brain):
    """Ollama ローカルLLM を使った思考エンジン"""

    def __init__(self, model: str = "llama3.1", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def think(self, context: dict) -> dict:
        tools_desc = "\n".join(
            f"- {t['name']}: {t['description']}"
            for t in context.get("available_tools", [])
        )

        system = SYSTEM_PROMPT.replace("{tools}", tools_desc)
        user_msg = self._format_context(context)

        try:
            payload = json.dumps({
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 1024},
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self.base_url}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                content = result.get("message", {}).get("content", "")
                return self._parse_response(content)

        except urllib.error.URLError:
            return {
                "thought": "Ollamaに接続できない。ローカルでOllamaが動いているか確認が必要。",
                "plan": ["Ollamaの状態を確認"],
                "action": None,
                "new_goals": [],
                "reasoning": "Ollama接続エラー — ollama serveで起動しているか確認",
            }
        except Exception as e:
            return {
                "thought": f"Ollamaエラー: {e}",
                "plan": [],
                "action": None,
                "new_goals": [],
                "reasoning": f"API呼び出し失敗: {e}",
            }

    def _format_context(self, context: dict) -> str:
        parts = [f"観察: {context.get('observation', '')}"]
        goals = context.get("goals", [])
        if goals:
            parts.append("ゴール: " + ", ".join(g.get("description", "") for g in goals))
        else:
            parts.append("ゴール: なし。自分で見つけて。")
        return "\n".join(parts)

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
