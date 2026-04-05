"""エージェント間通信プロトコル — メッセージパッシングで協調

複数のエージェントがメッセージを送り合い、タスクを分担する。
スレッドセーフなメッセージキューで実装。
"""

import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class MessageType(Enum):
    """メッセージ種別"""
    TASK_ASSIGN = "task_assign"       # タスク割り当て
    TASK_RESULT = "task_result"       # タスク結果報告
    TASK_DECLINE = "task_decline"     # タスク拒否
    STATUS_REQUEST = "status_request" # 状態問い合わせ
    STATUS_REPORT = "status_report"   # 状態報告
    BROADCAST = "broadcast"           # 全員へのブロードキャスト
    KNOWLEDGE = "knowledge"           # 知識共有
    SHUTDOWN = "shutdown"             # 停止要求


@dataclass
class Message:
    """エージェント間メッセージ"""
    msg_type: MessageType
    sender: str
    receiver: str  # "*" でブロードキャスト
    content: dict
    msg_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: float = field(default_factory=time.time)
    reply_to: str | None = None  # 返信先のmsg_id

    def to_dict(self) -> dict:
        return {
            "msg_id": self.msg_id,
            "msg_type": self.msg_type.value,
            "sender": self.sender,
            "receiver": self.receiver,
            "content": self.content,
            "timestamp": self.timestamp,
            "reply_to": self.reply_to,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        return cls(
            msg_type=MessageType(data["msg_type"]),
            sender=data["sender"],
            receiver=data["receiver"],
            content=data.get("content", {}),
            msg_id=data.get("msg_id", uuid.uuid4().hex[:8]),
            timestamp=data.get("timestamp", time.time()),
            reply_to=data.get("reply_to"),
        )


class MessageBus:
    """エージェント間のメッセージバス（ハブ&スポーク方式）

    全エージェントが1つの MessageBus に接続し、メッセージを送受信する。
    """

    def __init__(self):
        self._queues: dict[str, queue.Queue] = {}
        self._lock = threading.Lock()
        self._history: list[Message] = []

    def register(self, agent_id: str):
        """エージェントをバスに登録"""
        with self._lock:
            if agent_id not in self._queues:
                self._queues[agent_id] = queue.Queue()

    def unregister(self, agent_id: str):
        """エージェントをバスから削除"""
        with self._lock:
            self._queues.pop(agent_id, None)

    def send(self, message: Message):
        """メッセージを送信"""
        with self._lock:
            self._history.append(message)
            # 履歴は最大1000件
            if len(self._history) > 1000:
                self._history = self._history[-1000:]

            if message.receiver == "*":
                # ブロードキャスト
                for agent_id, q in self._queues.items():
                    if agent_id != message.sender:
                        q.put(message)
            else:
                q = self._queues.get(message.receiver)
                if q:
                    q.put(message)

    def receive(self, agent_id: str, timeout: float = 0.1) -> Message | None:
        """メッセージを受信（ブロッキング）"""
        q = self._queues.get(agent_id)
        if not q:
            return None
        try:
            return q.get(timeout=timeout)
        except queue.Empty:
            return None

    def receive_all(self, agent_id: str) -> list[Message]:
        """溜まっている全メッセージを取得"""
        q = self._queues.get(agent_id)
        if not q:
            return []
        messages = []
        while True:
            try:
                messages.append(q.get_nowait())
            except queue.Empty:
                break
        return messages

    def agents(self) -> list[str]:
        """登録済みエージェント一覧"""
        with self._lock:
            return list(self._queues.keys())

    def history(self, limit: int = 20) -> list[dict]:
        """メッセージ履歴"""
        with self._lock:
            return [m.to_dict() for m in self._history[-limit:]]
