"""タスク学習 — 成功パターンの記録・検索・再利用

エージェントが過去にうまくいった行動パターンを記憶し、
類似の状況で再利用することで、行動の精度を上げていく。
"""

import json
import os
from datetime import datetime


DEFAULT_PATH = "data/task_patterns.json"


class TaskPattern:
    """1つの成功パターン"""

    def __init__(
        self,
        situation: str,
        action_tool: str,
        action_args: dict,
        result_summary: str,
        success: bool = True,
        goal_keywords: list[str] | None = None,
    ):
        self.situation = situation
        self.action_tool = action_tool
        self.action_args = action_args
        self.result_summary = result_summary
        self.success = success
        self.goal_keywords = goal_keywords or []
        self.use_count = 1
        self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "situation": self.situation,
            "action_tool": self.action_tool,
            "action_args": self.action_args,
            "result_summary": self.result_summary,
            "success": self.success,
            "goal_keywords": self.goal_keywords,
            "use_count": self.use_count,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskPattern":
        p = cls(
            situation=data["situation"],
            action_tool=data["action_tool"],
            action_args=data.get("action_args", {}),
            result_summary=data.get("result_summary", ""),
            success=data.get("success", True),
            goal_keywords=data.get("goal_keywords", []),
        )
        p.use_count = data.get("use_count", 1)
        p.created_at = data.get("created_at", "")
        return p


class TaskLearner:
    """成功パターンの記録・検索・再利用"""

    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        self._patterns: list[TaskPattern] = []
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._patterns = [TaskPattern.from_dict(p) for p in data.get("patterns", [])]
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        data = {"patterns": [p.to_dict() for p in self._patterns]}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def record(
        self,
        situation: str,
        action_tool: str,
        action_args: dict,
        result_summary: str,
        success: bool,
        goal_description: str = "",
    ):
        """行動パターンを記録"""
        keywords = self._extract_keywords(goal_description)

        # 同じツール + 同じ状況の重複チェック
        for p in self._patterns:
            if p.action_tool == action_tool and self._similarity(p.situation, situation) > 0.5:
                p.use_count += 1
                if success:
                    p.success = True
                self._save()
                return

        pattern = TaskPattern(
            situation=situation,
            action_tool=action_tool,
            action_args=action_args,
            result_summary=result_summary[:200],
            success=success,
            goal_keywords=keywords,
        )
        self._patterns.append(pattern)

        # 上限管理
        if len(self._patterns) > 500:
            # 成功率と使用頻度で並べ替え、古い失敗パターンを除去
            self._patterns.sort(key=lambda p: (p.success, p.use_count), reverse=True)
            self._patterns = self._patterns[:500]

        self._save()

    def suggest(self, situation: str, goal: str = "", limit: int = 3) -> list[dict]:
        """現在の状況に合った過去のパターンを提案"""
        if not self._patterns:
            return []

        keywords = self._extract_keywords(goal) + self._extract_keywords(situation)
        scored = []

        for p in self._patterns:
            if not p.success:
                continue
            score = 0.0
            # キーワードマッチ
            for kw in keywords:
                if kw in p.situation.lower() or kw in " ".join(p.goal_keywords):
                    score += 1.0
            # 状況の類似度
            score += self._similarity(p.situation, situation) * 2.0
            # 使用頻度ボーナス
            score += min(p.use_count * 0.1, 1.0)

            if score > 0:
                scored.append({
                    "tool": p.action_tool,
                    "args": p.action_args,
                    "reason": p.situation[:100],
                    "score": round(score, 2),
                    "use_count": p.use_count,
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def success_rate(self, tool_name: str | None = None) -> float:
        """全体またはツール別の成功率"""
        patterns = self._patterns
        if tool_name:
            patterns = [p for p in patterns if p.action_tool == tool_name]
        if not patterns:
            return 0.0
        successes = sum(1 for p in patterns if p.success)
        return successes / len(patterns)

    def stats(self) -> dict:
        """学習統計"""
        total = len(self._patterns)
        success = sum(1 for p in self._patterns if p.success)
        tools = {}
        for p in self._patterns:
            tools[p.action_tool] = tools.get(p.action_tool, 0) + 1
        return {
            "total_patterns": total,
            "success_patterns": success,
            "success_rate": round(success / total, 2) if total > 0 else 0,
            "tools_used": tools,
        }

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        """テキストからキーワードを抽出"""
        import re
        words = re.findall(r"[a-zA-Z]{3,}|[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]{2,}", text.lower())
        return words[:10]

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """2つの文字列の簡易類似度（Jaccard）"""
        if not a or not b:
            return 0.0
        set_a = set(a.lower().split())
        set_b = set(b.lower().split())
        if not set_a or not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union)
