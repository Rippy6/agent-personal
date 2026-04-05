"""シェルコマンド実行ツール — 安全チェック付き"""

import re
import subprocess
from agent.tools.base import Tool


BLOCKED_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"mkfs\.",
    r"dd\s+if=",
    r":\(\)\s*\{",          # fork bomb
    r">\s*/dev/sd",
    r"chmod\s+-R\s+777\s+/",
    r"wget.*\|\s*sh",
    r"curl.*\|\s*sh",
]

CAUTION_PATTERNS = [
    r"rm\s+",
    r"mv\s+",
    r"chmod\s+",
    r"chown\s+",
    r"kill\s+",
    r"pip\s+install",
    r"apt\s+",
    r"sudo\s+",
]


class ShellTool(Tool):
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return "シェルコマンドを実行する（安全チェック付き）"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "実行するコマンド"},
                "timeout": {"type": "integer", "description": "タイムアウト秒数", "default": 30},
            },
            "required": ["command"],
        }

    def _is_blocked(self, command: str) -> str | None:
        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, command):
                return f"ブロックされたコマンド (パターン: {pattern})"
        return None

    def _is_caution(self, command: str) -> bool:
        return any(re.search(p, command) for p in CAUTION_PATTERNS)

    def execute(self, **kwargs) -> str:
        command = kwargs.get("command", "")
        timeout = kwargs.get("timeout", 30)
        if not command:
            return "エラー: commandが指定されていません"

        blocked = self._is_blocked(command)
        if blocked:
            return f"⛔ 安全チェック: {blocked}\nコマンド: {command}"

        if self.dry_run:
            caution = " ⚠️ 要注意" if self._is_caution(command) else ""
            return f"[dry-run] 実行予定: {command}{caution}"

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += f"\n[stderr] {result.stderr}"
            if result.returncode != 0:
                output += f"\n[終了コード: {result.returncode}]"
            return output.strip() or "(出力なし)"
        except subprocess.TimeoutExpired:
            return f"エラー: タイムアウト ({timeout}秒)"
        except Exception as e:
            return f"エラー: {e}"
