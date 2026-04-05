"""シェルコマンド実行ツール — 多層セキュリティ付き

セキュリティレイヤー:
1. コマンドの正規化（空白圧縮、制御文字除去）
2. 危険パターンのブロックリスト
3. メタ文字によるインジェクション検出
4. dry-run モード
5. 出力サイズ制限
6. タイムアウト制御
"""

import re
import shlex
import subprocess
from agent.tools.base import Tool


# 絶対にブロックするパターン（正規化後のコマンドに適用）
BLOCKED_PATTERNS = [
    r"rm\s+(-\w+\s+)*(/|/\w+)$",  # rm -rf / 系
    r"rm\s+(-\w+\s+)*~",           # ホームディレクトリ削除
    r"mkfs\b",
    r"\bdd\b.*\bif=",
    r":\(\)\s*\{",                  # fork bomb
    r">\s*/dev/sd",
    r"chmod\s+(-\w+\s+)*777\s+/",
    r"\bwget\b.*\|\s*(ba)?sh",
    r"\bcurl\b.*\|\s*(ba)?sh",
    r"\bsudo\s+rm\b",
    r"\bformat\b.*[cCdD]:",         # Windows format
    r">\s*/etc/",                    # システムファイル上書き
    r"\bshutdown\b",
    r"\breboot\b",
    r"\binit\s+0",
]

# 注意が必要なパターン（dry-runモード時に警告表示）
CAUTION_PATTERNS = [
    r"\brm\b",
    r"\bmv\b",
    r"\bchmod\b",
    r"\bchown\b",
    r"\bkill\b",
    r"\bpip\s+install\b",
    r"\bapt\b",
    r"\bsudo\b",
    r"\bgit\s+push\b",
    r"\bgit\s+reset\b",
]

# シェルインジェクションに使われるメタ文字パターン
INJECTION_PATTERNS = [
    r"`[^`]+`",             # バッククォート実行
    r"\$\([^)]+\)",         # $() コマンド置換
    r";\s*\w+",             # セミコロン連結
    r"\|\|?\s*\w+",         # パイプ・OR連結は許可するが記録
]

MAX_OUTPUT_BYTES = 50_000  # 出力上限 50KB


class ShellTool(Tool):
    """シェルコマンド実行ツール（多層セキュリティ付き）"""

    def __init__(self, dry_run: bool = False, allowed_dirs: list[str] | None = None):
        self.dry_run = dry_run
        self.allowed_dirs = allowed_dirs  # 将来的にサンドボックス用
        self._execution_log: list[dict] = []

    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return "シェルコマンドを実行する（多層セキュリティ付き）"

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

    @staticmethod
    def _normalize(command: str) -> str:
        """コマンドを正規化: 制御文字除去、空白圧縮"""
        # Remove control characters
        command = re.sub(r"[\x00-\x08\x0e-\x1f\x7f]", "", command)
        # Collapse whitespace
        command = re.sub(r"\s+", " ", command).strip()
        return command

    def _is_blocked(self, command: str) -> str | None:
        """ブロックリストとの照合"""
        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return f"危険なコマンドパターンを検出: {pattern}"
        return None

    def _detect_injection(self, command: str) -> list[str]:
        """インジェクションの兆候を検出"""
        warnings = []
        for pattern in INJECTION_PATTERNS:
            matches = re.findall(pattern, command)
            if matches:
                warnings.append(f"メタ文字検出: {matches[0][:30]}")
        return warnings

    def _is_caution(self, command: str) -> bool:
        return any(re.search(p, command) for p in CAUTION_PATTERNS)

    def execute(self, **kwargs) -> str:
        command = kwargs.get("command", "")
        timeout = min(kwargs.get("timeout", 30), 120)  # 最大120秒
        if not command:
            return "エラー: commandが指定されていません"

        # Step 1: Normalize
        command = self._normalize(command)

        # Step 2: Block check
        blocked = self._is_blocked(command)
        if blocked:
            self._log(command, "blocked", blocked)
            return f"⛔ 安全チェック: {blocked}\nコマンド: {command}"

        # Step 3: Injection detection
        injection_warnings = self._detect_injection(command)

        # Step 4: Dry-run
        if self.dry_run:
            caution = " ⚠️ 要注意" if self._is_caution(command) else ""
            warnings_str = ""
            if injection_warnings:
                warnings_str = "\n⚠️ " + "; ".join(injection_warnings)
            self._log(command, "dry-run")
            return f"[dry-run] 実行予定: {command}{caution}{warnings_str}"

        # Step 5: Execute
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=None,
                env=None,  # inherit parent env
            )

            # Step 6: Output size limit
            output = ""
            if result.stdout:
                output += result.stdout[:MAX_OUTPUT_BYTES]
                if len(result.stdout) > MAX_OUTPUT_BYTES:
                    output += f"\n... (出力が{MAX_OUTPUT_BYTES}バイトを超えたため省略)"
            if result.stderr:
                stderr = result.stderr[:10_000]
                output += f"\n[stderr] {stderr}"
            if result.returncode != 0:
                output += f"\n[終了コード: {result.returncode}]"

            result_str = output.strip() or "(出力なし)"
            self._log(command, "success" if result.returncode == 0 else "error")
            return result_str

        except subprocess.TimeoutExpired:
            self._log(command, "timeout")
            return f"エラー: タイムアウト ({timeout}秒)"
        except OSError as e:
            self._log(command, "os_error")
            return f"エラー: {e}"

    def _log(self, command: str, status: str, detail: str = ""):
        self._execution_log.append({
            "command": command,
            "status": status,
            "detail": detail,
        })

    def get_execution_log(self) -> list[dict]:
        return list(self._execution_log)
