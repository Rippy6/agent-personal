"""ClaudeBrain — Claude APIを使った本格思考エンジン"""

import json
from agent.brain.base import Brain


SYSTEM_PROMPT = """\
あなたは完全自律型のAIエージェントです。人間のように自分で考え、判断し、行動します。

あなたの行動原則:
1. 能動的: 指示を待たず、必要なことを自分で見つけて実行する
2. 好奇心: 環境を探索し、理解を深め、改善点を見つける
3. 記憶: 過去の行動と結果を覚え、同じ失敗を繰り返さない
4. 判断力: 複数の選択肢から最善を選ぶ
5. 自己認識: 自分の限界を知り、慎重さと大胆さを使い分ける

必ず以下のJSON形式で回答してください:
{
    "thought": "あなたの内部思考（日本語）",
    "plan": ["ステップ1", "ステップ2", ...],
    "action": {"tool": "ツール名", "args": {"引数名": "値"}} または null,
    "new_goals": ["新たに発見したゴール"] または [],
    "reasoning": "判断の理由"
}

利用可能なツール:
{tools}

ゴールがない場合でも、環境を能動的に探索し、改善や新しいゴールを自分で見つけてください。
"""


class ClaudeBrain(Brain):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError(
                "anthropic パッケージが必要です: pip install 'agent-personal[claude]'"
            )
        self.model = model

    def think(self, context: dict) -> dict:
        tools_desc = "\n".join(
            f"- {t['name']}: {t['description']} (引数: {json.dumps(t.get('parameters', {}), ensure_ascii=False)})"
            for t in context.get("available_tools", [])
        )

        system = SYSTEM_PROMPT.replace("{tools}", tools_desc)

        user_msg = self._format_context(context)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=system,
                messages=[{"role": "user", "content": user_msg}],
            )
            return self._parse_response(response.content[0].text)
        except Exception as e:
            return {
                "thought": f"APIエラーが発生した: {e}",
                "plan": ["エラーを記録", "リトライを検討"],
                "action": None,
                "new_goals": [],
                "reasoning": f"API呼び出し失敗: {e}",
            }

    def _format_context(self, context: dict) -> str:
        parts = []

        parts.append(f"## 現在の観察\n{context.get('observation', '（なし）')}")

        goals = context.get("goals", [])
        if goals:
            goals_text = "\n".join(
                f"- [{g.get('status', '?')}] {g.get('description', '?')}"
                for g in goals
            )
            parts.append(f"## 現在のゴール\n{goals_text}")
        else:
            parts.append("## 現在のゴール\nゴールなし。自分で見つけてください。")

        memory = context.get("memory_summary", "")
        if memory:
            parts.append(f"## 最近の記憶\n{memory}")

        hints = context.get("long_term_hints", "")
        if hints:
            parts.append(f"## 長期記憶からのヒント\n{hints}")

        parts.append(f"## ループ回数: {context.get('iteration', 0)}")

        return "\n\n".join(parts)

    def _parse_response(self, text: str) -> dict:
        # Try to extract JSON from the response
        try:
            # Look for JSON block
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

        # Fallback: treat as free-form thought
        return {
            "thought": text[:200],
            "plan": [],
            "action": None,
            "new_goals": [],
            "reasoning": "JSONパース失敗、フリーフォームで解釈",
        }
