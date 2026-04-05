"""エージェントコアループ — 観察→思考→計画→実行→振り返り

これがエージェントの心臓部。全コンポーネントを統合し、
自律的な行動ループを実現する。

設計哲学: ゴールが全て完了しても停止しない。
環境を観察し、新しい改善点や課題を自分で発見してゴールを生成する。
これが「分身」としての核心。
"""

import os
import time
import signal
from datetime import datetime

from agent.brain.base import Brain
from agent.memory.short_term import ShortTermMemory
from agent.memory.long_term import LongTermMemory
from agent.memory.vector import VectorMemory
from agent.tools.registry import ToolRegistry
from agent.goal import GoalManager
from agent.learning import TaskLearner
from agent.planner import Planner
from agent.context_optimizer import ContextOptimizer
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
        max_iterations: int = 0,
        dashboard=None,
    ):
        self.brain = brain
        self.tools = tools
        self.logger = logger or AgentLogger()
        self.short_memory = ShortTermMemory()
        self.long_memory = LongTermMemory(path=memory_path)
        self.vector_memory = VectorMemory(
            path=os.path.join(os.path.dirname(memory_path), "vector_memory.json")
        )
        self.goal_manager = GoalManager(path=goals_path)
        self.task_learner = TaskLearner(
            path=os.path.join(os.path.dirname(goals_path), "task_patterns.json")
        )
        self.planner = Planner(self.goal_manager)
        self.context_optimizer = ContextOptimizer(
            short_memory=self.short_memory,
            long_memory=self.long_memory,
            vector_memory=self.vector_memory,
            goal_manager=self.goal_manager,
        )
        self.loop_delay = loop_delay
        self.max_iterations = max_iterations  # 0 = 無制限
        self.dashboard = dashboard  # Optional DashboardState for Web UI
        self._running = False
        self._iteration = 0
        self._stats = {"actions": 0, "goals_completed": 0, "goals_generated": 0, "errors": 0}

        # Connect note tool to long-term memory
        note_tool = self.tools.get("note")
        if note_tool and hasattr(note_tool, "set_memory"):
            note_tool.set_memory(self.long_memory)

        # Connect logger to dashboard
        if self.dashboard:
            self.logger.set_dashboard(self.dashboard)

    def add_goal(self, description: str, priority: int = 5) -> str:
        goal = self.goal_manager.add_goal(description, priority=priority)
        self.logger.goal(f"新しいゴール: {description}", f"ID: {goal.id}, 優先度: {priority}")
        self._stats["goals_generated"] += 1
        return goal.id

    @property
    def stats(self) -> dict:
        return {**self._stats, "iterations": self._iteration}

    def run(self):
        """メインの自律ループを開始 — ゴールがなくても止まらない"""
        self._running = True
        self._iteration = 0

        original_sigint = signal.getsignal(signal.SIGINT)

        def _shutdown(sig, frame):
            self.logger.system("シャットダウン中... 状態を保存します。")
            self._running = False

        signal.signal(signal.SIGINT, _shutdown)

        self.logger.system("エージェント起動")
        self.logger.system(
            f"ツール: {', '.join(self.tools.list_names())}",
            f"最大イテレーション: {self.max_iterations or '無制限'}",
        )

        if self.goal_manager.has_active_goals():
            self.logger.system(f"\n{self.goal_manager.summary()}")

        try:
            while self._running:
                self._iteration += 1

                if self.max_iterations > 0 and self._iteration > self.max_iterations:
                    self.logger.system(f"最大イテレーション({self.max_iterations})に到達。停止します。")
                    break

                # Check for goals submitted from Web UI
                self._check_dashboard_goals()

                # === 5 PHASE LOOP ===
                observation = self._observe()
                decision = self._think(observation)
                self._plan(decision)
                result = self._act(decision)
                self._reflect(decision, result)

                # Push state to dashboard
                self._sync_dashboard()

                # Adaptive delay: faster when busy, slower when idle
                if decision.get("action") is not None:
                    time.sleep(self.loop_delay)
                else:
                    time.sleep(self.loop_delay * 3)  # Idle = slower polling

        finally:
            signal.signal(signal.SIGINT, original_sigint)
            self._print_session_summary()
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
                if user_input.lower() in ("stats", "統計"):
                    self._print_session_summary()
                    continue
                if user_input.lower() in ("status", "状態"):
                    print(self.goal_manager.summary())
                    print(f"\nイテレーション: {self._iteration}")
                    print(f"記憶: {len(self.short_memory)}件（短期）")
                    continue

                # Add as goal and run cycles
                self.add_goal(user_input)

                cycles = 0
                max_cycles = 30
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
            self._print_session_summary()
            self.logger.system("対話モード終了")

    # === Internal phases ===

    def _observe(self) -> str:
        """Phase 1: 環境を観察し、現状を把握する"""
        parts = []

        # Current directory state
        cwd = os.getcwd()
        try:
            entries = os.listdir(cwd)
            files = [e for e in entries if os.path.isfile(e)]
            dirs = [e for e in entries if os.path.isdir(e) and not e.startswith(".")]
            parts.append(f"作業ディレクトリ: {cwd} ({len(files)}ファイル, {len(dirs)}ディレクトリ)")
        except OSError:
            parts.append(f"作業ディレクトリ: {cwd}")

        parts.append(f"現在時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        parts.append(f"セッション: イテレーション{self._iteration}, 完了ゴール{self._stats['goals_completed']}件")

        # Goal state
        active_goals = self.goal_manager.get_active_goals()
        if active_goals:
            parts.append(f"アクティブゴール: {len(active_goals)}件")
            for g in active_goals[:5]:
                parts.append(f"  - [{g.status}] {g.description}")
        else:
            parts.append("アクティブゴール: なし（自分で見つける必要がある）")

        # Last action result
        last_result = self.short_memory.get_last_action_result()
        if last_result:
            truncated = last_result[:500] + "..." if len(last_result) > 500 else last_result
            parts.append(f"前回の実行結果:\n{truncated}")

        # Long-term memory hints
        patterns = self.long_memory.get_patterns()
        if patterns:
            parts.append(f"学習パターン: {'; '.join(patterns[-3:])}")

        observation = "\n".join(parts)
        self.logger.observe(
            f"環境スキャン (イテレーション {self._iteration})",
            observation if self.logger.verbose else None,
        )
        self.short_memory.add("observe", observation)
        return observation

    def _think(self, observation: str) -> dict:
        """Phase 2: 観察を基に思考し、判断する。ゴールがなくても自分で考える"""
        # コンテキスト最適化: 重要度に応じて情報を選別
        context = self.context_optimizer.summarize_for_brain(
            observation, self._iteration, self._stats
        )
        context["available_tools"] = self.tools.list_tools()

        # タスク学習: 過去の成功パターンをヒントとして追加
        current_goal = self.goal_manager.get_next_goal()
        if current_goal:
            suggestions = self.task_learner.suggest(observation, current_goal.description)
            if suggestions:
                hint = "過去の成功パターン: " + "; ".join(
                    f"{s['tool']}({s['reason'][:40]})" for s in suggestions[:2]
                )
                context["long_term_hints"] = (context.get("long_term_hints", "") + "\n" + hint).strip()

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

        new_goals = decision.get("new_goals", [])
        for goal_desc in new_goals:
            if goal_desc:
                goal_id = self.add_goal(goal_desc)
                # 複雑なゴールは自動でサブタスクに分解
                if self.planner.should_decompose(goal_id):
                    subtask_ids = self.planner.decompose(goal_id)
                    if subtask_ids:
                        self.logger.plan(f"ゴールを{len(subtask_ids)}サブタスクに分解")

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

        self.logger.act(f"{tool_name}: {self._format_args(args)}")
        self._stats["actions"] += 1

        result = self.tools.run(tool_name, **args)

        display_result = result[:200] + "..." if len(result) > 200 else result
        if self.logger.verbose:
            self.logger.act(f"結果: {display_result}")

        self.short_memory.add("act", f"{tool_name}({self._format_args(args)})")
        self.short_memory.add("act_result", result)

        return result

    def _reflect(self, decision: dict, result: str):
        """Phase 5: 結果を評価し、学びを記録し、次のゴールを自己生成する

        これが「分身」の核心 — 振り返りの中で次にやるべきことを自分で見つける。
        """
        action = decision.get("action")
        thought = decision.get("thought", "")

        if not action:
            # アクションなしでも、状況を分析して次の行動を考える
            self._generate_self_goals(result)
            return

        tool_name = action.get("tool", "")

        is_error = "エラー" in result or "error" in result.lower()
        is_empty = not result.strip()

        current_goal = self.goal_manager.get_next_goal()
        goal_desc = current_goal.description if current_goal else ""

        if is_error:
            reflection = f"「{tool_name}」でエラーが発生。アプローチを見直す。"
            self.long_memory.store_pattern(f"「{tool_name}」実行時にエラー: {result[:100]}")
            self._stats["errors"] += 1
            # タスク学習: 失敗パターンを記録
            self.task_learner.record(
                thought, tool_name, action.get("args", {}), result[:100], success=False, goal_description=goal_desc,
            )
        elif is_empty:
            reflection = f"「{tool_name}」の結果が空。別の方法を試すべきか。"
        else:
            reflection = f"「{tool_name}」は成功。"
            # ゴール完了判定
            if current_goal and self._seems_goal_complete(current_goal, result):
                self.goal_manager.complete_goal(current_goal.id, result[:200])
                reflection += f" ゴール「{current_goal.description}」を完了。"
                self._stats["goals_completed"] += 1

            # 成功した結果から学びを記録
            self._learn_from_result(tool_name, result)
            # タスク学習: 成功パターンを記録
            self.task_learner.record(
                thought, tool_name, action.get("args", {}), result[:100], success=True, goal_description=goal_desc,
            )
            # ベクトル記憶に蓄積
            self.vector_memory.store(f"{tool_name}: {result[:200]}", topic=tool_name)

        self.logger.reflect(reflection)
        self.short_memory.add("reflect", reflection)

        # 振り返り後、次にやるべきことを自分で見つける
        self._generate_self_goals(result)

    def _generate_self_goals(self, last_result: str):
        """振り返りの中で、次にやるべきゴールを自己生成する"""
        if self.goal_manager.has_active_goals():
            return  # まだやるべきことがある

        # ゴールが空 → 環境から新しい課題を見つける
        observation = self.short_memory.get_context_summary()

        # 最近の行動から改善点を探す
        recent = self.short_memory.get_recent(5)
        recent_tools = [
            e["content"] for e in recent
            if e["phase"] == "act" and e["content"] != "なし"
        ]

        # Brain に「次に何をすべきか」を考えさせる
        context = {
            "observation": f"全てのゴールが完了した。環境を見て次にやるべきことを自分で見つけよう。\n最近の行動: {recent_tools[-3:] if recent_tools else '（なし）'}",
            "goals": [],
            "memory_summary": observation,
            "long_term_hints": self.long_memory.get_all_facts_summary(limit=5),
            "available_tools": self.tools.list_tools(),
            "iteration": self._iteration,
            "stats": self._stats,
        }

        decision = self.brain.think(context)
        new_goals = decision.get("new_goals", [])
        for goal_desc in new_goals:
            if goal_desc:
                self.add_goal(goal_desc)

    def _learn_from_result(self, tool_name: str, result: str):
        """成功した結果から長期記憶に知識を蓄積"""
        if tool_name == "file_list" and "件" in result:
            # ディレクトリ構造を学習
            self.long_memory.store("directory_structure", result[:200])
        elif tool_name == "file_read":
            # ファイル内容のサマリーを記憶
            lines = result.split("\n")
            if lines:
                self.long_memory.store("file_contents", lines[0][:100])
        elif tool_name == "shell":
            # コマンド結果を記憶
            if len(result) > 10:
                self.long_memory.store("command_results", result[:150])

    def _seems_goal_complete(self, goal, result: str) -> bool:
        """ゴールが完了したかのヒューリスティック判定"""
        desc = goal.description.lower()
        if any(kw in desc for kw in ["一覧", "list", "確認", "見る", "読む", "分析"]):
            return bool(result.strip())
        if any(kw in desc for kw in ["作成", "write", "書く", "生成"]):
            return "ファイルを書き込みました" in result or "作成" in result
        if any(kw in desc for kw in ["実行", "run", "テスト"]):
            return "エラー" not in result
        return bool(result.strip()) and "エラー" not in result

    def _print_session_summary(self):
        """セッション終了時のサマリー表示"""
        s = self._stats
        learn = self.task_learner.stats()
        self.logger.system(
            f"セッションサマリー: {s['actions']}アクション, "
            f"{s['goals_completed']}ゴール完了, "
            f"{s['goals_generated']}ゴール生成, "
            f"{s['errors']}エラー, "
            f"{self._iteration}イテレーション, "
            f"学習パターン{learn['total_patterns']}件(成功率{learn['success_rate']:.0%}), "
            f"ベクトル記憶{self.vector_memory.count()}件"
        )

    def _check_dashboard_goals(self):
        """Web UIから追加されたゴールを取り込む"""
        if not self.dashboard:
            return
        for goal_desc in self.dashboard.pop_pending_goals():
            self.add_goal(goal_desc)
            self.logger.system(f"Web UIからゴール追加: {goal_desc}")

    def _sync_dashboard(self):
        """ダッシュボードにエージェント状態を同期"""
        if not self.dashboard:
            return
        self.dashboard.update_goals(self.goal_manager.get_all_goals())
        self.dashboard.update_stats(self.stats)
        self.dashboard.is_running = self._running
        self.dashboard.brain_name = type(self.brain).__name__

    @staticmethod
    def _format_args(args: dict) -> str:
        parts = []
        for k, v in args.items():
            sv = str(v)
            if len(sv) > 50:
                sv = sv[:50] + "..."
            parts.append(f'{k}="{sv}"')
        return ", ".join(parts)
