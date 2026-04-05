"""ベクトル記憶 — TF-IDF風の軽量セマンティック検索

外部依存なし。stdlib の math だけで実装。
記憶をベクトル化し、クエリとのコサイン類似度で検索する。

仕組み:
1. テキストを単語（トークン）に分割
2. 各単語の TF-IDF スコアを計算
3. クエリとの cos 類似度でランキング
"""

import json
import math
import os
import re
from collections import Counter


def _tokenize(text: str) -> list[str]:
    """テキストをトークン（単語）に分割。日本語は文字バイグラム、英語は単語"""
    tokens = []
    # 英数字の単語
    for word in re.findall(r"[a-zA-Z0-9_]+", text.lower()):
        if len(word) >= 2:
            tokens.append(word)
    # 日本語: ひらがな・カタカナ・漢字のバイグラム
    jp_chars = re.findall(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]+", text)
    for segment in jp_chars:
        for i in range(len(segment) - 1):
            tokens.append(segment[i : i + 2])
        if len(segment) == 1:
            tokens.append(segment)
    return tokens


class VectorMemory:
    """TF-IDF ベースの軽量ベクトル記憶"""

    def __init__(self, path: str = "data/vector_memory.json"):
        self.path = path
        self._entries: list[dict] = []  # {"text": str, "topic": str, "tokens": list}
        self._idf_cache: dict[str, float] = {}
        self._dirty = False
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._entries = data.get("entries", [])
                self._rebuild_idf()
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        data = {"entries": self._entries}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._dirty = False

    def _rebuild_idf(self):
        """IDF（逆文書頻度）を再計算"""
        n = len(self._entries)
        if n == 0:
            self._idf_cache = {}
            return
        doc_freq: Counter = Counter()
        for entry in self._entries:
            unique_tokens = set(entry.get("tokens", []))
            for token in unique_tokens:
                doc_freq[token] += 1
        self._idf_cache = {
            token: math.log((n + 1) / (df + 1)) + 1
            for token, df in doc_freq.items()
        }

    def _tfidf_vector(self, tokens: list[str]) -> dict[str, float]:
        """トークンリストから TF-IDF ベクトルを生成"""
        tf = Counter(tokens)
        total = len(tokens) if tokens else 1
        vec = {}
        for token, count in tf.items():
            idf = self._idf_cache.get(token, 1.0)
            vec[token] = (count / total) * idf
        return vec

    @staticmethod
    def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
        """2つのスパースベクトルのコサイン類似度"""
        common = set(vec_a) & set(vec_b)
        if not common:
            return 0.0
        dot = sum(vec_a[k] * vec_b[k] for k in common)
        norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
        norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def store(self, text: str, topic: str = "general"):
        """テキストをベクトル化して記憶に追加"""
        # 重複チェック
        for entry in self._entries:
            if entry["text"] == text:
                return

        tokens = _tokenize(text)
        self._entries.append({
            "text": text,
            "topic": topic,
            "tokens": tokens,
        })

        # エントリ数の上限（メモリ効率）
        if len(self._entries) > 1000:
            self._entries = self._entries[-1000:]

        self._rebuild_idf()
        self._save()

    def search(self, query: str, limit: int = 5, min_score: float = 0.05) -> list[dict]:
        """クエリに類似した記憶を検索

        Returns: [{"text": str, "topic": str, "score": float}, ...]
        """
        if not self._entries:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        query_vec = self._tfidf_vector(query_tokens)

        scored = []
        for entry in self._entries:
            entry_vec = self._tfidf_vector(entry.get("tokens", []))
            score = self._cosine_similarity(query_vec, entry_vec)
            if score >= min_score:
                scored.append({
                    "text": entry["text"],
                    "topic": entry["topic"],
                    "score": round(score, 4),
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def count(self) -> int:
        return len(self._entries)

    def topics(self) -> list[str]:
        return list({e["topic"] for e in self._entries})
