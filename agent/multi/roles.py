"""ロールベースエージェント — 役割に特化したエージェント定義

各ロールは専用のシステムプロンプトとツールセットを持つ。
"""

from dataclasses import dataclass, field


@dataclass
class AgentRole:
    """エージェントの役割定義"""
    name: str
    description: str
    system_prompt: str
    allowed_tools: list[str] = field(default_factory=list)  # 空 = 全ツール利用可
    priority_keywords: list[str] = field(default_factory=list)  # この役割が得意なキーワード

    def matches(self, task_description: str) -> float:
        """タスクとの適合度を計算（0.0〜1.0）"""
        if not self.priority_keywords:
            return 0.5  # キーワード未設定 = 汎用
        desc_lower = task_description.lower()
        matches = sum(1 for kw in self.priority_keywords if kw in desc_lower)
        return min(matches / max(len(self.priority_keywords), 1), 1.0)


# 組み込みロール定義
BUILTIN_ROLES: dict[str, AgentRole] = {
    "researcher": AgentRole(
        name="Researcher",
        description="情報収集・調査に特化。ファイルやWebを読み、知識をまとめる。",
        system_prompt="あなたは調査専門のエージェントです。情報を収集し、分析し、わかりやすくまとめてください。",
        allowed_tools=["file_read", "file_list", "web_fetch", "note", "shell"],
        priority_keywords=["調査", "調べる", "分析", "読む", "確認", "research", "analyze", "investigate"],
    ),
    "coder": AgentRole(
        name="Coder",
        description="コーディングに特化。ファイルの作成・修正・テストを行う。",
        system_prompt="あなたはコーディング専門のエージェントです。コードを書き、テストし、品質を保ってください。",
        allowed_tools=["file_read", "file_write", "file_list", "shell"],
        priority_keywords=["コード", "実装", "修正", "バグ", "テスト", "code", "implement", "fix", "bug", "test"],
    ),
    "reviewer": AgentRole(
        name="Reviewer",
        description="レビューに特化。コードや文書の品質チェック・改善提案を行う。",
        system_prompt="あなたはレビュー専門のエージェントです。品質問題を発見し、具体的な改善案を提示してください。",
        allowed_tools=["file_read", "file_list", "note"],
        priority_keywords=["レビュー", "チェック", "品質", "改善", "review", "check", "quality", "improve"],
    ),
    "writer": AgentRole(
        name="Writer",
        description="文書作成に特化。ドキュメント・README・レポートを書く。",
        system_prompt="あなたは文書作成専門のエージェントです。わかりやすく、読みやすいドキュメントを作成してください。",
        allowed_tools=["file_read", "file_write", "file_list", "note"],
        priority_keywords=["ドキュメント", "README", "書く", "レポート", "説明", "document", "write", "report"],
    ),
    "ops": AgentRole(
        name="Ops",
        description="運用・DevOpsに特化。環境構築・デプロイ・監視を行う。",
        system_prompt="あなたは運用専門のエージェントです。環境を構築し、安定的に動作するよう管理してください。",
        allowed_tools=["shell", "file_read", "file_write", "file_list"],
        priority_keywords=["デプロイ", "環境", "設定", "サーバー", "Docker", "deploy", "setup", "config", "server"],
    ),
}


def find_best_role(task_description: str, roles: dict[str, AgentRole] | None = None) -> str:
    """タスクに最適なロールを返す"""
    roles = roles or BUILTIN_ROLES
    best_role = "researcher"  # デフォルト
    best_score = 0.0
    for role_id, role in roles.items():
        score = role.matches(task_description)
        if score > best_score:
            best_score = score
            best_role = role_id
    return best_role
