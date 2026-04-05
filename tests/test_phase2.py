"""Phase 2 テスト — ベクトル記憶・タスク学習・プランナー・ベンチマーク・コンテキスト最適化"""

import os
import json
import tempfile
import pytest

from agent.memory.vector import VectorMemory, _tokenize
from agent.learning import TaskLearner
from agent.planner import Planner
from agent.goal import GoalManager
from agent.benchmark import AgentBenchmark
from agent.context_optimizer import ContextOptimizer
from agent.memory.short_term import ShortTermMemory
from agent.memory.long_term import LongTermMemory
from agent.brain.gemini import GeminiBrain


# === ベクトル記憶 ===

class TestTokenize:
    def test_english_words(self):
        tokens = _tokenize("hello world test")
        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens

    def test_japanese_bigrams(self):
        tokens = _tokenize("テスト")
        assert "テス" in tokens
        assert "スト" in tokens

    def test_mixed(self):
        tokens = _tokenize("ファイル read test")
        assert "read" in tokens
        assert "test" in tokens
        assert any("ファ" in t for t in tokens)

    def test_short_words_filtered(self):
        tokens = _tokenize("a b cd ef hello")
        assert "a" not in tokens
        assert "b" not in tokens
        assert "hello" in tokens


class TestVectorMemory:
    @pytest.fixture
    def vmem(self, tmp_path):
        return VectorMemory(path=str(tmp_path / "vec.json"))

    def test_store_and_search(self, vmem):
        vmem.store("Pythonでファイルを読む方法", topic="python")
        vmem.store("Javaでデータベースに接続する", topic="java")
        vmem.store("Pythonのテストフレームワーク", topic="python")

        results = vmem.search("Python ファイル")
        assert len(results) > 0
        assert results[0]["topic"] == "python"

    def test_deduplication(self, vmem):
        vmem.store("同じテキスト")
        vmem.store("同じテキスト")
        assert vmem.count() == 1

    def test_count_and_topics(self, vmem):
        vmem.store("テスト1", topic="a")
        vmem.store("テスト2", topic="b")
        assert vmem.count() == 2
        assert set(vmem.topics()) == {"a", "b"}

    def test_persistence(self, tmp_path):
        path = str(tmp_path / "vec.json")
        vm1 = VectorMemory(path=path)
        vm1.store("永続化テスト", topic="test")

        vm2 = VectorMemory(path=path)
        assert vm2.count() == 1

    def test_empty_search(self, vmem):
        results = vmem.search("何もない")
        assert results == []

    def test_cosine_similarity(self):
        score = VectorMemory._cosine_similarity(
            {"a": 1.0, "b": 2.0},
            {"a": 1.0, "c": 3.0},
        )
        assert 0 < score < 1


# === タスク学習 ===

class TestTaskLearner:
    @pytest.fixture
    def learner(self, tmp_path):
        return TaskLearner(path=str(tmp_path / "patterns.json"))

    def test_record_and_suggest(self, learner):
        learner.record(
            situation="ファイ��一覧を確認する",
            action_tool="file_list",
            action_args={"directory": "."},
            result_summary="10件���ファイル",
            success=True,
            goal_description="プロジェクトを分析する",
        )

        suggestions = learner.suggest("ファイルを確認", goal="分析")
        assert len(suggestions) > 0
        assert suggestions[0]["tool"] == "file_list"

    def test_success_rate(self, learner):
        learner.record("test", "shell", {}, "ok", success=True)
        learner.record("test2", "shell", {}, "error", success=False)
        rate = learner.success_rate("shell")
        assert 0 < rate < 1

    def test_stats(self, learner):
        learner.record("s1", "file_list", {}, "ok", True)
        learner.record("s2", "shell", {}, "ok", True)
        stats = learner.stats()
        assert stats["total_patterns"] == 2
        assert "file_list" in stats["tools_used"]

    def test_persistence(self, tmp_path):
        path = str(tmp_path / "patterns.json")
        l1 = TaskLearner(path=path)
        l1.record("s", "tool", {}, "ok", True)

        l2 = TaskLearner(path=path)
        assert l2.stats()["total_patterns"] == 1


# === プランナー ===

