"""Crew — 複数エージェントの協調フレームワーク

親エージェント（Orchestrator）が子エージェント（Worker）にタスクを委譲し、
結果を集約する。YAMLファイルでCrew構成を定義可能。
"""

import json
import os
import threading
import time
from dataclasses import dataclass, field

from agent.multi.protocol import MessageBus, Message, MessageType
from agent.multi.roles import AgentRole, BUILTIN_ROLES, find_best_role
from agent.memory.long_term import LongTermMemory


@dataclass
class WorkerConfig:
    """ワーカーエージェントの設定"""
    agent_id: str
    role: str  # BUILTIN_ROLESのキー or カスタム
    brain_type: str = "mock"
    max_iterations: int = 10


@dataclass
class CrewConfig:
    """Crew全体の設定"""
    name: str = "default-crew"
    workers: list[WorkerConfig] = field(default_factory=list)
    shared_memory_path: str = "data/shared_memory.json"


class SharedMemory:
    """複数エージェントが共有する記憶ストア"""

    def __init__(self, path: str = "data/shared_memory.json"):
        self._memory = LongTermMemory(path=path)
        self._lock = threading.Lock()

    def store(self, agent_id: str, topic: str, content: str):
        with self._lock:
            self._memory.store(f"{agent_id}:{topic}", content)

    def recall(self, query: str, limit: int = 5) -> list[str]:
        with self._lock:
            return self._memory.recall(query, limit=limit)

    def get_all(self, limit: int = 20) -> str:
        with self._lock:
            return self._memory.get_all_facts_summary(limit=limit)


class Crew:
    """マルチエージェントのオーケストレーター"""

    def __init__(self, config: CrewConfig | None = None):
        self.config = config or CrewConfig()
        self.bus = MessageBus()
        self.shared_memory = SharedMemory(path=self.config.shared_memory_path)
        self._workers: dict[str, dict] = {}  # agent_id -> {thread, config, results}
        self._orchestrator_id = "orchestrator"
        self.bus.register(self._orchestrator_id)

    def add_worker(self, worker_config: WorkerConfig):
        """ワーカーを追加"""
        self.bus.register(worker_config.agent_id)
        self._workers[worker_config.agent_id] = {
            "config": worker_config,
            "thread": None,
            "results": [],
            "status": "idle",
        }

    def assign_task(self, task: str, agent_id: str | None = None) -> str:
        """タスクを割り当て。agent_id未指定なら最適なワーカーを自動選択"""
        if agent_id is None:
            agent_id = self._find_best_worker(task)

        if agent_id not in self._workers:
            return f"エラー: ワーカー '{agent_id}' が見つかりません"

        msg = Message(
            msg_type=MessageType.TASK_ASSIGN,
            sender=self._orchestrator_id,
            receiver=agent_id,
            content={"task": task},
        )
        self.bus.send(msg)
        self._workers[agent_id]["status"] = "working"

        return f"タスク「{task}」を {agent_id} に割り当てました"

    def broadcast(self, content: str):
        """全ワーカーにメッセージをブロードキャスト"""
        msg = Message(
            msg_type=MessageType.BROADCAST,
            sender=self._orchestrator_id,
            receiver="*",
            content={"message": content},
        )
        self.bus.send(msg)

    def collect_results(self, timeout: float = 5.0) -> list[dict]:
        """ワーカーからの結果を収集"""
        results = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = self.bus.receive(self._orchestrator_id, timeout=0.5)
            if msg and msg.msg_type == MessageType.TASK_RESULT:
                results.append({
                    "worker": msg.sender,
                    "result": msg.content,
                })
                self._workers[msg.sender]["status"] = "idle"
                self._workers[msg.sender]["results"].append(msg.content)
            elif msg is None and all(
                w["status"] == "idle" for w in self._workers.values()
            ):
                break
        return results

    def status(self) -> dict:
        """Crew全体の状態"""
        return {
            "name": self.config.name,
            "workers": {
                wid: {
                    "role": w["config"].role,
                    "status": w["status"],
                    "completed_tasks": len(w["results"]),
                }
                for wid, w in self._workers.items()
            },
            "message_history": len(self.bus.history()),
        }

    def _find_best_worker(self, task: str) -> str:
        """タスクに最適なワーカーを見つける"""
        best_worker = None
        best_score = -1.0

        for wid, worker in self._workers.items():
            if worker["status"] != "idle":
                continue
            role_id = worker["config"].role
            role = BUILTIN_ROLES.get(role_id)
            if role:
                score = role.matches(task)
            else:
                score = 0.5
            if score > best_score:
                best_score = score
                best_worker = wid

        return best_worker or next(iter(self._workers), self._orchestrator_id)

    @classmethod
    def from_yaml(cls, path: str) -> "Crew":
        """YAMLファイルからCrew構成を読み込み

        YAMLフォーマット:
        ```yaml
        name: my-crew
        shared_memory: data/shared_memory.json
        workers:
          - id: researcher-1
            role: researcher
            brain: mock
            max_iterations: 15
          - id: coder-1
            role: coder
            brain: claude
        ```
        """
        # stdlib only: 簡易YAMLパーサー
        config = CrewConfig()

        if not os.path.exists(path):
            return cls(config)

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # 簡易パース（PyYAML不要）
        current_worker: dict | None = None
        workers = []

        for line in content.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if stripped.startswith("name:"):
                config.name = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("shared_memory:"):
                config.shared_memory_path = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("- id:"):
                if current_worker:
                    workers.append(current_worker)
                current_worker = {"id": stripped.split(":", 1)[1].strip()}
            elif current_worker and stripped.startswith("role:"):
                current_worker["role"] = stripped.split(":", 1)[1].strip()
            elif current_worker and stripped.startswith("brain:"):
                current_worker["brain"] = stripped.split(":", 1)[1].strip()
            elif current_worker and stripped.startswith("max_iterations:"):
                try:
                    current_worker["max_iterations"] = int(stripped.split(":", 1)[1].strip())
                except ValueError:
                    pass

        if current_worker:
            workers.append(current_worker)

        for w in workers:
            config.workers.append(WorkerConfig(
                agent_id=w.get("id", "worker"),
                role=w.get("role", "researcher"),
                brain_type=w.get("brain", "mock"),
                max_iterations=w.get("max_iterations", 10),
            ))

        crew = cls(config)
        for wc in config.workers:
            crew.add_worker(wc)
        return crew
