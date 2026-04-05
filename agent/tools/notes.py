"""メモ・知識記録ツール — 長期記憶と連携"""

from agent.tools.base import Tool


class NoteTool(Tool):
    def __init__(self, long_term_memory=None):
        self._memory = long_term_memory

    def set_memory(self, memory):
        self._memory = memory

    @property
    def name(self) -> str:
        return "note"

    @property
    def description(self) -> str:
        return "メモを保存・検索・一覧表示する（長期記憶に保存される）"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["save", "search", "list"],
                    "description": "操作: save=保存, search=検索, list=一覧",
                },
                "topic": {"type": "string", "description": "トピック名"},
                "content": {"type": "string", "description": "保存する内容 (saveの場合)"},
                "query": {"type": "string", "description": "検索キーワード (searchの場合)"},
            },
            "required": ["action"],
        }

    def execute(self, **kwargs) -> str:
        if self._memory is None:
            return "エラー: 長期記憶が接続されていません"

        action = kwargs.get("action", "")

        if action == "save":
            topic = kwargs.get("topic", "general")
            content = kwargs.get("content", "")
            if not content:
                return "エラー: contentが指定されていません"
            self._memory.store(topic, content)
            return f"メモを保存しました: [{topic}] {content[:50]}..."

        elif action == "search":
            query = kwargs.get("query", "")
            if not query:
                return "エラー: queryが指定されていません"
            results = self._memory.recall(query)
            if not results:
                return f"「{query}」に関するメモは見つかりませんでした"
            return f"「{query}」の検索結果 ({len(results)}件):\n" + "\n".join(
                f"  • {r}" for r in results
            )

        elif action == "list":
            topics = self._memory.list_topics()
            if not topics:
                return "メモはまだありません"
            return f"トピック一覧 ({len(topics)}件):\n" + "\n".join(
                f"  📌 {t}" for t in topics
            )

        else:
            return f"エラー: 不明なaction: {action}"
