"""ゴール管理システムのテスト"""

import json
import pytest
from agent.goal import GoalManager, Goal


class TestGoalManager:
    def test_add_goal(self, tmp_path):
        mgr = GoalManager(path=str(tmp_path / "goals.json"))
        goal = mgr.add_goal("テストゴール")
        assert goal.description == "テストゴール"
        assert goal.status == "pending"

    def test_complete_goal(self, tmp_path):
        mgr = GoalManager(path=str(tmp_path / "goals.json"))
        goal = mgr.add_goal("完了テスト")
        mgr.complete_goal(goal.id, "完了しました")
        updated = mgr.get_goal(goal.id)
        assert updated.status == "done"
        assert updated.result == "完了しました"

    def test_fail_goal(self, tmp_path):
        mgr = GoalManager(path=str(tmp_path / "goals.json"))
        goal = mgr.add_goal("失敗テスト")
        mgr.fail_goal(goal.id, "エラーが発生")
        assert mgr.get_goal(goal.id).status == "failed"

    def test_subtask_completion(self, tmp_path):
        mgr = GoalManager(path=str(tmp_path / "goals.json"))
        parent = mgr.add_goal("親ゴール")
        child1 = mgr.add_goal("子1", parent_id=parent.id)
        child2 = mgr.add_goal("子2", parent_id=parent.id)

        mgr.complete_goal(child1.id)
        assert mgr.get_goal(parent.id).status != "done"

        mgr.complete_goal(child2.id)
        assert mgr.get_goal(parent.id).status == "done"

    def test_priority_ordering(self, tmp_path):
        mgr = GoalManager(path=str(tmp_path / "goals.json"))
        mgr.add_goal("低優先", priority=10)
        mgr.add_goal("高優先", priority=1)
        mgr.add_goal("中優先", priority=5)

        active = mgr.get_active_goals()
        assert active[0].description == "高優先"
        assert active[-1].description == "低優先"

    def test_get_next_goal(self, tmp_path):
        mgr = GoalManager(path=str(tmp_path / "goals.json"))
        mgr.add_goal("唯一のゴール")
        goal = mgr.get_next_goal()
        assert goal is not None
        assert goal.status == "active"

    def test_persistence(self, tmp_path):
        path = str(tmp_path / "goals.json")
        mgr1 = GoalManager(path=path)
        mgr1.add_goal("永続化テスト")

        mgr2 = GoalManager(path=path)
        assert mgr2.has_active_goals()

    def test_summary(self, tmp_path):
        mgr = GoalManager(path=str(tmp_path / "goals.json"))
        mgr.add_goal("ゴールA")
        mgr.add_goal("ゴールB")
        summary = mgr.summary()
        assert "ゴールA" in summary
        assert "ゴールB" in summary
        assert "2件" in summary

    def test_no_active_goals(self, tmp_path):
        mgr = GoalManager(path=str(tmp_path / "goals.json"))
        assert not mgr.has_active_goals()
        assert mgr.get_next_goal() is None
