"""長期記憶 — JSON永続化によるトピック別知識ストア"""

import json
import os
from pathlib import Path


DEFAULT_PATH = "data/memory.json"


class LongTermMemory:
    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        self._data: dict = {"facts": {}, "preferences": {}, "learned_patterns": []}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def store(self, topic: str, fact: str):
        facts = self._data.setdefault("facts", {})
        topic_facts = facts.setdefault(topic, [])
        if fact not in topic_facts:
            topic_facts.append(fact)
            self._save()

    def recall(self, query: str, limit: int = 5) -> list[str]:
        query_lower = query.lower()
        keywords = query_lower.split()
        results = []
        for topic, facts in self._data.get("facts", {}).items():
            for fact in facts:
                score = sum(1 for kw in keywords if kw in fact.lower() or kw in topic.lower())
                if score > 0:
                    results.append((score, f"[{topic}] {fact}"))
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:limit]]

    def list_topics(self) -> list[str]:
        return list(self._data.get("facts", {}).keys())

    def store_preference(self, key: str, value: str):
        self._data.setdefault("preferences", {})[key] = value
        self._save()

    def get_preference(self, key: str) -> str | None:
        return self._data.get("preferences", {}).get(key)

    def store_pattern(self, pattern: str):
        patterns = self._data.setdefault("learned_patterns", [])
        if pattern not in patterns:
            patterns.append(pattern)
            self._save()

    def get_patterns(self) -> list[str]:
        return self._data.get("learned_patterns", [])

    def get_all_facts_summary(self, limit: int = 10) -> str:
        lines = []
        count = 0
        for topic, facts in self._data.get("facts", {}).items():
            for fact in facts:
                lines.append(f"[{topic}] {fact}")
                count += 1
                if count >= limit:
                    return "\n".join(lines)
        return "\n".join(lines) if lines else "（長期記憶は空）"
