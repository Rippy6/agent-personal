"""ゴール管理 — ツリー構造のゴール分解・追跡・永続化"""

import json
import os
import uuid
from datetime import datetime


DEFAULT_PATH = "data/goals.json"


class Goal:
    def __init__(
        self,
        description: str,
        goal_id: str | None = None,
        parent_id: str | None = None,
        priority: int = 5,
        status: str = "pending",
    ):
        self.id = goal_id or uuid.uuid4().hex[:8]
        self.description = description
        self.parent_id = parent_id
        self.priority = priority  # 1 (highest) - 10 (lowest)
        self.status = status  # pending, active, done, failed
        self.created_at = datetime.now().isoformat()
        self.completed_at: str | None = None
        self.subtasks: list[str] = []  # child goal IDs
        self.result: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "parent_id": self.parent_id,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "subtasks": self.subtasks,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Goal":
        goal = cls(
            description=data["description"],
            goal_id=data["id"],
            parent_id=data.get("parent_id"),
            priority=data.get("priority", 5),
            status=data.get("status", "pending"),
        )
        goal.created_at = data.get("created_at", "")
        goal.completed_at = data.get("completed_at")
        goal.subtasks = data.get("subtasks", [])
        goal.result = data.get("result")
        return goal


class GoalManager:
    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        self._goals: dict[str, Goal] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("goals", []):
                    goal = Goal.from_dict(item)
                    self._goals[goal.id] = goal
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        data = {"goals": [g.to_dict() for g in self._goals.values()]}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_goal(self, description: str, parent_id: str | None = None, priority: int = 5) -> Goal:
        goal = Goal(description=description, parent_id=parent_id, priority=priority)
        self._goals[goal.id] = goal
        if parent_id and parent_id in self._goals:
            self._goals[parent_id].subtasks.append(goal.id)
        self._save()
        return goal

    def get_goal(self, goal_id: str) -> Goal | None:
        return self._goals.get(goal_id)

    def complete_goal(self, goal_id: str, result: str | None = None):
        goal = self._goals.get(goal_id)
        if goal:
            goal.status = "done"
            goal.completed_at = datetime.now().isoformat()
            goal.result = result
            self._check_parent_completion(goal)
            self._save()

    def fail_goal(self, goal_id: str, reason: str | None = None):
        goal = self._goals.get(goal_id)
        if goal:
            goal.status = "failed"
            goal.completed_at = datetime.now().isoformat()
            goal.result = reason
            self._save()

    def activate_goal(self, goal_id: str):
        goal = self._goals.get(goal_id)
        if goal:
            goal.status = "active"
            self._save()

    def _check_parent_completion(self, goal: Goal):
        """子ゴールが全て完了したら、親ゴールも完了にする"""
        if not goal.parent_id:
            return
        parent = self._goals.get(goal.parent_id)
        if not parent:
            return
        if all(
            self._goals.get(sid) and self._goals[sid].status == "done"
            for sid in parent.subtasks
        ):
            parent.status = "done"
            parent.completed_at = datetime.now().isoformat()

    def get_active_goals(self) -> list[Goal]:
        """優先度順にアクティブ・ペンディングのゴールを返す"""
        active = [
            g for g in self._goals.values()
            if g.status in ("pending", "active")
        ]
        active.sort(key=lambda g: g.priority)
        return active

    def get_next_goal(self) -> Goal | None:
        """次に取り組むべきゴールを返す"""
        active = self.get_active_goals()
        if not active:
            return None
        # Prefer already-active goals over pending
        for g in active:
            if g.status == "active":
                return g
        # Activate the highest priority pending goal
        goal = active[0]
        self.activate_goal(goal.id)
        return goal

    def get_all_goals(self) -> list[dict]:
        return [g.to_dict() for g in self._goals.values()]

    def has_active_goals(self) -> bool:
        return any(g.status in ("pending", "active") for g in self._goals.values())

    def summary(self) -> str:
        if not self._goals:
            return "ゴールなし"
        lines = []
        status_icons = {"pending": "⏳", "active": "🔄", "done": "✅", "failed": "❌"}
        for goal in self._goals.values():
            icon = status_icons.get(goal.status, "?")
            lines.append(f"  {icon} [{goal.id}] {goal.description}")
        return f"ゴール ({len(self._goals)}件):\n" + "\n".join(lines)
