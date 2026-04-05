"""i18n — 多言語対応

エージェントのUI文字列を多言語で提供。
JSONファイルベースの軽量国際化。
"""

import json
import os

# 組み込み翻訳
TRANSLATIONS: dict[str, dict[str, str]] = {
    "ja": {
        "agent.started": "エージェント起動",
        "agent.stopped": "エージェント停止",
        "agent.shutdown": "シャットダウン中... 状態を保存します。",
        "agent.max_iterations": "最大イテレーション({n})に到達。停止します。",
        "agent.tools": "ツール: {tools}",
        "agent.mode.autonomous": "自律",
        "agent.mode.interactive": "対話",
        "agent.mode.explore": "探索",
        "goal.new": "新しいゴール: {description}",
        "goal.completed": "ゴール「{description}」を完了。",
        "goal.none": "ゴールなし",
        "observe.scan": "環境スキャン (イテレーション {n})",
        "observe.no_goals": "アクティブゴール: なし（自分で見つける必要がある）",
        "act.no_action": "（アクションなし — 観察を継続）",
        "reflect.error": "「{tool}」でエラーが発生。アプローチを見直す。",
        "reflect.empty": "「{tool}」の結果が空。別の方法を試すべきか。",
        "reflect.success": "「{tool}」は成功。",
        "dashboard.goal_added": "Web UIからゴール追加: {description}",
        "session.summary": "セッションサマリー: {actions}アクション, {goals}ゴール完了, {errors}エラー",
        "interactive.prompt": "あなた> ",
        "interactive.started": "対話モード起動（Ctrl+Cで終了）",
        "banner.title": "完全自律AIエージェント",
        "banner.subtitle": "自分で考え、判断し、行動する分身",
    },
    "en": {
        "agent.started": "Agent started",
        "agent.stopped": "Agent stopped",
        "agent.shutdown": "Shutting down... saving state.",
        "agent.max_iterations": "Max iterations ({n}) reached. Stopping.",
        "agent.tools": "Tools: {tools}",
        "agent.mode.autonomous": "autonomous",
        "agent.mode.interactive": "interactive",
        "agent.mode.explore": "explore",
        "goal.new": "New goal: {description}",
        "goal.completed": "Goal '{description}' completed.",
        "goal.none": "No goals",
        "observe.scan": "Environment scan (iteration {n})",
        "observe.no_goals": "Active goals: none (need to find on own)",
        "act.no_action": "(No action — continuing observation)",
        "reflect.error": "Error with '{tool}'. Reconsidering approach.",
        "reflect.empty": "Empty result from '{tool}'. Try another method?",
        "reflect.success": "'{tool}' succeeded.",
        "dashboard.goal_added": "Goal added from Web UI: {description}",
        "session.summary": "Session summary: {actions} actions, {goals} goals completed, {errors} errors",
        "interactive.prompt": "You> ",
        "interactive.started": "Interactive mode started (Ctrl+C to exit)",
        "banner.title": "Fully Autonomous AI Agent",
        "banner.subtitle": "A clone that thinks, decides, and acts on its own",
    },
    "zh": {
        "agent.started": "代理启动",
        "agent.stopped": "代理停止",
        "agent.shutdown": "正在关闭...保存状态。",
        "agent.max_iterations": "已达到最大迭代次数({n})。停止。",
        "agent.tools": "工具: {tools}",
        "agent.mode.autonomous": "自主",
        "agent.mode.interactive": "交互",
        "agent.mode.explore": "探索",
        "goal.new": "新目标: {description}",
        "goal.completed": "目标「{description}」已完成。",
        "goal.none": "无目标",
        "banner.title": "完全自主AI代理",
        "banner.subtitle": "自己思考、判断、行动的分身",
    },
    "ko": {
        "agent.started": "에이전트 시작",
        "agent.stopped": "에이전트 중지",
        "agent.shutdown": "종료 중... 상태를 저장합니다.",
        "agent.max_iterations": "최대 반복({n})에 도달. 중지합니다.",
        "agent.tools": "도구: {tools}",
        "agent.mode.autonomous": "자율",
        "agent.mode.interactive": "대화",
        "agent.mode.explore": "탐색",
        "goal.new": "새 목표: {description}",
        "goal.completed": "목표 '{description}' 완료.",
        "goal.none": "목표 없음",
        "banner.title": "완전 자율 AI 에이전트",
        "banner.subtitle": "스스로 생각하고 판단하고 행동하는 분신",
    },
}

# デフォルト言語
_current_lang = "ja"


def set_language(lang: str):
    """言語を設定"""
    global _current_lang
    if lang in TRANSLATIONS:
        _current_lang = lang
    elif lang.split("-")[0] in TRANSLATIONS:  # "en-US" → "en"
        _current_lang = lang.split("-")[0]


def get_language() -> str:
    return _current_lang


def available_languages() -> list[str]:
    return list(TRANSLATIONS.keys())


def t(key: str, **kwargs) -> str:
    """翻訳キーを現在の言語でフォーマットして返す"""
    lang_dict = TRANSLATIONS.get(_current_lang, TRANSLATIONS["ja"])
    template = lang_dict.get(key)
    if template is None:
        # フォールバック: 日本語 → キーそのまま
        template = TRANSLATIONS["ja"].get(key, key)
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


def load_custom_translations(path: str):
    """カスタム翻訳ファイルを読み込み（既存を上書き）"""
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for lang, strings in data.items():
            if lang not in TRANSLATIONS:
                TRANSLATIONS[lang] = {}
            TRANSLATIONS[lang].update(strings)
    except (json.JSONDecodeError, OSError):
        pass
