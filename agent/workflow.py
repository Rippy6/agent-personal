"""ワークフローエディタ — ノーコードでエージェントの行動パターンを定義

JSONファイルでワークフロー（ステップの列）を定義し、
エージェントが順番に実行する。条件分岐・ループ対応。
"""

import json
import os
from dataclasses import dataclass, field


@dataclass
class WorkflowStep:
    """ワークフローの1ステップ"""
    id: str
    action: str  # "tool", "goal", "condition", "loop"
    params: dict = field(default_factory=dict)
    next_step: str | None = None  # 次のステップID
    on_error: str | None = None  # エラー時のステップID

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "action": self.action,
            "params": self.params,
            "next_step": self.next_step,
            "on_error": self.on_error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowStep":
        return cls(
            id=data["id"],
            action=data["action"],
            params=data.get("params", {}),
            next_step=data.get("next_step"),
            on_error=data.get("on_error"),
        )


@dataclass
class Workflow:
    """ワークフロー定義"""
    name: str
    description: str = ""
    steps: list[WorkflowStep] = field(default_factory=list)
    start_step: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "start_step": self.start_step,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Workflow":
        wf = cls(
            name=data["name"],
            description=data.get("description", ""),
            start_step=data.get("start_step", ""),
        )
        for step_data in data.get("steps", []):
            wf.steps.append(WorkflowStep.from_dict(step_data))
        if not wf.start_step and wf.steps:
            wf.start_step = wf.steps[0].id
        return wf

    def get_step(self, step_id: str) -> WorkflowStep | None:
        for s in self.steps:
            if s.id == step_id:
                return s
        return None

    def validate(self) -> list[str]:
        """ワークフローの検証。エラーメッセージのリストを返す"""
        errors = []
        if not self.name:
            errors.append("ワークフロー名が未設定")
        if not self.steps:
            errors.append("ステップが0件")
            return errors
        if not self.start_step:
            errors.append("開始ステップが未設定")

        step_ids = {s.id for s in self.steps}
        if self.start_step and self.start_step not in step_ids:
            errors.append(f"開始ステップ '{self.start_step}' が見つかりません")

        for step in self.steps:
            if step.next_step and step.next_step not in step_ids:
                errors.append(f"ステップ '{step.id}' の next_step '{step.next_step}' が見つかりません")
            if step.on_error and step.on_error not in step_ids:
                errors.append(f"ステップ '{step.id}' の on_error '{step.on_error}' が見つかりません")

        return errors


class WorkflowRunner:
    """ワークフローを実行するランナー"""

    def __init__(self, tools=None, logger=None):
        self.tools = tools
        self.logger = logger
        self._results: list[dict] = []

    def run(self, workflow: Workflow, max_steps: int = 100) -> list[dict]:
        """ワークフローを実行"""
        errors = workflow.validate()
        if errors:
            return [{"step": "validation", "error": "; ".join(errors)}]

        self._results = []
        current_id = workflow.start_step
        step_count = 0

        while current_id and step_count < max_steps:
            step = workflow.get_step(current_id)
            if not step:
                self._results.append({"step": current_id, "error": "ステップが見つかりません"})
                break

            step_count += 1
            result = self._execute_step(step)
            self._results.append({"step": step.id, "action": step.action, **result})

            if result.get("error") and step.on_error:
                current_id = step.on_error
            else:
                current_id = step.next_step

        return self._results

    def _execute_step(self, step: WorkflowStep) -> dict:
        """1ステップを実行"""
        if step.action == "tool":
            return self._run_tool(step.params)
        elif step.action == "goal":
            return {"result": f"ゴール追加: {step.params.get('description', '')}"}
        elif step.action == "condition":
            return self._evaluate_condition(step.params)
        elif step.action == "log":
            msg = step.params.get("message", "")
            if self.logger:
                self.logger.system(msg)
            return {"result": msg}
        else:
            return {"error": f"未知のアクション: {step.action}"}

    def _run_tool(self, params: dict) -> dict:
        """ツールを実行"""
        tool_name = params.get("tool", "")
        args = params.get("args", {})
        if not self.tools:
            return {"error": "ツールが未設定"}
        try:
            result = self.tools.run(tool_name, **args)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}

    def _evaluate_condition(self, params: dict) -> dict:
        """条件を評価（前のステップ結果を参照）"""
        check = params.get("check", "")
        if not self._results:
            return {"result": "false"}

        last = self._results[-1]
        last_result = last.get("result", "")

        if check == "has_result":
            return {"result": "true" if last_result else "false"}
        elif check == "no_error":
            return {"result": "true" if "error" not in last else "false"}
        elif check == "contains":
            keyword = params.get("keyword", "")
            return {"result": "true" if keyword in str(last_result) else "false"}
        else:
            return {"result": "true"}


def load_workflow(path: str) -> Workflow:
    """JSONファイルからワークフローを読み込み"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Workflow.from_dict(data)


def save_workflow(workflow: Workflow, path: str):
    """ワークフローをJSONファイルに保存"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(workflow.to_dict(), f, ensure_ascii=False, indent=2)
