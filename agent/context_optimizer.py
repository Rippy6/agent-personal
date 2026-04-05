"""コンテキストウィンドウ最適化 — 大量の記憶を効率的にLLMに渡す

LLM の入力トークン数には限界がある。
観察・記憶・ゴール情報を優先度で圧縮・選別し、
最も重要な情報だけをコンテキストに含める。
"""

from agent.memory.short_term import ShortTermMemory
from agent.memory.long_term import LongTermMemory
from agent.memory.vector import VectorMemory
from agent.goal import GoalManager


class ContextOptimizer:
    """コンテキストを最適化して LLM に渡す情報量を制御"""

    def __init__(
        self,
        short_memory: ShortTermMemory,
        long_memory: LongTermMemory,
        vector_memory: VectorMemory | None = None,
        goal_manager: GoalManager | None = None,
        max_chars: int = 4000,
    ):
        self.short_memory = short_memory
        self.long_memory = long_memory
        self.vector_memory = vector_memory
        self.goal_manager = goal_manager
        self.max_chars = max_chars

    def build_context(self, observation: str, iteration: int, stats: dict) -> dict:
        """最適化されたコンテキストを構築"""
        budget = self.max_chars
        context_parts = {}

        # 1. 観察（最優先 — 最大40%）
        obs_budget = int(budget * 0.4)
        context_parts["observation"] = self._truncate(observation, obs_budget)
        budget -= len(context_parts["observation"])

        # 2. ゴール（高優先 — 最大20%）
        goals_text = ""
        if self.goal_manager:
            active = self.goal_manager.get_active_goals()
            if active:
                goals_text = "\n".join(
                    f"- [{g.status}] {g.description}" for g in active[:10]
                )
        goal_budget = int(self.max_chars * 0.2)
        context_parts["goals_summary"] = self._truncate(goals_text, goal_budget)
        budget -= len(context_parts["goals_summary"])

        # 3. 短期記憶（中優先 — 最大20%）
        mem_budget = int(self.max_chars * 0.2)
        short_summary = self.short_memory.get_context_summary()
        context_parts["memory_summary"] = self._truncate(short_summary, mem_budget)
        budget -= len(context_parts["memory_summary"])

        # 4. ベクトル記憶で関連情報を検索（残りの予算）
        if self.vector_memory and budget > 100:
            query = observation[:200]
            results = self.vector_memory.search(query, limit=3)
            if results:
                hints = "\n".join(f"[{r['topic']}] {r['text']}" for r in results)
                context_parts["vector_hints"] = self._truncate(hints, budget)
                budget -= len(context_parts["vector_hints"])

        # 5. 長期記憶（最低優先 — 残り）
        if budget > 50:
            long_hints = self.long_memory.get_all_facts_summary(limit=3)
            context_parts["long_term_hints"] = self._truncate(long_hints, budget)

        # メタ情報
        context_parts["iteration"] = iteration
        context_parts["stats"] = stats

        return context_parts

    def summarize_for_brain(self, observation: str, iteration: int, stats: dict) -> dict:
        """Brain.think() に渡す完全なコンテキストを構築"""
        parts = self.build_context(observation, iteration, stats)

        goals = []
        if self.goal_manager:
            goals = [g.to_dict() for g in self.goal_manager.get_active_goals()[:10]]

        return {
            "observation": parts.get("observation", ""),
            "goals": goals,
            "memory_summary": parts.get("memory_summary", ""),
            "long_term_hints": parts.get("long_term_hints", "")
            + ("\n" + parts.get("vector_hints", "") if parts.get("vector_hints") else ""),
            "available_tools": [],  # 呼び出し元で設定
            "iteration": iteration,
            "stats": stats,
        }

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """テキストを指定文字数で切り詰め"""
        if not text:
            return ""
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."
