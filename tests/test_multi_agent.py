"""Phase 4 テスト — マルチエージェント（通信・ロール・Crew）"""

import os
import tempfile
import pytest

from agent.multi.protocol import MessageBus, Message, MessageType
from agent.multi.roles import AgentRole, BUILTIN_ROLES, find_best_role
from agent.multi.crew import Crew, CrewConfig, WorkerConfig, SharedMemory


# === メッセージバス ===

class TestMessageBus:
    def test_register_and_agents(self):
        bus = MessageBus()
        bus.register("agent-1")
        bus.register("agent-2")
        assert set(bus.agents()) == {"agent-1", "agent-2"}

    def test_send_and_receive(self):
        bus = MessageBus()
        bus.register("sender")
        bus.register("receiver")

        msg = Message(
            msg_type=MessageType.TASK_ASSIGN,
            sender="sender",
            receiver="receiver",
            content={"task": "テスト"},
        )
        bus.send(msg)

        received = bus.receive("receiver", timeout=1.0)
        assert received is not None
        assert received.content["task"] == "テスト"
        assert received.sender == "sender"

    def test_broadcast(self):
        bus = MessageBus()
        bus.register("boss")
        bus.register("worker-1")
        bus.register("worker-2")

        msg = Message(
            msg_type=MessageType.BROADCAST,
            sender="boss",
            receiver="*",
            content={"message": "全員集合"},
        )
        bus.send(msg)

        r1 = bus.receive("worker-1", timeout=1.0)
        r2 = bus.receive("worker-2", timeout=1.0)
        boss_msg = bus.receive("boss", timeout=0.1)

        assert r1 is not None
        assert r2 is not None
        assert boss_msg is None  # 送信者には届かない

    def test_receive_all(self):
        bus = MessageBus()
        bus.register("a")
        bus.register("b")

        for i in range(3):
            bus.send(Message(
                msg_type=MessageType.KNOWLEDGE,
                sender="a",
                receiver="b",
                content={"data": i},
            ))

        messages = bus.receive_all("b")
        assert len(messages) == 3

    def test_unregister(self):
        bus = MessageBus()
        bus.register("temp")
        bus.unregister("temp")
        assert "temp" not in bus.agents()

    def test_history(self):
        bus = MessageBus()
        bus.register("a")
        bus.register("b")
        bus.send(Message(
            msg_type=MessageType.KNOWLEDGE,
            sender="a", receiver="b",
            content={"test": True},
        ))
        h = bus.history()
        assert len(h) == 1
        assert h[0]["sender"] == "a"

    def test_receive_timeout(self):
        bus = MessageBus()
        bus.register("lonely")
        msg = bus.receive("lonely", timeout=0.1)
        assert msg is None


class TestMessage:
    def test_to_dict_and_back(self):
        msg = Message(
            msg_type=MessageType.TASK_ASSIGN,
            sender="a",
            receiver="b",
            content={"task": "テスト"},
        )
        d = msg.to_dict()
        restored = Message.from_dict(d)
        assert restored.sender == "a"
        assert restored.receiver == "b"
        assert restored.content["task"] == "テスト"


# === ロール ===

class TestRoles:
    def test_builtin_roles_exist(self):
        assert "researcher" in BUILTIN_ROLES
        assert "coder" in BUILTIN_ROLES
        assert "reviewer" in BUILTIN_ROLES
        assert "writer" in BUILTIN_ROLES
        assert "ops" in BUILTIN_ROLES

    def test_role_matches(self):
        researcher = BUILTIN_ROLES["researcher"]
        assert researcher.matches("ファイルを分析して調査する") > 0.0
        assert researcher.matches("xyzabc") == 0.0

    def test_find_best_role_coding(self):
        role = find_best_role("バグを修正してテストを実行する")
        assert role == "coder"

    def test_find_best_role_docs(self):
        role = find_best_role("READMEドキュメントを書く")
        assert role == "writer"

    def test_find_best_role_research(self):
        role = find_best_role("プロジェクトの構造を調査して分析する")
        assert role == "researcher"

    def test_find_best_role_ops(self):
        role = find_best_role("Dockerでデプロイしてサーバーを設定する")
        assert role == "ops"


