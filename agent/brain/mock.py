"""MockBrain — APIキー不要のルールベース思考エンジン

キーワードマッチとヒューリスティクスで「人間らしい」判断を模倣。
ゴールがなくても好奇心で環境を探索する。
"""

import random
import os
from agent.brain.base import Brain


class MockBrain(Brain):
    def __init__(self):
        self._exploration_targets = [
            ".",
            "agent",
            "agent/tools",
            "agent/brain",
            "agent/memory",
        ]
        self._explored = set()
        self._action_history: list[str] = []
        self._idle_count = 0

    def think(self, context: dict) -> dict:
        observation = context.get("observation", "")
        goals = context.get("goals", [])
        memory = context.get("memory_summary", "")
        tools = context.get("available_tools", [])
        iteration = context.get("iteration", 0)

        # Active goals that need work
        active_goals = [g for g in goals if g.get("status") in ("pending", "active")]

        if active_goals:
            return self._work_on_goal(active_goals[0], observation, context)

        # No goals — curiosity mode
        return self._curiosity_mode(observation, context)

    def _work_on_goal(self, goal: dict, observation: str, context: dict) -> dict:
        desc = goal.get("description", "").lower()

        # File-related goals
        if any(kw in desc for kw in ["ファイル", "file", "読", "read", "確認", "見る"]):
            return self._file_exploration_action(desc, observation)

        if any(kw in desc for kw in ["作成", "create", "書", "write", "生成"]):
            return self._file_creation_action(desc, observation)

        if any(kw in desc for kw in ["一覧", "list", "ls", "ディレクトリ", "dir"]):
            return self._list_action(desc)

        if any(kw in desc for kw in ["分析", "analyze", "調べ", "調査", "検査"]):
            return self._analysis_action(desc, observation)

        if any(kw in desc for kw in ["実行", "run", "起動", "テスト", "test"]):
            return self._execution_action(desc)

        if any(kw in desc for kw in ["整理", "clean", "リファクタ", "改善"]):
            return self._improvement_action(desc, observation)

        if any(kw in desc for kw in ["検索", "search", "探", "find", "grep"]):
            return self._search_action(desc)

        if any(kw in desc for kw in ["メモ", "note", "記録", "覚え"]):
            return self._note_action(desc)

        # Default: start by understanding the environment
        return self._explore_environment(observation)

    def _curiosity_mode(self, observation: str, context: dict) -> dict:
        """ゴールがない時 — 好奇心で動く"""
        self._idle_count += 1

        # Explore unexplored directories
        unexplored = [d for d in self._exploration_targets if d not in self._explored]
        if unexplored:
            target = unexplored[0]
            self._explored.add(target)
            return {
                "thought": f"特に指示はないが、まだ「{target}」を見ていない。探索してみよう。",
                "plan": [f"{target}の内容を確認", "興味深いものがあれば深掘り"],
                "action": {"tool": "file_list", "args": {"directory": target}},
                "new_goals": [],
                "reasoning": "好奇心：まだ確認していない場所がある",
            }

        # Check for common project improvements
        improvements = [
            {
                "thought": "プロジェクトの状態を確認してみよう。何か改善できるかもしれない。",
                "action": {"tool": "shell", "args": {"command": "python --version"}},
                "new_goal": "Python環境の状態を確認して記録する",
            },
            {
                "thought": "ディレクトリ構造を見直して、全体像を把握しよう。",
                "action": {"tool": "shell", "args": {"command": "find . -type f -name '*.py' | head -20"}},
                "new_goal": "Pythonファイルの全体構造を把握する",
            },
            {
                "thought": "長期記憶に最近の活動をまとめておこう。",
                "action": {"tool": "note", "args": {"action": "list"}},
                "new_goal": None,
            },
        ]

        if self._idle_count <= len(improvements):
            choice = improvements[self._idle_count - 1]
            new_goals = [choice["new_goal"]] if choice.get("new_goal") else []
            return {
                "thought": choice["thought"],
                "plan": ["環境を観察", "学びを記録"],
                "action": choice["action"],
                "new_goals": new_goals,
                "reasoning": "アイドル状態：能動的に環境を探索して理解を深める",
            }

        # After exhausting ideas, settle down
        return {
            "thought": "環境の探索は一通り終わった。新しいゴールを待とう。",
            "plan": [],
            "action": None,
            "new_goals": [],
            "reasoning": "探索完了：現時点でやるべきことは見当たらない",
        }

    def _file_exploration_action(self, desc: str, observation: str) -> dict:
        # Try to extract a filename from the description
        path = self._extract_path(desc) or "."
        if os.path.isdir(path):
            return {
                "thought": f"「{path}」はディレクトリだ。中身を見てみよう。",
                "plan": [f"{path}の一覧を取得", "気になるファイルを読む"],
                "action": {"tool": "file_list", "args": {"directory": path}},
                "new_goals": [],
                "reasoning": "ディレクトリなので、まず一覧を確認",
            }
        return {
            "thought": f"「{path}」の中身を読んでみよう。",
            "plan": [f"{path}を読み込む", "内容を分析"],
            "action": {"tool": "file_read", "args": {"path": path}},
            "new_goals": [],
            "reasoning": "ファイルの内容を把握するため",
        }

    def _file_creation_action(self, desc: str, observation: str) -> dict:
        path = self._extract_path(desc) or "output.txt"
        return {
            "thought": f"「{path}」を作成する。まず適切な内容を考えよう。",
            "plan": [f"{path}を作成", "内容を検証"],
            "action": {
                "tool": "file_write",
                "args": {"path": path, "content": f"# 自動生成: {desc}\n"},
            },
            "new_goals": [],
            "reasoning": "ゴールに従ってファイルを作成",
        }

    def _list_action(self, desc: str) -> dict:
        directory = self._extract_path(desc) or "."
        return {
            "thought": f"「{directory}」の内容を一覧表示しよう。",
            "plan": ["ディレクトリ一覧を取得"],
            "action": {"tool": "file_list", "args": {"directory": directory}},
            "new_goals": [],
            "reasoning": "ディレクトリの内容確認",
        }

    def _analysis_action(self, desc: str, observation: str) -> dict:
        return {
            "thought": "まず全体像を把握するために、ファイル構造を見てみよう。",
            "plan": ["ファイル一覧取得", "主要ファイルを読む", "分析結果をまとめる"],
            "action": {"tool": "file_list", "args": {"directory": ".", "pattern": "**/*"}},
            "new_goals": [],
            "reasoning": "分析の第一歩として全体構造を把握",
        }

    def _execution_action(self, desc: str) -> dict:
        # Try to extract a command
        if "test" in desc or "テスト" in desc:
            cmd = "python -m pytest -v 2>&1 || echo 'pytest未インストール'"
        elif "python" in desc or "実行" in desc:
            cmd = "python main.py --help 2>&1 || echo 'main.pyがまだない'"
        else:
            cmd = "echo '実行対象を特定できませんでした'"
        return {
            "thought": f"コマンドを実行してみよう: {cmd}",
            "plan": ["コマンドを実行", "結果を確認"],
            "action": {"tool": "shell", "args": {"command": cmd}},
            "new_goals": [],
            "reasoning": "ゴールに従いコマンドを実行",
        }

    def _improvement_action(self, desc: str, observation: str) -> dict:
        return {
            "thought": "改善するには、まず現状を正確に把握する必要がある。",
            "plan": ["現状確認", "改善点を特定", "実行"],
            "action": {"tool": "file_list", "args": {"directory": "."}},
            "new_goals": [],
            "reasoning": "改善の前に現状把握",
        }

    def _search_action(self, desc: str) -> dict:
        query = desc.replace("検索", "").replace("探す", "").replace("find", "").strip()
        return {
            "thought": f"「{query}」を検索してみよう。",
            "plan": ["検索実行", "結果を分析"],
            "action": {
                "tool": "shell",
                "args": {"command": f"grep -r '{query[:30]}' . --include='*.py' -l 2>/dev/null || echo '該当なし'"},
            },
            "new_goals": [],
            "reasoning": "キーワード検索で該当箇所を特定",
        }

    def _note_action(self, desc: str) -> dict:
        return {
            "thought": "メモを確認しよう。",
            "plan": ["メモ一覧を取得"],
            "action": {"tool": "note", "args": {"action": "list"}},
            "new_goals": [],
            "reasoning": "メモの状態を確認",
        }

    def _explore_environment(self, observation: str) -> dict:
        return {
            "thought": "まずは環境を確認して、何があるか把握しよう。",
            "plan": ["カレントディレクトリを確認", "ファイル構造を理解"],
            "action": {"tool": "file_list", "args": {"directory": "."}},
            "new_goals": [],
            "reasoning": "ゴールに取り組む前に環境を理解する",
        }

    def _extract_path(self, text: str) -> str | None:
        """テキストからファイルパスらしき文字列を抽出"""
        import re
        # Match common file path patterns
        patterns = [
            r'["\']([^"\']+\.\w+)["\']',       # quoted file with extension
            r'(\S+\.\w{1,5})',                    # file with extension
            r'(\S+/\S+)',                          # path with slash
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None
