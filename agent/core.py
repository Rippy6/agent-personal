"""エージェントコアループ — 観察→思考→計画→実行→振り返り

これがエージェントの心臓部。全コンポーネントを統合し、
自律的な行動ループを実現する。
"""

import os
import time
import signal
from datetime import datetime

from agent.brain.base import Brain
from agent.memory.short_term import ShortTermMemory
from agent.memory.long_term import LongTermMemory
from agent.tools.registry import ToolRegistry
from agent.goal import GoalManager
from agent.utils.logger import AgentLogger


class Agent:
    def __init__(
        self,
        brain: Brain,
        tools: ToolRegistry,
        logger: AgentLogger | None = None,
        memory_path: str = "data/memory.json",
        goals_path: str = "data/goals.json",
        loop_delay: float = 1.0,
        max_iterations: int = 100,
    ):
        self.brain = brain
        self.tools = tools
        self.logger = logger or AgentLogger()
        self.short_memory = ShortTermMemory()
        self.long_memory = LongTermMemory(path=memory_path)
        self.goal_manager = GoalManager(path=goals_path)
        self.loop_delay = loop_delay
        self.max_iterations = max_iterations
        self._running = False
        self._iteration = 0

        # Connect note tool to long-term memory
        note_tool = self.tools.get("note")
        if note_tool and hasattr(note_tool, "set_memory"):
            note_tool.set_memory(self.long_memory)

    def add_goal(self, description: str, priority: int = 5):
        goal = self.goal_manager.add_goal(description, priority=priority)
        self.logger.goal(f"新しいゴール: {description}", f"ID: {goal.id}, 優先度: {priority}")

    def run(self):
        """メインの自律ループを開始"""
        self._running = True
        self._iteration = 0

        # Handle graceful shutdown
        original_sigint = signal.getsignal(signal.SIGINT)

        def _shutdown(sig, frame):
            self.logger.system("シャットダウン中... 状態を保存します。")
            self._running = False

        signal.signal(signal.SIGINT, _shutdown)

        self.logger.system("エージェント起動")
        self.logger.system(
            f"ツール: {', '.join(self.tools.list_names())}",
            f"最大イテレーション: {self.max_iterations}",
        )

        if self.goal_manager.has_active_goals():
            self.logger.system(f"\n{self.goal_manager.summary()}")

        idle_count = 0
        max_idle = 5  # Stop after 5 consecutive idle cycles

        try:
            while self._running:
                self._iteration += 1

                if self.max_iterations > 0 and self._iteration > self.max_iterations:
                    self.logger.system(f"最大イテレーション({self.max_iterations})に到達。停止します。")
                    break

                # === 1. OBSERVE ===
                observation = self._observe()

                # === 2. THINK ===
                decision = self._think(observation)

                if decision.get("action") is None and not decision.get("new_goals"):
                    idle_count += 1
                    if idle_count >= max_idle:
                        self.logger.system("アイドル状態が続いています。新しいゴールを待ちます。")
                        break
                else:
                    idle_count = 0

                # === 3. PLAN ===
                self._plan(decision)

                # === 4. ACT ===
                result = self._act(decision)

                # === 5. REFLECT ===
                self._reflect(decision, result)

                # Delay between iterations
                if self._running and self.loop_delay > 0:
                    time.sleep(self.loop_delay)

        finally:
            signal.signal(signal.SIGINT, original_sigint)
            self.logger.system("エージェント停止")

    def run_interactive(self):
        """対話モード — ユーザー入力を受け付けつつ自律ループを回す"""
        self._running = True
        self._iteration = 0

        original_sigint = signal.getsignal(signal.SIGINT)

        def _shutdown(sig, frame):
            self.logger.system("シャットダウン中...")
            self._running = False

        signal.signal(signal.SIGINT, _shutdown)

        self.logger.system("対話モード起動（Ctrl+Cで終了）")
        self.logger.system(f"ツール: {', '.join(self.tools.list_names())}")
        print()

        try:
            while self._running:
                # Get user input
                try:
                    user_input = input("あなた> ").strip()
                except EOFError:
                    break

                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit", "終了", "q"):
                    break
                if user_input.lower() in ("goals", "ゴール"):
                    print(self.goal_manager.summary())
                    continue
                if user_input.lower() in ("memory", "記憶"):
                    print(self.long_memory.get_all_facts_summary())
                    continue

                # Add as goal and run one cycle
                self.add_goal(user_input)

                # Run cycles until goal is done or idle
                cycles = 0
                max_cycles = 20
                while self._running and self.goal_manager.has_active_goals() and cycles < max_cycles:
                    cycles += 1
                    self._iteration += 1
                    observation = self._observe()
                    decision = self._think(observation)
                    self._plan(decision)
                    result = self._act(decision)
                    self._reflect(decision, result)

                    if decision.get("action") is None:
                        break

                    time.sleep(self.loop_delay)

                print()

        finally:
            signal.signal(signal.SIGINT, original_sigint)
            self.logger.system("対話モード終了")

    # === Internal phases ===

    def _observe(self) -> str:
        """Phase 1: 環境を観察し、現状を把握する"""
        parts = []

        # Current directory state
        cwd = os.getcwd()
        try:
            entries = os.listdir(cwd)
            file_count = len([e for e in entries if os.path.isfile(e)])
            dir_count = len([e for e in entries if os.path.isdir(e)])
            parts.append(f"作業ディレクトリ: {cwd} ({file_count}ファイル, {dir_count}ディレクトリ)")
        except OSError:
            parts.append(f"作業ディレクトリ: {cwd}")

        # Current time
        parts.append(f"現在時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Goal state
        active_goals = self.goal_manager.get_active_goals()
        if active_goals:
            parts.append(f"アクティブゴール: {len(active_goals)}件")
            for g in active_goals[:3]:
                parts.append(f"  - [{g.status}] {g.description}")
        else:
            parts.append("アクティブゴール: なし")

        # Last action result
        last_result = self.short_memory.get_last_action_result()
        if last_result:
            truncated = last_result[:300] + "..." if len(last_result) > 300 else last_result
            parts.append(f"前回の実行結果:\n{truncated}")

        observation = "\n".join(parts)
        self.logger.observe(
            f"環境スキャン (イテレーション {self._iteration})",
            observation if self.logger.verbose else None,
        )
        self.short_memory.add("observe", observation)
        return observation

    def _think(self, observation: str) -> dict:
        """Phase 2: 観察を基に思考し、判断する"""
        context = {
            "observation": observation,
            "goals": [g.to_dict() for g in self.goal_manager.get_active_goals()],
            "memory_summary": self.short_memory.get_context_summary(),
            "long_term_hints": self.long_memory.get_all_facts_summary(limit=5),
            "available_tools": self.tools.list_tools(),
            "iteration": self._iteration,
        }

        decision = self.brain.think(context)

        thought = decision.get("thought", "（思考なし）")
        self.logger.think(thought)
        self.short_memory.add("think", thought)

        return decision

    def _plan(self, decision: dict):
        """Phase 3: 新しいゴール/サブタスクを追加し、計画を更新"""
        plan_steps = decision.get("plan", [])
        if plan_steps:
            self.logger.plan(" → ".join(plan_steps))

        # Add new goals discovered by the brain
        new_goals = decision.get("new_goals", [])
        for goal_desc in new_goals:
            if goal_desc:
                self.add_goal(goal_desc)

        self.short_memory.add("plan", str(plan_steps))

    def _act(self, decision: dict) -> str:
        """Phase 4: 決定されたアクションを実行"""
        action = decision.get("action")
        if action is None:
            self.logger.act("（アクションなし — 観察を継続）")
            self.short_memory.add("act", "なし")
            self.short_memory.add("act_result", "（アクションなし）")
            return ""

        tool_name = action.get("tool", "")
        args = action.get("args", {})

        self.logger.act(
            f"{tool_name}: {self._format_args(args)}",
        )

        result = self.tools.run(tool_name, **args)

        # Log result (truncated for display)
        display_result = result[:200] + "..." if len(result) > 200 else result
        if self.logger.verbose:
            self.logger.act(f"結果: {display_result}")

        self.short_memory.add("act", f"{tool_name}({self._format_args(args)})")
        self.short_memory.add("act_result", result)

        return result

    def _reflect(self, decision: dict, result: str):
        """Phase 5: 結果を評価し、学びを記録"""
        action = decision.get("action")
        thought = decision.get("thought", "")

        if not action:
            return

        tool_name = action.get("tool", "")

        # Simple heuristic: was the action successful?
        is_error = "エラー" in result or "error" in result.lower()
        is_empty = not result.strip()

        if is_error:
            reflection = f"「{tool_name}」でエラーが発生した。アプローチを見直す必要がある。"
            self.long_memory.store_pattern(f"「{tool_name}」実行時にエラー: {result[:100]}")
        elif is_empty:
            reflection = f"「{tool_name}」の結果が空だった。別の方法を試すべきか。"
        else:
            reflection = f"「{tool_name}」は成功した。"
            # Try to mark current goal as done if result looks complete
            current_goal = self.goal_manager.get_next_goal()
            if current_goal and self._seems_goal_complete(current_goal, result):
                self.goal_manager.complete_goal(current_goal.id, result[:200])
                reflection += f" ゴール「{current_goal.description}」を完了。"

        self.logger.reflect(reflection)
        self.short_memory.add("reflect", reflection)

    def _seems_goal_complete(self, goal, result: str) -> bool:
        """ゴールが完了したかのヒューリスティック判定"""
        desc = goal.description.lower()
        # Simple heuristics
        if any(kw in desc for kw in ["一覧", "list", "確認", "見る", "読む", "分析"]):
            return bool(result.strip())
        if any(kw in desc for kw in ["作成", "write", "書く", "生成"]):
            return "ファイルを書き込みました" in result or "作成" in result
        if any(kw in desc for kw in ["実行", "run", "テスト"]):
            return "エラー" not in result
        # Default: mark as done after first successful action
        return bool(result.strip()) and "エラー" not in result

    def _format_args(self, args: dict) -> str:
        parts = []
        for k, v in args.items():
            sv = str(v)
            if len(sv) > 50:
                sv = sv[:50] + "..."
            parts.append(f'{k}="{sv}"')
        return ", ".join(parts)
