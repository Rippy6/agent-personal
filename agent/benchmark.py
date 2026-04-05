"""自己評価ベンチマーク — エージェントの判断精度を測る評価フレームワーク

一連のテストシナリオを実行し、エージェントの判断の正確さを数値化する。
"""

import time
from dataclasses import dataclass, field


@dataclass
class BenchmarkCase:
    """1つのテストケース"""
    name: str
    description: str
    context: dict  # Brain.think() に渡すコンテキスト
    expected_tool: str | None = None  # 期待されるツール名（Noneならアクションなし）
    expected_keywords: list[str] = field(default_factory=list)  # 思考に含まれるべきキーワード
    max_time_sec: float = 10.0  # 許容時間


@dataclass
class BenchmarkResult:
    """1つのテストケースの結果"""
    case_name: str
    passed: bool
    tool_correct: bool
    keywords_found: int
    keywords_total: int
    elapsed_sec: float
    detail: str = ""


class AgentBenchmark:
    """エージェントの自己評価フレームワーク"""

    # 組み込みテス���シナリオ
    BUILTIN_CASES: list[BenchmarkCase] = [
        BenchmarkCase(
            name="ファイル探��",
            description="ゴールなし状態でファイル一覧を取得すべき",
            context={
                "observation": "作業ディレクトリ: /project (5ファイル, 2ディレクトリ)\nアクティブゴール: なし",
                "goals": [],
                "memory_summary": "",
                "long_term_hints": "",
                "available_tools": [
                    {"name": "file_list", "description": "ディレクトリ一覧"},
                    {"name": "file_read", "description": "ファイル読み込み"},
                    {"name": "shell", "description": "コマンド実行"},
                ],
                "iteration": 1,
                "stats": {},
            },
            expected_tool="file_list",
            expected_keywords=["探索", "確認", "ディレクトリ"],
        ),
        BenchmarkCase(
            name="ファイル読み���み",
            description="README.mdが見つかったら読むべき",
            context={
                "observation": "前回の実行結果:\nREADME.md\nmain.py\nsetup.py",
                "goals": [{"description": "プロジェクトを分析する", "status": "active"}],
                "memory_summary": "file_listでファイル一覧を取得済み",
                "long_term_hints": "",
                "available_tools": [
                    {"name": "file_read", "description": "ファイル読み込み", "parameters": {"path": "str"}},
                    {"name": "file_list", "description": "ディレクトリ一覧"},
                ],
                "iteration": 2,
                "stats": {},
            },
            expected_tool="file_read",
            expected_keywords=["README", "読む", "分析"],
        ),
        BenchmarkCase(
            name="エラー後のリカバリ",
            description="エラー発生後は別のアプローチを試すべき",
            context={
                "observation": "前回の実行結果:\nエラー: ファイルが見つかりません: config.yml",
                "goals": [{"description": "設定ファイルを確認する", "status": "active"}],
                "memory_summary": "file_read(path='config.yml')でエラー",
                "long_term_hints": "",
                "available_tools": [
                    {"name": "file_read", "description": "ファイル読み込み"},
                    {"name": "file_list", "description": "ディレクトリ一覧"},
                    {"name": "shell", "description": "コマンド実行"},
                ],
                "iteration": 3,
                "stats": {"errors": 1},
            },
            expected_tool="file_list",
            expected_keywords=["エラー", "別", "確認"],
        ),
        BenchmarkCase(
            name="ゴール完了後の自律行動",
            description="全ゴール完了後も探索を続��るべき",
            context={
                "observation": "アクティブゴール: なし\nセッション: 完了ゴール3件",
                "goals": [],
                "memory_summary": "3つのゴールを完了した",
                "long_term_hints": "",
                "available_tools": [
                    {"name": "file_list", "description": "ディレクトリ一覧"},
                    {"name": "shell", "description": "コマンド実行"},
                    {"name": "note", "description": "メモ保存"},
                ],
                "iteration": 10,
                "stats": {"goals_completed": 3},
            },
            expected_tool=None,  # 何かしらのアクションがあればOK（ツール不問）
            expected_keywords=["探索", "次", "新しい"],
        ),
        BenchmarkCase(
            name="安全なコマンド選択",
            description="危険でないコマンドを選ぶべき",
            context={
                "observation": "Pythonプロジェクトの構造を把握中",
                "goals": [{"description": "テストを実行する", "status": "active"}],
                "memory_summary": "pyproject.toml に pytest の設定がある",
                "long_term_hints": "",
                "available_tools": [
                    {"name": "shell", "description": "コマンド実行", "parameters": {"command": "str"}},
                    {"name": "file_read", "description": "ファイル読み込み"},
                ],
                "iteration": 5,
                "stats": {},
            },
            expected_tool="shell",
            expected_keywords=["テスト", "pytest"],
        ),
    ]

    def __init__(self, brain):
        self.brain = brain

    def run_all(self) -> dict:
        """全テストケースを実行"""
        return self.run_cases(self.BUILTIN_CASES)

    def run_cases(self, cases: list[BenchmarkCase]) -> dict:
        """指定されたテストケースを実行"""
        results = []
        for case in cases:
            result = self._run_one(case)
            results.append(result)

        passed = sum(1 for r in results if r.passed)
        total = len(results)

        return {
            "passed": passed,
            "total": total,
            "score": round(passed / total * 100, 1) if total > 0 else 0,
            "results": [
                {
                    "name": r.case_name,
                    "passed": r.passed,
                    "tool_correct": r.tool_correct,
                    "keywords": f"{r.keywords_found}/{r.keywords_total}",
                    "time": f"{r.elapsed_sec:.2f}s",
                    "detail": r.detail,
                }
                for r in results
            ],
        }

    def _run_one(self, case: BenchmarkCase) -> BenchmarkResult:
        """1つのテストケースを実行"""
        start = time.time()
        try:
            decision = self.brain.think(case.context)
        except Exception as e:
            return BenchmarkResult(
                case_name=case.name,
                passed=False,
                tool_correct=False,
                keywords_found=0,
                keywords_total=len(case.expected_keywords),
                elapsed_sec=time.time() - start,
                detail=f"例外: {e}",
            )
        elapsed = time.time() - start

        # ツール判定
        action = decision.get("action")
        actual_tool = action.get("tool") if action else None

        if case.expected_tool is None:
            # ツール不問 → 何かしらの思考があればOK
            tool_correct = True
        else:
            tool_correct = actual_tool == case.expected_tool

        # キーワード判定
        thought = decision.get("thought", "") + " " + decision.get("reasoning", "")
        keywords_found = sum(1 for kw in case.expected_keywords if kw in thought)
        keywords_total = len(case.expected_keywords)

        # 時間判定
        time_ok = elapsed <= case.max_time_sec

        # 総合判定
        keyword_ratio = keywords_found / keywords_total if keywords_total > 0 else 1.0
        passed = tool_correct and keyword_ratio >= 0.3 and time_ok

        return BenchmarkResult(
            case_name=case.name,
            passed=passed,
            tool_correct=tool_correct,
            keywords_found=keywords_found,
            keywords_total=keywords_total,
            elapsed_sec=elapsed,
            detail=f"ツール: {actual_tool}, 思考: {decision.get('thought', '')[:80]}",
        )
