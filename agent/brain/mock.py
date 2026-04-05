"""MockBrain — APIキー不要のルールベース思考エンジン

ゴールがなくても好奇心で環境を探索し、改善点を発見し、
自分でゴールを生成する「生きたエージェント」を模倣する。
"""

import os
import random
from agent.brain.base import Brain


# ゴールのキーワードに対する行動マッピング
GOAL_KEYWORDS = {
    "file_explore": {
        "keywords": ["ファイル", "file", "読", "read", "確認", "見る", "内容"],
        "thought_template": "「{target}」の内容を確認しよう。",
        "default_tool": "file_list",
    },
    "create": {
        "keywords": ["作成", "create", "書", "write", "生成", "追加"],
        "thought_template": "新しいファイルを作成する。",
        "default_tool": "file_write",
    },
    "list": {
        "keywords": ["一覧", "list", "ls", "ディレクトリ", "dir", "構造"],
        "thought_template": "ディレクトリの内容を一覧表示しよう。",
        "default_tool": "file_list",
    },
    "analyze": {
        "keywords": ["分析", "analyze", "調べ", "調査", "検査", "レビュー", "review"],
        "thought_template": "まず全体像を把握するために構造を見よう。",
        "default_tool": "file_list",
    },
    "execute": {
        "keywords": ["実行", "run", "起動", "テスト", "test", "ビルド", "build"],
        "thought_template": "コマンドを実行してみよう。",
        "default_tool": "shell",
    },
    "improve": {
        "keywords": ["整理", "clean", "リファクタ", "改善", "optimize", "修正", "fix"],
        "thought_template": "改善するには、まず現状を正確に把握する必要がある。",
        "default_tool": "file_list",
    },
    "search": {
        "keywords": ["検索", "search", "探", "find", "grep"],
        "thought_template": "該当箇所を検索してみよう。",
        "default_tool": "shell",
    },
    "note": {
        "keywords": ["メモ", "note", "記録", "覚え"],
        "thought_template": "メモを確認しよう。",
        "default_tool": "note",
    },
}

# 好奇心モードで生成するゴール候補
CURIOSITY_GOALS = [
    "プロジェクトのファイル構造を把握して長期記憶に記録する",
    "主要なPythonファイルの内容を読んで理解する",
    "READMEの内容を確認して改善点がないか探す",
    "テストが存在するか確認し、あればテストを実行する",
    "pyproject.tomlを確認してプロジェクトの設定を理解する",
    "最近変更されたファイルを確認する",
    "プロジェクトの依存関係を確認する",
    ".gitignoreの内容を確認して適切か評価する",
    "コードの品質をチェックする（lintエラーなど）",
    "ドキュメントが最新かどうか確認する",
]


