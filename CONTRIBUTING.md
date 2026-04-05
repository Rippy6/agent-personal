# Contributing to agent-personal

agent-personal をより良くするために貢献してくれてありがとうございます！

## 貢献の方法

### バグ報告

1. まず [Issues](../../issues) で同じ報告がないか確認
2. なければ Bug Report テンプレートで新規Issue作成
3. 再現手順、期待する動作、実際の動作を書いてください

### 機能提案

1. [Issues](../../issues) で Feature Request テンプレートを使って提案
2. なぜその機能が必要か、どう使うかを説明してください

### プルリクエスト

1. リポジトリをFork
2. feature ブランチを作成: `git checkout -b feature/my-feature`
3. 変更をコミット: `git commit -m "feat: add my feature"`
4. テストを追加・実行: `python -m pytest`
5. Lint を通す: `python -m ruff check .`
6. Push して PR 作成

### プラグイン（ツール）の追加

新しいツールの追加は最も歓迎される貢献です！

1. `agent/tools/base.py` の `Tool` クラスを継承
2. `agent/tools/` に新しいファイルを作成
3. `name`, `description`, `parameters`, `execute()` を実装
4. テストを `tests/tools/` に追加
5. PR を送る

```python
# agent/tools/my_tool.py
from agent.tools.base import Tool

class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "ツールの説明"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "パラメータの説明"},
            },
            "required": ["param1"],
        }

    def execute(self, **kwargs) -> str:
        # 実装
        return "結果"
```

## コミットメッセージ規約

[Conventional Commits](https://www.conventionalcommits.org/) に従います:

- `feat:` 新機能
- `fix:` バグ修正
- `docs:` ドキュメント
- `test:` テスト
- `refactor:` リファクタリング
- `ci:` CI/CD
- `chore:` その他

## 開発環境セットアップ

```bash
git clone https://github.com/Rippy6/agent-personal.git
cd agent-personal
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest
```

## コードスタイル

- Python 3.11+
- [Ruff](https://github.com/astral-sh/ruff) でフォーマット・リント
- 型ヒント必須（public API）
- docstring は日本語 or 英語

## ライセンス

貢献したコードは [MIT License](LICENSE) の下でリリースされます。
