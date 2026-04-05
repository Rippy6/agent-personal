"""マルチステップ計画 — 複雑なゴールを自動でサブタスク木に分解

Brain に頼らず、キーワードベースのルールで分解する軽量版。
Brain 接続時はより高度な分解が可能。
"""

from agent.goal import GoalManager


# ゴール → サブタスク分解ルール
DECOMPOSITION_RULES: list[dict] = [
    {
        "keywords": ["分析", "analyze", "analysis"],
        "subtasks": [
            "対象の構造を確認する",
            "内容を詳しく読む",
            "問題点や改善点を列挙する",
            "分析結果をまとめる",
        ],
    },
    {
        "keywords": ["作成", "create", "生成", "write", "書く"],
        "subtasks": [
            "必要な情報を収集する",
            "構成を決める",
            "内容を作成する",
            "結果を確認・修正する",
        ],
    },
    {
        "keywords": ["修正", "fix", "バグ", "bug", "エラー", "error", "修復", "repair"],
        "subtasks": [
            "問題の原因を特定する",
            "修正方法を決める",
            "修正を実施する",
            "修正結果を検証する",
        ],
    },
    {
        "keywords": ["整理", "organize", "リファクタ", "refactor", "cleanup"],
        "subtasks": [
            "現状の構造を把握する",
            "改善ポイントを特定する",
            "段階的にリファクタリングする",
            "テストで品質を確認する",
        ],
    },
    {
        "keywords": ["テスト", "test", "検証", "verify"],
        "subtasks": [
            "テスト対象を特定する",
            "テストケースを設計する",
            "テストを実行する",
            "結果を評価する",
        ],
    },
    {
        "keywords": ["調査", "investigate", "調べる", "research", "リサーチ"],
        "subtasks": [
            "調査対象を明確にする",
            "関連情報を収集する",
            "情報を分析・整理する",
            "調査結果をまとめる",
        ],
    },
    {
        "keywords": ["設定", "setup", "configure", "インストール", "install", "セットアップ"],
        "subtasks": [
            "必要な前提条件を確認する",
            "設定を行う",
            "動作確認する",
        ],
    },
    {
        "keywords": ["改善", "improve", "最適化", "optimize"],
        "subtasks": [
            "現状のパフォーマンスを測定する",
            "ボトルネックを特定する",
            "改善策を実施する",
            "改善結果を測定・比較する",
        ],
    },
]


class Planner:
    """ゴールをサブタスクに自動分解するプランナー"""

    def __init__(self, goal_manager: GoalManager):
        self.goal_manager = goal_manager

    def decompose(self, goal_id: str) -> list[str]:
        """ゴールをサブタスクに分解し、GoalManager に登録する

        Returns: 作成されたサブタスクのID一覧
        """
        goal = self.goal_manager.get_goal(goal_id)
        if not goal:
            return []

        # 既にサブタスクがあれば分解しない
        if goal.subtasks:
            return goal.subtasks

        description = goal.description.lower()
        subtask_ids = []

        # ルールマッチ
        for rule in DECOMPOSITION_RULES:
            if any(kw in description for kw in rule["keywords"]):
                for i, subtask_desc in enumerate(rule["subtasks"]):
                    sub = self.goal_manager.add_goal(
                        description=f"{subtask_desc}（{goal.description}）",
                        parent_id=goal_id,
                        priority=goal.priority,
                    )
                    subtask_ids.append(sub.id)
                return subtask_ids

        # マッチしない場合 → 汎用的な3ステップ分解
        for desc in [
            f"情報を収集する（{goal.description}）",
            f"実行する（{goal.description}）",
            f"結果を確認する（{goal.description}）",
        ]:
            sub = self.goal_manager.add_goal(
                description=desc,
                parent_id=goal_id,
                priority=goal.priority,
            )
            subtask_ids.append(sub.id)

        return subtask_ids

    def should_decompose(self, goal_id: str) -> bool:
        """このゴールはサブタスクに分解すべきか"""
        goal = self.goal_manager.get_goal(goal_id)
        if not goal:
            return False
        if goal.subtasks:
            return False  # 既に分解済み
        # 短すぎる説明は分解不要
        if len(goal.description) < 8:
            return False
        # 複雑さの指標: キーワードが含まれているか
        desc = goal.description.lower()
        complex_keywords = [
            "分析", "analyze", "作成", "create", "修正", "fix", "整理",
            "organize", "テスト", "test", "調査", "investigate", "改善",
            "improve", "設定", "setup",
        ]
        return any(kw in desc for kw in complex_keywords)

    def get_execution_order(self, goal_id: str) -> list[str]:
        """サブタスクの実行順序を返す（未完了のもののみ）"""
        goal = self.goal_manager.get_goal(goal_id)
        if not goal or not goal.subtasks:
            return [goal_id] if goal else []

        ordered = []
        for sub_id in goal.subtasks:
            sub = self.goal_manager.get_goal(sub_id)
            if sub and sub.status in ("pending", "active"):
                ordered.append(sub_id)
        return ordered
