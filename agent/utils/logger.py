"""構造化ログ — エージェントの思考過程をリアルタイム表示"""

import sys
from datetime import datetime


PHASE_ICONS = {
    "observe": "🔍",
    "think": "💭",
    "plan": "📋",
    "act": "⚡",
    "reflect": "📝",
    "system": "🔧",
    "error": "❌",
    "goal": "🎯",
}

PHASE_LABELS = {
    "observe": "観察",
    "think": "思考",
    "plan": "計画",
    "act": "実行",
    "reflect": "振り返り",
    "system": "システム",
    "error": "エラー",
    "goal": "ゴール",
}


class AgentLogger:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._dashboard = None

    def set_dashboard(self, dashboard):
        """Web UIダッシュボードへのブリッジを設定"""
        self._dashboard = dashboard

    def log(self, phase: str, message: str, detail: str | None = None):
        icon = PHASE_ICONS.get(phase, "•")
        label = PHASE_LABELS.get(phase, phase)
        timestamp = datetime.now().strftime("%H:%M:%S")

        if self.verbose:
            print(f"[{timestamp}] {icon} [{label}] {message}", flush=True)
        else:
            print(f"{icon} [{label}] {message}", flush=True)

        if detail and self.verbose:
            for line in detail.split("\n"):
                print(f"    {line}", flush=True)

        # Forward to dashboard
        if self._dashboard:
            self._dashboard.add_log(phase, message)

    def observe(self, msg: str, detail: str | None = None):
        self.log("observe", msg, detail)

    def think(self, msg: str, detail: str | None = None):
        self.log("think", msg, detail)

    def plan(self, msg: str, detail: str | None = None):
        self.log("plan", msg, detail)

    def act(self, msg: str, detail: str | None = None):
        self.log("act", msg, detail)

    def reflect(self, msg: str, detail: str | None = None):
        self.log("reflect", msg, detail)

    def system(self, msg: str, detail: str | None = None):
        self.log("system", msg, detail)

    def error(self, msg: str, detail: str | None = None):
        self.log("error", msg, detail)

    def goal(self, msg: str, detail: str | None = None):
        self.log("goal", msg, detail)
