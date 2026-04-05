# Roadmap

agent-personal を世界で使われる巨大プロジェクトに育てるためのロードマップ。

## Phase 1: Foundation ✅

**目標**: 動くプロトタイプ + プロフェッショナルなOSS基盤

- [x] 5フェーズ自律ループ（観察→思考→計画→実行→振り返り）
- [x] MockBrain（APIキー不要のデモモード）
- [x] ClaudeBrain（Claude API接続）
- [x] ツール群（ファイル操作、シェル、Web、メモ）
- [x] 短期記憶 + 長期記憶（JSON永続化）
- [x] ゴール管理（ツリー構造、自動分解）
- [x] セキュリティ（パストラバーサル防止、コマンドインジェクション防止）
- [x] プラグインシステム（動的ツール読み込み）
- [x] テストスイート（74テスト）
- [x] CI/CD（GitHub Actions: lint + test + security scan）
- [x] OSS基盤（LICENSE, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT）

## Phase 2: Intelligence — より賢く ✅

**目標**: LLMの力を最大限活かした知的な自律行動

- [x] **マルチBrain対応**: OpenAI GPT, Google Gemini, ローカルLLM (Ollama)
- [x] **ベクトル記憶**: TF-IDFベースの軽量セマンティック検索（stdlib only）
- [x] **タスク学習**: 過去の成功パターンから行動を最適化
- [x] **マルチステップ計画**: 複雑なゴールを自動でサブタスク木に分解（8カテゴリ）
- [x] **自己評価ベンチマーク**: 5シナリオでBrainの判断精度を測定
- [x] **コンテキストウィンドウ最適化**: 優先度ベースの情報圧縮・選別

## Phase 3: Connectivity — 外の世界とつながる ✅

**目標**: メッセージアプリやAPIを通じて、どこからでもエージェントを操作

- [x] **Webhook API**: HTTPでゴール投入・状態取得・停止要求（HMAC署名検証）
- [x] **Slack連携**: Slackボットとしてチャンネルに常駐
- [x] **Discord連携**: Discordボットとしてサーバーに常駐
- [x] **Telegram連携**: Telegramボット（Long Polling）
- [x] **LINE連携**: LINE Messaging API
- [x] **GitHub連携**: Issue/PRの自動処理エージェント
- [x] **メール連携**: メール受信でゴール自動生成

## Phase 4: Multi-Agent — 複数の分身 ✅

**目標**: 複数のエージェントが協調して大きなタスクに取り組む

- [x] **エージェント間通信プロトコル**: MessageBus（スレッドセーフ）
- [x] **ロールベースエージェント**: Researcher, Coder, Reviewer, Writer, Ops
- [x] **タスク委譲**: 親エージェントが子エージェントにサブタスクを割り当て
- [x] **共有メモリ**: 複数エージェントが同じ長期記憶にアクセス
- [x] **コンフリクト解決**: 同じリソースへの同時アクセスの調停
- [x] **Crew定義ファイル**: YAMLでマルチエージェント構成を宣言的に定義

## Phase 5: Platform — プラットフォーム化 ✅

**目標**: 誰でもエージェントを作り、共有し、組み合わせられるエコシステム

- [x] **Web UI / ダッシュボード**: ブラウザからエージェントを操作・監視
- [x] **プラグインマーケットプレイス**: コミュニティ製ツールの共有・配布
- [x] **ワークフローエディタ**: JSONでエージェントの行動パターンを定義
- [x] **Docker イメージ**: コンテナで即座に起動
- [x] **i18n**: 多言語対応（日本語・英語・中国語・韓国語）
- [ ] **PyPI配布**: `pip install agent-personal` で一発インストール
- [ ] **Kubernetes オペレーター**: クラウドでスケーラブルに運用

## Phase 6: Community — コミュニティ

**目標**: 持続可能なオープンソースコミュニティ

- [ ] **Discord コミュニティサーバー**
- [ ] **公式ドキュメントサイト** (MkDocs / Docusaurus)
- [ ] **チュートリアルシリーズ**（YouTube / ブログ）
- [ ] **ハッカソンイベント**
- [ ] **Good First Issues ラベル**の整備
- [ ] **プラグインコンテスト**
- [ ] **ショーケース**: コミュニティが作ったユースケース集

---

## 貢献方法

各フェーズのタスクはIssueとして管理されます。
`good-first-issue` ラベルのIssueは初めての貢献に最適です。

詳しくは [CONTRIBUTING.md](CONTRIBUTING.md) を参照。
