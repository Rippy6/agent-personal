"""Brain抽象インターフェース — 思考エンジンの基底クラス"""

from abc import ABC, abstractmethod


class Brain(ABC):
    @abstractmethod
    def think(self, context: dict) -> dict:
        """
        コンテキストを受け取り、判断を返す。

        context = {
            "observation": str,       # 現在の観察結果
            "goals": list[dict],      # 現在のゴール一覧
            "memory_summary": str,    # 短期記憶サマリー
            "long_term_hints": str,   # 長期記憶から関連情報
            "available_tools": list,  # 利用可能なツール一覧
            "iteration": int,         # 現在のループ回数
        }

        returns = {
            "thought": str,           # 内部思考（コンソールに表示）
            "plan": list[str],        # 計画ステップ
            "action": {               # 実行するアクション
                "tool": str,          #   ツール名
                "args": dict,         #   引数
            } | None,
            "new_goals": list[str],   # 新たに発見したゴール（あれば）
            "reasoning": str,         # 判断の理由
        }
        """
        ...
