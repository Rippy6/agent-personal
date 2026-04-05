"""Brain（思考エンジン）のテスト"""

import pytest
from agent.brain.mock import MockBrain


class TestMockBrain:
    def setup_method(self):
        self.brain = MockBrain()

    def _make_context(self, goals=None, observation=""):
        return {
            "observation": observation,
            "goals": goals or [],
            "memory_summary": "",
            "long_term_hints": "",
            "available_tools": [
                {"name": "file_list", "description": "ファイル一覧"},
                {"name": "file_read", "description": "ファイル読み込み"},
                {"name": "shell", "description": "コマンド実行"},
            ],
            "iteration": 1,
        }

    def test_curiosity_mode_no_goals(self):
        """ゴールなしの場合、好奇心モードで探索する"""
        ctx = self._make_context()
        decision = self.brain.think(ctx)
        assert decision["thought"]
        assert decision["action"] is not None

    def test_file_related_goal(self):
        ctx = self._make_context(
            goals=[{"description": "ファイル一覧を確認", "status": "active"}]
        )
        decision = self.brain.think(ctx)
        assert decision["action"] is not None
        assert decision["action"]["tool"] in ("file_list", "file_read")

    def test_analysis_goal(self):
        ctx = self._make_context(
            goals=[{"description": "プロジェクトを分析して", "status": "active"}]
        )
        decision = self.brain.think(ctx)
        assert decision["action"] is not None

    def test_test_goal(self):
        ctx = self._make_context(
            goals=[{"description": "テストを実行", "status": "active"}]
        )
        decision = self.brain.think(ctx)
        assert decision["action"]["tool"] == "shell"

    def test_decision_structure(self):
        """決定結果に必須フィールドがあるか"""
        ctx = self._make_context()
        decision = self.brain.think(ctx)
        assert "thought" in decision
        assert "plan" in decision
        assert "action" in decision
        assert "new_goals" in decision
        assert "reasoning" in decision

    def test_idle_eventually_stops(self):
        """好奇心モードがいつか終わる"""
        ctx = self._make_context()
        actions = []
        for i in range(20):
            ctx["iteration"] = i
            decision = self.brain.think(ctx)
            actions.append(decision["action"])
        # At some point action should be None (idle)
        assert None in actions
