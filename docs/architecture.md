# Architecture / アーキテクチャ

## 全体像

```
┌──────────────────────────────────────────────────────────┐
│                        main.py (CLI)                      │
│          argparse → Brain選択 → Agent構築 → 実行          │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│                    Agent (core.py)                        │
│                                                          │
│   ┌─────────────────────────────────────────────────┐    │
│   │              自律ループ (5フェーズ)              │    │
│   │                                                 │    │
│   │  🔍 Observe ──→ 💭 Think ──→ 📋 Plan           │    │
│   │       ▲                          │              │    │
│   │       │                          ▼              │    │
│   │  📝 Reflect ◀── ⚡ Act ◀────────┘              │    │
│   └─────────────────────────────────────────────────┘    │
│                                                          │
│   依存コンポーネント:                                     │
│   ├── Brain (思考エンジン)                                │
│   ├── ToolRegistry (ツール群)                             │
│   ├── ShortTermMemory (短期記憶)                          │
│   ├── LongTermMemory (長期記憶)                           │
│   └── GoalManager (ゴール管理)                            │
└──────────────────────────────────────────────────────────┘
```

## コンポーネント詳細

### Brain (思考エンジン)

```
agent/brain/
├── base.py      ← Brain ABC: think(context) → decision
├── mock.py      ← MockBrain: ルールベース（APIキー不要）
└── claude.py    ← ClaudeBrain: Claude API呼び出し
```

**インターフェース**: `Brain.think(context: dict) -> dict`

入力 (context):
```python
{
    "observation": str,        # 現在の環境状態
    "goals": list[dict],       # アクティブなゴール一覧
    "memory_summary": str,     # 短期記憶のサマリー
    "long_term_hints": str,    # 長期記憶から関連情報
    "available_tools": list,   # 使えるツール一覧
    "iteration": int,          # ループ回数
}
```

出力 (decision):
```python
{
    "thought": str,            # 内部思考（表示用）
    "plan": list[str],         # 計画ステップ
    "action": {                # 実行アクション
        "tool": str,
        "args": dict,
    } | None,
    "new_goals": list[str],    # 新ゴール
    "reasoning": str,          # 判断理由
}
```

**新しいBrainの追加方法**:
1. `agent/brain/base.py` の `Brain` を継承
2. `think()` メソッドを実装
3. `main.py` で選択ロジックを追加

### ToolRegistry (ツール群)

```
agent/tools/
├── base.py       ← Tool ABC: name, description, parameters, execute()
├── registry.py   ← ToolRegistry: 登録・検索・実行・プラグイン読み込み
├── file_ops.py   ← FileRead/Write/List (パストラバーサル防止)
├── shell.py      ← ShellTool (多層セキュリティ)
├── web.py        ← WebFetchTool
└── notes.py      ← NoteTool (長期記憶連携)
```

**新しいツールの追加方法**:
1. `Tool` を継承したクラスを作成
2. `agent/tools/` に配置 → `discover()` で自動検出
3. または `load_plugin("path/to/tool.py")` で外部読み込み

### Memory (記憶)

```
agent/memory/
├── short_term.py  ← ShortTermMemory: deque(maxlen=50)
└── long_term.py   ← LongTermMemory: JSON永続化
```

**短期記憶**: セッション内のみ。最大50イベント保持。
**長期記憶**: `data/memory.json` に永続化。トピック別ファクト、学習パターン、ユーザー嗜好。

### GoalManager (ゴール管理)

```
agent/goal.py  ← GoalManager + Goal クラス
```

ツリー構造: 親ゴール → 子ゴール（サブタスク）。
子が全て完了すると親も自動完了。
`data/goals.json` に永続化。

## セキュリティアーキテクチャ

```
ユーザー入力
    │
    ▼
┌─────────────────┐
│ 入力バリデーション │ ← パス正規化、制御文字除去
└────────┬────────┘
         ▼
┌─────────────────┐
│ ブロックリスト照合 │ ← 危険パターンの検出
└────────┬────────┘
         ▼
┌─────────────────┐
│ サンドボックス確認 │ ← パストラバーサル防止、許可ディレクトリ
└────────┬────────┘
         ▼
┌─────────────────┐
│ 実行 + 監視      │ ← タイムアウト、出力サイズ制限
└────────┬────────┘
         ▼
┌─────────────────┐
│ 監査ログ         │ ← 実行履歴の記録
└─────────────────┘
```

## プラグインシステム

### 自動検出
```python
registry = ToolRegistry()
registry.discover()  # agent/tools/ 内の Tool サブクラスを自動登録
```

### 外部プラグイン読み込み
```python
registry.load_plugin("plugins/my_custom_tool.py")
```

### プラグインの作り方
```python
from agent.tools.base import Tool

class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "何をするツールか"

    def execute(self, **kwargs) -> str:
        return "結果"
```

## データフロー

```
起動 → config.json読み込み → Brain選択 → ツール構築
  │
  ▼
ゴール追加（CLI引数 or 対話入力 or 自己生成）
  │
  ▼
自律ループ開始
  │
  ├── Observe: os.listdir, goals, last_result → observation
  ├── Think:  Brain.think(context) → decision
  ├── Plan:   GoalManager.add_goal() → goal tree update
  ├── Act:    ToolRegistry.run() → result
  └── Reflect: 評価 → LongTermMemory.store() → goal update
  │
  ▼
ゴール完了 → 好奇心モード → 新ゴール生成 → ループ継続
```
