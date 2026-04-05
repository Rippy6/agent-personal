#!/usr/bin/env python3
"""
完全自律AIエージェント — 自分で考え、判断し、行動するもう1人の人間

使い方:
  python main.py -g "このリポジトリを分析して報告して"   # 自律モード
  python main.py -i                                       # 対話モード
  python main.py                                          # ゴールなしで自律探索
"""

import argparse
import os
import sys


def create_brain():
    """APIキーの有無でBrainを自動選択"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            from agent.brain.claude import ClaudeBrain
            brain = ClaudeBrain(api_key=api_key)
            brain_name = "Claude API"
        except ImportError:
            print("⚠️  anthropicパッケージが未インストール。モックモードで起動します。")
            print("   インストール: pip install 'agent-personal[claude]'")
            from agent.brain.mock import MockBrain
            brain = MockBrain()
            brain_name = "Mock (Claude未インストール)"
    else:
        from agent.brain.mock import MockBrain
        brain = MockBrain()
        brain_name = "Mock (デモ)"
    return brain, brain_name


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
  python main.py -g "READMEを作成して" --max-iterations 50
  python main.py -i
  python main.py -v
        """,
    )
    parser.add_argument(
        "-g", "--goal",
        help="エージェントに与えるゴール",
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="対話モード（チャットしながら指示）",
    )
    parser.add_argument(
        "-n", "--max-iterations",
        type=int,
        default=100,
        help="最大ループ回数 (デフォルト: 100, 0=無制限)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="詳細な内部状態を表示",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="シェルコマンドを実行せずに表示だけ",
    )
    parser.add_argument(
        "-d", "--delay",
        type=float,
        default=1.0,
        help="ループ間の待機秒数 (デフォルト: 1.0)",
    )

    args = parser.parse_args()

    # Banner
    print("=" * 50)
    print("  🤖 完全自律AIエージェント v0.1.0")
    print("  「自分で考え、判断し、行動する分身」")
    print("=" * 50)

    # Create components
    brain, brain_name = create_brain()
    tools = create_tools(dry_run=args.dry_run)

    from agent.core import Agent
    from agent.utils.logger import AgentLogger

    logger = AgentLogger(verbose=args.verbose)

    agent = Agent(
        brain=brain,
        tools=tools,
        logger=logger,
        loop_delay=args.delay,
        max_iterations=args.max_iterations,
    )

    print(f"  Brain: {brain_name}")
    print(f"  モード: {'対話' if args.interactive else '自律'}")
    if args.dry_run:
        print("  ⚠️  dry-runモード（シェルコマンドは実行されません）")
    print("=" * 50)
    print()

    # Add initial goal if provided
    if args.goal:
        agent.add_goal(args.goal)

    # Run
    if args.interactive:
        agent.run_interactive()
    else:
        agent.run()


if __name__ == "__main__":
    main()
