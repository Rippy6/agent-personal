#!/usr/bin/env python3
"""
セットアップウィザード — 対話形式で初期設定を行う

初めてエージェントを使う人向けに、
ステップバイステップで環境を整える。
"""

import json
import os
import sys
import shutil


DATA_DIR = "data"
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")

DEFAULT_CONFIG = {
    "brain": "mock",
    "language": "ja",
    "max_iterations": 100,
    "loop_delay": 1.0,
    "verbose": False,
    "dry_run": False,
    "shell_safety": True,
}


def print_banner():
    print()
    print("=" * 54)
    print("  🤖 完全自律AIエージェント — セットアップウィザード")
    print("=" * 54)
    print()
    print("  このウィザードが、エージェントの初期設定を")
    print("  ステップバイステップでお手伝いします。")
    print()


def ask(question: str, options: list[str] | None = None, default: str = "") -> str:
    """ユーザーに質問して回答を得る"""
    if options:
        print(f"\n  {question}")
        for i, opt in enumerate(options, 1):
            marker = " ←おすすめ" if i == 1 else ""
            print(f"    {i}. {opt}{marker}")
        while True:
            choice = input(f"\n  番号を入力 [{1}]: ").strip()
            if not choice:
                return options[0]
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            except ValueError:
                pass
            print("  ⚠️  正しい番号を入力してください")
    else:
        prompt = f"  {question}"
        if default:
            prompt += f" [{default}]"
        prompt += ": "
        result = input(prompt).strip()
        return result or default


def ask_yes_no(question: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    result = input(f"  {question} [{hint}]: ").strip().lower()
    if not result:
        return default
    return result in ("y", "yes", "はい")


def step_welcome():
    print("─" * 54)
    print("  📖 ステップ 1/4: このエージェントについて")
    print("─" * 54)
    print()
    print("  このエージェントは「もう1人の人間」です。")
    print("  指示を待たず、自分で考え、判断し、行動します。")
    print()
    print("  できること:")
    print("    • ファイルの読み書き・検索")
    print("    • シェルコマンドの実行")
    print("    • Webページの取得")
    print("    • メモの保存・検索（長期記憶）")
    print("    • ゴールの自動分解と追跡")
    print()
    print("  3つの動かし方:")
    print("    🎯 自律モード — ゴールを1つ渡すだけ。あとは全部自分でやる")
    print("    💬 対話モード — チャットしながら一緒に作業する")
    print("    🔍 探索モード — 何も指示しない。好奇心で動き出す")
    print()
    input("  Enterで次へ...")


def step_brain(config: dict):
    print()
    print("─" * 54)
    print("  🧠 ステップ 2/4: 思考エンジンの選択")
    print("─" * 54)
    print()
    print("  エージェントの「脳」を選びます。")
    print()
    print("  • デモモード: APIキー不要。ルールベースで動く。")
    print("    まずはこれで試すのがおすすめです。")
    print()
    print("  • Claude API: Anthropicの AIを使う本格モード。")
    print("    より賢く柔軟に動きますが、APIキーが必要です。")

    choice = ask(
        "どちらを使いますか？",
        options=["デモモード（APIキー不要）", "Claude API（要APIキー）"],
    )

    if "Claude" in choice:
        print()
        print("  Claude APIを使うにはAPIキーが必要です。")
        print("  https://console.anthropic.com/ で取得できます。")
        print()
        api_key = ask("APIキーを入力（後で設定する場合は空Enter）")
        if api_key:
            config["brain"] = "claude"
            config["api_key"] = api_key
            print("  ✅ Claude APIを設定しました")
        else:
            config["brain"] = "mock"
            print("  ℹ️  後で設定する場合:")
            print("     export ANTHROPIC_API_KEY=sk-ant-...")
            print("  ひとまずデモモードで起動します。")
    else:
        config["brain"] = "mock"
        print("  ✅ デモモードで設定しました")


def step_behavior(config: dict):
    print()
    print("─" * 54)
    print("  ⚙️  ステップ 3/4: 動作設定")
    print("─" * 54)

    print()
    print("  エージェントがどれくらい自由に動けるか設定します。")

    # Shell safety
    print()
    config["shell_safety"] = ask_yes_no(
        "シェルコマンドの安全チェックを有効にする？（おすすめ: はい）", default=True
    )
    if config["shell_safety"]:
        print("  ✅ 危険なコマンドは自動でブロックされます")
    else:
        print("  ⚠️  安全チェックをオフにしました。上級者向けです。")

    # Dry run
    config["dry_run"] = ask_yes_no(
        "dry-runモードにする？（コマンドを実行せず表示だけ）", default=False
    )

    # Verbose
    config["verbose"] = ask_yes_no(
        "詳細ログを表示する？（内部の思考過程を全部見たい場合）", default=False
    )

    # Max iterations
    print()
    iters = ask("最大ループ回数（0=無制限）", default="100")
    try:
        config["max_iterations"] = int(iters)
    except ValueError:
        config["max_iterations"] = 100

    # Delay
    delay = ask("ループ間の待機秒数", default="1.0")
    try:
        config["loop_delay"] = float(delay)
    except ValueError:
        config["loop_delay"] = 1.0

    print("  ✅ 動作設定完了")


def step_finish(config: dict):
    print()
    print("─" * 54)
    print("  🎉 ステップ 4/4: セットアップ完了！")
    print("─" * 54)

    # Save config
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print()
    print(f"  設定を保存しました: {CONFIG_PATH}")
    print()
    print("  さっそく動かしてみましょう！")
    print()
    print("  ┌─────────────────────────────────────────────┐")
    print("  │  🎯 ゴールを与えて自律実行:                  │")
    print('  │    python main.py -g "ファイルを分析して"     │')
    print("  │                                              │")
    print("  │  💬 対話モードで会話:                         │")
    print("  │    python main.py -i                         │")
    print("  │                                              │")
    print("  │  🔍 何も指示せず探索させる:                   │")
    print("  │    python main.py                            │")
    print("  └─────────────────────────────────────────────┘")
    print()

    # Show summary
    brain_name = "Claude API" if config.get("brain") == "claude" else "デモモード"
    print(f"  設定内容:")
    print(f"    🧠 思考エンジン: {brain_name}")
    print(f"    🔒 安全チェック: {'ON' if config.get('shell_safety') else 'OFF'}")
    print(f"    🔄 最大ループ: {config.get('max_iterations', 100)}回")
    print(f"    ⏱️  ループ間隔: {config.get('loop_delay', 1.0)}秒")
    print()


def load_config() -> dict:
    """保存済みの設定を読み込む（なければデフォルト）"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_CONFIG)


def main():
    config = dict(DEFAULT_CONFIG)

    print_banner()

    # Check if already set up
    if os.path.exists(CONFIG_PATH):
        print("  ℹ️  既に設定ファイルがあります。")
        if not ask_yes_no("最初からやり直しますか？", default=False):
            print("  既存の設定を使います。")
            print(f"  設定ファイル: {CONFIG_PATH}")
            return

    try:
        step_welcome()
        step_brain(config)
        step_behavior(config)
        step_finish(config)
    except (KeyboardInterrupt, EOFError):
        print("\n\n  セットアップを中断しました。")
        print("  いつでも `python setup.py` で再開できます。")
        sys.exit(1)


if __name__ == "__main__":
    main()