class TestPlanner:
    @pytest.fixture
    def planner(self, tmp_path):
        gm = GoalManager(path=str(tmp_path / "goals.json"))
        return Planner(gm), gm

    def test_decompose_analysis_goal(self, planner):
        p, gm = planner
        goal = gm.add_goal("プロジェクトを分析���る")
        subtask_ids = p.decompose(goal.id)
        assert len(subtask_ids) == 4  # 分析ルール: 4サブタスク
        # サブタスクが親に紐づいている
        parent = gm.get_goal(goal.id)
        assert len(parent.subtasks) == 4

    def test_decompose_create_goal(self, planner):
        p, gm = planner
        goal = gm.add_goal("READMEを作成する")
        subtask_ids = p.decompose(goal.id)
        assert len(subtask_ids) == 4  # 作��ルール

    def test_decompose_generic_goal(self, planner):
        p, gm = planner
        goal = gm.add_goal("何か面白いことをやる")
        subtask_ids = p.decompose(goal.id)
        assert len(subtask_ids) == 3  # 汎用3ステップ

    def test_should_decompose(self, planner):
        p, gm = planner
        goal = gm.add_goal("プロジェクトを分析して報告する")
        assert p.should_decompose(goal.id) is True

    def test_should_not_decompose_short(self, planner):
        p, gm = planner
        goal = gm.add_goal("hello")
        assert p.should_decompose(goal.id) is False

    def test_no_double_decompose(self, planner):
        p, gm = planner
        goal = gm.add_goal("テストを実行する")
        p.decompose(goal.id)
        # 2回目は分解しな���
        result = p.decompose(goal.id)
        assert result == goal.subtasks

    def test_execution_order(self, planner):
        p, gm = planner
        goal = gm.add_goal("バグを修正する")
        p.decompose(goal.id)
        order = p.get_execution_order(goal.id)
        assert len(order) == 4


# === ベンチマーク ===

class TestBenchmark:
    def test_benchmark_with_mock_brain(self):
        from agent.brain.mock import MockBrain
        brain = MockBrain()
        bench = AgentBenchmark(brain)
        results = bench.run_all()
        assert "score" in results
        assert "passed" in results
        assert "total" in results
        assert results["total"] == 5
        assert 0 <= results["score"] <= 100

    def test_single_case(self):
        from agent.brain.mock import MockBrain
        from agent.benchmark import BenchmarkCase
        brain = MockBrain()
        bench = AgentBenchmark(brain)
        case = BenchmarkCase(
            name="テスト",
            description="テスト",
            context={
                "observation": "test",
                "goals": [],
                "memory_summary": "",
                "long_term_hints": "",
                "available_tools": [{"name": "file_list", "description": "一覧"}],
                "iteration": 1,
                "stats": {},
            },
        )
        results = bench.run_cases([case])
        assert results["total"] == 1


# === コンテキスト最適化 ===

class TestContextOptimizer:
    @pytest.fixture
    def optimizer(self, tmp_path):
        sm = ShortTermMemory()
        lm = LongTermMemory(path=str(tmp_path / "mem.json"))
        vm = VectorMemory(path=str(tmp_path / "vec.json"))
        gm = GoalManager(path=str(tmp_path / "goals.json"))
        return ContextOptimizer(sm, lm, vm, gm, max_chars=2000)

    def test_build_context(self, optimizer):
        ctx = optimizer.build_context("テスト観察", iteration=1, stats={})
        assert "observation" in ctx
        assert ctx["iteration"] == 1

    def test_summarize_for_brain(self, optimizer):
        ctx = optimizer.summarize_for_brain("テスト", iteration=5, stats={"actions": 3})
        assert ctx["iteration"] == 5
        assert ctx["stats"]["actions"] == 3
        assert "observation" in ctx
        assert "goals" in ctx

    def test_truncation(self):
        result = ContextOptimizer._truncate("a" * 1000, 100)
        assert len(result) == 100
        assert result.endswith("...")

    def test_truncation_short(self):
        result = ContextOptimizer._truncate("short", 100)
        assert result == "short"


# === Gemini Brain ===

class TestGeminiBrain:
    def test_parse_response_valid_json(self):
        text = '{"thought":"テスト","plan":[],"action":null,"new_goals":[],"reasoning":"ok"}'
        result = GeminiBrain._parse_response(text)
        assert result["thought"] == "テスト"

    def test_parse_response_with_surrounding_text(self):
        text = 'Here is my response:\n{"thought":"考え","plan":["step1"],"action":null,"new_goals":[],"reasoning":"理由"}\nDone.'
        result = GeminiBrain._parse_response(text)
        assert result["thought"] == "考え"

    def test_parse_response_invalid(self):
        result = GeminiBrain._parse_response("not json at all")
        assert result["reasoning"] == "JSONパース失敗"
