"""記憶システムのテスト"""

import json
import os
import pytest
from agent.memory.short_term import ShortTermMemory
from agent.memory.long_term import LongTermMemory


class TestShortTermMemory:
    def test_add_and_get_recent(self):
        mem = ShortTermMemory(maxlen=10)
        mem.add("observe", "テスト観察")
        mem.add("think", "テスト思考")
        recent = mem.get_recent(2)
        assert len(recent) == 2
        assert recent[0]["phase"] == "observe"
        assert recent[1]["phase"] == "think"

    def test_maxlen(self):
        mem = ShortTermMemory(maxlen=3)
        for i in range(5):
            mem.add("act", f"action_{i}")
        assert len(mem) == 3
        recent = mem.get_recent(3)
        assert "action_2" in recent[0]["content"]

    def test_context_summary(self):
        mem = ShortTermMemory()
        mem.add("observe", "ディレクトリを確認")
        summary = mem.get_context_summary()
        assert "observe" in summary
        assert "ディレクトリ" in summary

    def test_empty_summary(self):
        mem = ShortTermMemory()
        summary = mem.get_context_summary()
        assert "まだ" in summary

    def test_get_last_action_result(self):
        mem = ShortTermMemory()
        mem.add("act_result", "成功しました")
        mem.add("reflect", "振り返り")
        result = mem.get_last_action_result()
        assert result == "成功しました"

    def test_clear(self):
        mem = ShortTermMemory()
        mem.add("test", "data")
        mem.clear()
        assert len(mem) == 0


class TestLongTermMemory:
    def test_store_and_recall(self, tmp_path):
        path = str(tmp_path / "memory.json")
        mem = LongTermMemory(path=path)
        mem.store("python", "Pythonは動的型付け言語")
        results = mem.recall("Python")
        assert len(results) >= 1
        assert "Python" in results[0]

    def test_persistence(self, tmp_path):
        path = str(tmp_path / "memory.json")
        mem1 = LongTermMemory(path=path)
        mem1.store("test", "永続化テスト")

        mem2 = LongTermMemory(path=path)
        results = mem2.recall("永続化")
        assert len(results) >= 1

    def test_deduplication(self, tmp_path):
        path = str(tmp_path / "memory.json")
        mem = LongTermMemory(path=path)
        mem.store("topic", "同じ内容")
        mem.store("topic", "同じ内容")
        with open(path) as f:
            data = json.load(f)
        assert len(data["facts"]["topic"]) == 1

    def test_list_topics(self, tmp_path):
        path = str(tmp_path / "memory.json")
        mem = LongTermMemory(path=path)
        mem.store("alpha", "fact1")
        mem.store("beta", "fact2")
        topics = mem.list_topics()
        assert "alpha" in topics
        assert "beta" in topics

    def test_preferences(self, tmp_path):
        path = str(tmp_path / "memory.json")
        mem = LongTermMemory(path=path)
        mem.store_preference("lang", "ja")
        assert mem.get_preference("lang") == "ja"

    def test_patterns(self, tmp_path):
        path = str(tmp_path / "memory.json")
        mem = LongTermMemory(path=path)
        mem.store_pattern("エラー時はリトライ")
        patterns = mem.get_patterns()
        assert "エラー時はリトライ" in patterns

    def test_corrupted_file(self, tmp_path):
        path = str(tmp_path / "memory.json")
        with open(path, "w") as f:
            f.write("NOT JSON")
        # Should not crash
        mem = LongTermMemory(path=path)
        assert mem.list_topics() == []