class MockBrain(Brain):
    """ルールベース思考エンジン — 好奇心を持ち、自律的にゴールを生成する"""

    def __init__(self):
        self._explored_dirs: set[str] = set()
        self._explored_files: set[str] = set()
        self._action_history: list[str] = []
        self._curiosity_index = 0
        self._consecutive_idle = 0

    def think(self, context: dict) -> dict:
        observation = context.get("observation", "")
        goals = context.get("goals", [])
        iteration = context.get("iteration", 0)

        active_goals = [g for g in goals if g.get("status") in ("pending", "active")]

        if active_goals:
            self._consecutive_idle = 0
            return self._work_on_goal(active_goals[0], observation, context)

        # ゴールなし → 自分でゴールを生成して動く
        return self._autonomous_mode(observation, context)

    def _work_on_goal(self, goal: dict, observation: str, context: dict) -> dict:
        """アクティブなゴールに取り組む"""
        desc = goal.get("description", "").lower()

        for category, config in GOAL_KEYWORDS.items():
            if any(kw in desc for kw in config["keywords"]):
                return self._dispatch_goal_action(category, desc, observation, context)

        # マッチしないゴール → まず環境を調べる
        return self._explore_for_goal(desc, observation)

    def _dispatch_goal_action(self, category: str, desc: str, obs: str, ctx: dict) -> dict:
        """カテゴリに応じたアクションを生成"""
        config = GOAL_KEYWORDS[category]

        if category == "file_explore":
            path = self._extract_path(desc) or "."
            if os.path.isdir(path):
                return self._make_decision(
                    thought=f"「{path}」はディレクトリだ。中身を見てみよう。",
                    plan=[f"{path}の一覧を取得", "気になるファイルを読む"],
                    tool="file_list",
                    args={"directory": path},
                )
            return self._make_decision(
                thought=f"「{path}」の中身を読んでみよう。",
                plan=[f"{path}を読み込む", "内容を分析"],
                tool="file_read",
                args={"path": path},
            )

        if category == "create":
            path = self._extract_path(desc) or "output.txt"
            return self._make_decision(
                thought=f"「{path}」を作成する。",
                plan=[f"{path}を作成", "内容を検証"],
                tool="file_write",
                args={"path": path, "content": f"# {desc}\n"},
            )

        if category == "list":
            directory = self._extract_path(desc) or "."
            return self._make_decision(
                thought=f"「{directory}」の内容を一覧表示しよう。",
                plan=["ディレクトリ一覧を取得"],
                tool="file_list",
                args={"directory": directory},
            )

        if category == "analyze":
            # 前回の結果にファイルリストがあれば、次は読む
            last = self._get_last_result_summary(ctx)
            if last and "📄" in last:
                target = self._find_interesting_file(last)
                if target:
                    return self._make_decision(
                        thought=f"「{target}」が気になる。中身を読んでみよう。",
                        plan=[f"{target}を読む", "分析結果をまとめる"],
                        tool="file_read",
                        args={"path": target},
                    )
            return self._make_decision(
                thought="まず全体像を把握しよう。ファイル構造を確認する。",
                plan=["ファイル一覧取得", "主要ファイルを読む", "分析結果をまとめる"],
                tool="file_list",
                args={"directory": ".", "pattern": "*"},
            )

        if category == "execute":
            if "test" in desc or "テスト" in desc:
                cmd = "python -m pytest -v 2>&1 || echo 'pytest未インストール'"
            elif "build" in desc or "ビルド" in desc:
                cmd = "python -m build 2>&1 || echo 'buildツール未インストール'"
            else:
                cmd = "python main.py --help 2>&1"
            return self._make_decision(
                thought=f"コマンドを実行してみよう: {cmd}",
                plan=["コマンドを実行", "結果を確認"],
                tool="shell",
                args={"command": cmd},
            )

        if category == "improve":
            return self._make_decision(
                thought="改善するには、まず現状を把握する必要がある。",
                plan=["現状確認", "改善点を特定", "実行"],
                tool="file_list",
                args={"directory": "."},
            )

        if category == "search":
            query = desc.replace("検索", "").replace("探す", "").strip()[:30]
            return self._make_decision(
                thought=f"「{query}」を検索してみよう。",
                plan=["検索実行", "結果を分析"],
                tool="shell",
                args={"command": f"grep -r '{query}' . --include='*.py' -l 2>/dev/null || echo '該当なし'"},
            )

        if category == "note":
            return self._make_decision(
                thought="メモを確認しよう。",
                plan=["メモ一覧を取得"],
                tool="note",
                args={"action": "list"},
            )

        return self._explore_for_goal(desc, obs)

    def _autonomous_mode(self, observation: str, context: dict) -> dict:
        """ゴールがない時 — 自分でやるべきことを見つける"""
        self._consecutive_idle += 1

        # Phase 1: 未探索ディレクトリがあれば探索
        unexplored = self._find_unexplored_directory()
        if unexplored:
            self._explored_dirs.add(unexplored)
            return self._make_decision(
                thought=f"まだ「{unexplored}」を見ていない。探索してみよう。",
                plan=[f"{unexplored}の内容を確認", "興味深いものがあれば深掘り"],
                tool="file_list",
                args={"directory": unexplored},
                new_goals=self._suggest_exploration_goals(unexplored),
            )

        # Phase 2: 前回の結果から気になるファイルを深掘り
        last = self._get_last_result_summary(context)
        if last and "📄" in last and self._consecutive_idle < 5:
            target = self._find_interesting_file(last)
            if target and target not in self._explored_files:
                self._explored_files.add(target)
                return self._make_decision(
                    thought=f"「{target}」が気になる。中身を読んで理解を深めよう。",
                    plan=[f"{target}を読む", "内容を記憶に保存"],
                    tool="file_read",
                    args={"path": target},
                )

        # Phase 3: 好奇心ゴールを生成
        if self._curiosity_index < len(CURIOSITY_GOALS):
            goal = CURIOSITY_GOALS[self._curiosity_index]
            self._curiosity_index += 1
            return self._make_decision(
                thought=f"次にやるべきことを考えた。「{goal}」に取り組もう。",
                plan=["新しいゴールを設定", "取り組み開始"],
                tool=None,
                args={},
                new_goals=[goal],
            )

        # Phase 4: ランダムな改善活動
        activities = [
            {
                "thought": "プロジェクトの健康状態を確認しよう。",
                "tool": "shell",
                "args": {"command": "python -m pytest tests/ -v --tb=short 2>&1 | tail -20"},
                "goal": "テスト結果を確認して、失敗があれば修正する",
            },
            {
                "thought": "ファイルサイズの大きいものがないか確認しよう。",
                "tool": "shell",
                "args": {"command": "find . -name '*.py' -exec wc -l {} + 2>/dev/null | sort -n | tail -10"},
                "goal": "大きなファイルがあればリファクタリングを検討する",
            },
            {
                "thought": "最近の変更を確認しよう。",
                "tool": "shell",
                "args": {"command": "git log --oneline -10 2>/dev/null || echo 'git未初期化'"},
                "goal": None,
            },
            {
                "thought": "長期記憶に保存した情報をまとめ直そう。",
                "tool": "note",
                "args": {"action": "list"},
                "goal": None,
            },
            {
                "thought": "Python環境の状態を確認しておこう。",
                "tool": "shell",
                "args": {"command": "python --version && pip list --format=columns 2>/dev/null | head -20"},
                "goal": None,
            },
        ]

        if self._consecutive_idle <= len(activities):
            activity = activities[(self._consecutive_idle - 1) % len(activities)]
            new_goals = [activity["goal"]] if activity.get("goal") else []
            return self._make_decision(
                thought=activity["thought"],
                plan=["環境を観察", "学びを記録"],
                tool=activity["tool"],
                args=activity["args"],
                new_goals=new_goals,
            )

        # Phase 5: 探索サイクルをリセットして最初から
        self._explored_dirs.clear()
        self._explored_files.clear()
        self._curiosity_index = 0
        self._consecutive_idle = 0
        return self._make_decision(
            thought="一通り探索した。視点を変えて、もう一度環境を見直してみよう。",
            plan=["探索をリセット", "新しい視点で観察"],
            tool="file_list",
            args={"directory": "."},
            reasoning="探索サイクルのリセット — 新しい発見があるかもしれない",
        )

    def _find_unexplored_directory(self) -> str | None:
        """未探索のディレクトリを見つける"""
        candidates = ["."]
        try:
            for entry in os.listdir("."):
                if os.path.isdir(entry) and not entry.startswith((".", "__")):
                    candidates.append(entry)
                    for sub in os.listdir(entry):
                        sub_path = os.path.join(entry, sub)
                        if os.path.isdir(sub_path) and not sub.startswith((".", "__")):
                            candidates.append(sub_path)
        except OSError:
            pass

        for d in candidates:
            if d not in self._explored_dirs:
                return d
        return None

    def _find_interesting_file(self, last_result: str) -> str | None:
        """前回の結果から興味深いファイルを選ぶ"""
        interesting_extensions = [".py", ".md", ".toml", ".yml", ".yaml", ".json", ".txt"]
        for line in last_result.split("\n"):
            if "📄" in line:
                # Extract file path
                parts = line.strip().split()
                for part in parts:
                    if any(part.endswith(ext) for ext in interesting_extensions):
                        clean = part.strip("📄 ()")
                        if clean and clean not in self._explored_files:
                            return clean
        return None

    def _suggest_exploration_goals(self, directory: str) -> list[str]:
        """ディレクトリ探索から新しいゴールを提案"""
        if directory == ".":
            return []
        if "test" in directory.lower():
            return ["テストを実行して結果を確認する"]
        if "doc" in directory.lower():
            return ["ドキュメントの内容を確認して最新か検証する"]
        return []

    def _explore_for_goal(self, desc: str, observation: str) -> dict:
        """ゴールに取り組むため、まず環境を調べる"""
        return self._make_decision(
            thought=f"「{desc[:50]}」に取り組むため、まず環境を確認しよう。",
            plan=["環境確認", "ファイル構造を理解"],
            tool="file_list",
            args={"directory": "."},
        )

    def _get_last_result_summary(self, context: dict) -> str | None:
        """コンテキストから前回の実行結果を取得"""
        obs = context.get("observation", "")
        if "前回の実行結果:" in obs:
            return obs.split("前回の実行結果:")[1][:500]
        return None

    @staticmethod
    def _make_decision(
        thought: str,
        plan: list[str],
        tool: str | None,
        args: dict | None = None,
        new_goals: list[str] | None = None,
        reasoning: str = "",
    ) -> dict:
        action = {"tool": tool, "args": args or {}} if tool else None
        return {
            "thought": thought,
            "plan": plan,
            "action": action,
            "new_goals": new_goals or [],
            "reasoning": reasoning or thought,
        }

    @staticmethod
    def _extract_path(text: str) -> str | None:
        """テキストからファイルパスらしき文字列を抽出"""
        import re
        patterns = [
            r'["\']([^"\']+\.\w+)["\']',
            r'(\S+\.\w{1,5})',
            r'(\S+/\S+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None