# === Crew ===

class TestCrew:
    def test_create_crew(self):
        crew = Crew()
        assert crew.config.name == "default-crew"
        assert crew.bus.agents() == ["orchestrator"]

    def test_add_worker(self):
        crew = Crew()
        crew.add_worker(WorkerConfig(agent_id="w1", role="researcher"))
        assert "w1" in crew.bus.agents()

    def test_assign_task(self):
        crew = Crew()
        crew.add_worker(WorkerConfig(agent_id="w1", role="researcher"))
        result = crew.assign_task("ファイルを調査する", agent_id="w1")
        assert "w1" in result

    def test_assign_task_auto(self):
        crew = Crew()
        crew.add_worker(WorkerConfig(agent_id="coder-1", role="coder"))
        crew.add_worker(WorkerConfig(agent_id="writer-1", role="writer"))
        result = crew.assign_task("バグを修正する")
        assert "coder-1" in result

    def test_assign_task_unknown_worker(self):
        crew = Crew()
        result = crew.assign_task("何か", agent_id="nonexistent")
        assert "エラー" in result

    def test_broadcast(self):
        crew = Crew()
        crew.add_worker(WorkerConfig(agent_id="w1", role="coder"))
        crew.add_worker(WorkerConfig(agent_id="w2", role="writer"))
        crew.broadcast("テスト開始")
        # 両ワーカーにメッセージが届いている
        m1 = crew.bus.receive("w1", timeout=1.0)
        m2 = crew.bus.receive("w2", timeout=1.0)
        assert m1 is not None
        assert m2 is not None

    def test_status(self):
        crew = Crew()
        crew.add_worker(WorkerConfig(agent_id="w1", role="researcher"))
        s = crew.status()
        assert s["name"] == "default-crew"
        assert "w1" in s["workers"]
        assert s["workers"]["w1"]["role"] == "researcher"

    def test_collect_results(self):
        crew = Crew()
        crew.add_worker(WorkerConfig(agent_id="w1", role="coder"))
        # ワーカーから結果を送る
        crew.bus.send(Message(
            msg_type=MessageType.TASK_RESULT,
            sender="w1",
            receiver="orchestrator",
            content={"result": "完了"},
        ))
        results = crew.collect_results(timeout=1.0)
        assert len(results) == 1
        assert results[0]["worker"] == "w1"


class TestCrewFromYaml:
    def test_from_yaml(self, tmp_path):
        yaml_content = """# テストCrew
name: test-crew
shared_memory: data/test_shared.json
workers:
  - id: researcher-1
    role: researcher
    brain: mock
    max_iterations: 15
  - id: coder-1
    role: coder
    brain: mock
"""
        yaml_path = str(tmp_path / "crew.yaml")
        with open(yaml_path, "w") as f:
            f.write(yaml_content)

        crew = Crew.from_yaml(yaml_path)
        assert crew.config.name == "test-crew"
        assert "researcher-1" in crew.bus.agents()
        assert "coder-1" in crew.bus.agents()

    def test_from_yaml_missing_file(self, tmp_path):
        crew = Crew.from_yaml(str(tmp_path / "missing.yaml"))
        assert crew.config.name == "default-crew"


class TestSharedMemory:
    def test_store_and_recall(self, tmp_path):
        sm = SharedMemory(path=str(tmp_path / "shared.json"))
        sm.store("agent-1", "findings", "Pythonプロジェクトを発見")
        results = sm.recall("Python")
        assert len(results) > 0

    def test_get_all(self, tmp_path):
        sm = SharedMemory(path=str(tmp_path / "shared.json"))
        sm.store("a", "topic1", "データ1")
        sm.store("b", "topic2", "データ2")
        summary = sm.get_all()
        assert "データ" in summary
