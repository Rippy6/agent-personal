#!/usr/bin/env python3
"""
完全自律AIエージェント — 自分で考え、判断し、行動するもう1人の人間

使い方:
  python main.py -g "このリポジトリを分析して報告して"   # 自律モード
  python main.py -i                                       # 対話モード
  python main.py                                          # ゴールなしで自律探索
  python main.py --brain ollama                           # ローカルLLMで起動
"""

import argparse
import json
import os
import sys

VERSION = "0.3.0"


def load_config() -> dict:
    """data/config.json があればデフォルト値として読み込む"""
    config_path = os.path.join("data", "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def create_brain(brain_type: str = "auto", config: dict | None = None):
    """Brain を作成。brain_type で明示的に指定可能。"""
    config = config or {}

    if brain_type == "auto":
        # 環境変数から自動検出
        if os.environ.get("ANTHROPIC_API_KEY") or config.get("api_key"):
            brain_type = "claude"
        elif os.environ.get("OPENAI_API_KEY"):
            brain_type = "openai"
        elif os.environ.get("GOOGLE_API_KEY") or config.get("google_api_key"):
            brain_type = "gemini"
        else:
            brain_type = "mock"

    if brain_type == "claude":
        api_key = os.environ.get("ANTHROPIC_API_KEY") or config.get("api_key", "")
        if not api_key:
            print("⚠️  ANTHROPIC_API_KEY が設定されていません。デモモードで起動します。")
            from agent.brain.mock import MockBrain
            return MockBrain(), "Mock (APIキー未設定)"
        try:
            from agent.brain.claude import ClaudeBrain
            return ClaudeBrain(api_key=api_key), "Claude API"
        except ImportError:
            print("⚠️  anthropicパッケージが未インストール。デモモードで起動します。")
            print("   インストール: pip install anthropic")
            from agent.brain.mock import MockBrain
            return MockBrain(), "Mock (Claude未インストール)"

    elif brain_type == "openai":
        api_key = os.environ.get("OPENAI_API_KEY") or config.get("openai_api_key", "")
        if not api_key:
            print("⚠️  OPENAI_API_KEY が設定されていません。デモモードで起動します。")
            from agent.brain.mock import MockBrain
            return MockBrain(), "Mock (APIキー未設定)"
        try:
            from agent.brain.openai import OpenAIBrain
            model = config.get("openai_model", "gpt-4o")
            return OpenAIBrain(api_key=api_key, model=model), f"OpenAI {model}"
        except ImportError:
            print("⚠️  openaiパッケージが未インストール。デモモードで起動します。")
            print("   インストール: pip install openai")
            from agent.brain.mock import MockBrain
            return MockBrain(), "Mock (OpenAI未インストール)"

    elif brain_type == "gemini":
        api_key = os.environ.get("GOOGLE_API_KEY") or config.get("google_api_key", "")
        if not api_key:
            print("⚠️  GOOGLE_API_KEY が設定されていません。デモモードで起動します。")
            from agent.brain.mock import MockBrain
            return MockBrain(), "Mock (APIキー未設定)"
        from agent.brain.gemini import GeminiBrain
        model = config.get("gemini_model", "gemini-2.0-flash")
        return GeminiBrain(api_key=api_key, model=model), f"Gemini {model}"

    elif brain_type == "ollama":
        from agent.brain.ollama import OllamaBrain
        model = config.get("ollama_model", "llama3.1")
        base_url = config.get("ollama_url", "http://localhost:11434")
        return OllamaBrain(model=model, base_url=base_url), f"Ollama ({model})"

    else:  # mock
        from agent.brain.mock import MockBrain
        return MockBrain(), "Mock (デモ)"


def create_tools(dry_run: bool = False):
    """デフォルトのツールセットを構築"""
    from agent.tools.registry import ToolRegistry
    return ToolRegistry.create_default_registry(dry_run=dry_run)


def main():
    parser = argparse.ArgumentParser(
        description="完全自律AIエージェント — もう1人の人間",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  python main.py -g "ファイルを分析して報告して"
  python main.py -i
  python main.py --brain ollama
  python main.py --brain openai -g "プロジェクトを改善して"
        """,
    )
    parser.add_argument("-g", "--goal", help="エージェントに与えるゴール")
    parser.add_argument("-i", "--interactive", action="store_true", help="対話モード")
    parser.add_argument(
        "-b", "--brain",
        choices=["auto", "mock", "claude", "openai", "gemini", "ollama"],
        default="auto",
        help="思考エンジンを指定 (デフォルト: auto = 環境変数から自動検出)",
    )
    parser.add_argument("-n", "--max-iterations", type=int, default=0,
                        help="最大ループ回数 (デフォルト: 0=無制限)")
    parser.add_argument("-v", "--verbose", action="store_true", help="詳細表示")
    parser.add_argument("--dry-run", action="store_true", help="コマンド実行せず表示だけ")
    parser.add_argument("-d", "--delay", type=float, default=1.0, help="ループ間隔（秒）")
    parser.add_argument("--dashboard", action="store_true", help="Web UIダッシュボードを起動")
    parser.add_argument("--port", type=int, default=8080, help="ダッシュボードのポート (デフォルト: 8080)")
    parser.add_argument("--benchmark", action="store_true", help="Brainの判断精度をベンチマーク")

    args = parser.parse_args()

    # Load saved config
    config = load_config()
    if args.max_iterations == 0 and config.get("max_iterations"):
        args.max_iterations = config["max_iterations"]
    if args.delay == 1.0 and config.get("loop_delay"):
        args.delay = config["loop_delay"]
    if not args.verbose and config.get("verbose"):
        args.verbose = True
    if not args.dry_run and config.get("dry_run"):
        args.dry_run = True

    # Banner
    print("=" * 50)
    print(f"  🤖 完全自律AIエージェント v{VERSION}")
    print("  「自分で考え、判断し、行動する分身」")
    print("=" * 50)

    # Create components
    brain, brain_name = create_brain(args.brain, config)
    tools = create_tools(dry_run=args.dry_run)

    from agent.core import Agent
    from agent.utils.logger import AgentLogger

    # Dashboard setup
    dashboard = None
    if args.dashboard:
        from agent.web.server import start_dashboard, dashboard_state
        start_dashboard(port=args.port)
        dashboard = dashboard_state

    agent = Agent(
        brain=brain,
        tools=tools,
        logger=AgentLogger(verbose=args.verbose),
        loop_delay=args.delay,
        max_iterations=args.max_iterations,
        dashboard=dashboard,
    )

    mode = "対話" if args.interactive else ("自律" if args.goal else "探索")
    print(f"  Brain: {brain_name}")
    print(f"  モード: {mode}")
    if args.max_iterations > 0:
        print(f"  最大ループ: {args.max_iterations}回")
    else:
        print("  最大ループ: 無制限 (Ctrl+Cで停止)")
    if args.dry_run:
        print("  ⚠️  dry-runモード")
    if args.dashboard:
        print(f"  🌐 ダッシュボード: http://localhost:{args.port}")
    print("=" * 50)
    print()

    if args.benchmark:
        from agent.benchmark import AgentBenchmark
        bench = AgentBenchmark(brain)
        print("🏋️ ベンチマーク実行中...\n")
        results = bench.run_all()
        print(f"スコア: {results['score']}% ({results['passed']}/{results['total']})")
        for r in results["results"]:
            icon = "✅" if r["passed"] else "❌"
            print(f"  {icon} {r['name']}: ツール{'○' if r['tool_correct'] else '×'}, "
                  f"キーワード{r['keywords']}, {r['time']}")
            if not r["passed"]:
                print(f"     → {r['detail'][:80]}")
        return

    if args.goal:
        agent.add_goal(args.goal)

    if args.interactive:
        agent.run_interactive()
    else:
        agent.run()


if __name__ == "__main__":
    main()
