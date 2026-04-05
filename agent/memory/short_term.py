"""短期記憶 — セッション内のイベントコンテキスト"""

from collections import deque
from datetime import datetime


class ShortTermMemory:
    def __init__(self, maxlen: int = 50):
        self._events: deque[dict] = deque(maxlen=maxlen)

    def add(self, phase: str, content: str, metadata: dict | None = None):
        event = {
            "timestamp": datetime.now().isoformat(),
            "phase": phase,
            "content": content,
            "metadata": metadata or {},
        }
        self._events.append(event)

    def get_recent(self, n: int = 10) -> list[dict]:
        items = list(self._events)
        return items[-n:]

    def get_context_summary(self) -> str:
        if not self._events:
            return "（まだ何も起きていない）"
        lines = []
        for event in self._events:
            phase = event["phase"]
            content = event["content"]
            # Keep it concise
            if len(content) > 200:
                content = content[:200] + "..."
            lines.append(f"[{phase}] {content}")
        return "\n".join(lines)

    def get_last_action_result(self) -> str | None:
        for event in reversed(self._events):
            if event["phase"] == "act_result":
                return event["content"]
        return None

    def clear(self):
        self._events.clear()

    def __len__(self) -> int:
        return len(self._events)
