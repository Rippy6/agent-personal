"""ファイル操作ツール — 読み込み・書き込み・一覧（パストラバーサル防止付き）"""

import os
import glob as globmod
from pathlib import Path
from agent.tools.base import Tool


MAX_READ_BYTES = 1_000_000  # 1MB
MAX_WRITE_BYTES = 5_000_000  # 5MB


def _safe_resolve(path: str, base_dir: str | None = None) -> tuple[str, str | None]:
    """パスを安全に解決。パストラバーサル攻撃を防止。

    Returns:
        (resolved_path, error_message)
    """
    if not path:
        return "", "パスが空です"

    base = Path(base_dir or os.getcwd()).resolve()
    try:
        resolved = (base / path).resolve()
    except (OSError, ValueError) as e:
        return "", f"不正なパス: {e}"

    # Symlink resolution — ensure final path is still under base
    if not str(resolved).startswith(str(base)):
        return "", f"アクセス拒否: 許可されたディレクトリの外です ({resolved})"

    return str(resolved), None


class FileReadTool(Tool):
    """ファイル読み込みツール（サイズ制限・パス安全チェック付き）"""

    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir

    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return "ファイルの内容を読み込む（最大1MB）"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "読み込むファイルのパス"},
            },
            "required": ["path"],
        }

    def execute(self, **kwargs) -> str:
        path = kwargs.get("path", "")
        resolved, err = _safe_resolve(path, self.base_dir)
        if err:
            return f"エラー: {err}"

        if not os.path.isfile(resolved):
            return f"エラー: ファイルが見つかりません: {path}"

        size = os.path.getsize(resolved)
        if size > MAX_READ_BYTES:
            return f"エラー: ファイルが大きすぎます ({size:,}B > {MAX_READ_BYTES:,}B上限)"

        try:
            with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            lines = content.count("\n") + 1
            return f"[{path}] ({lines}行, {size:,}B)\n{content}"
        except OSError as e:
            return f"エラー: {e}"


class FileWriteTool(Tool):
    """ファイル書き込みツール（サイズ制限・パス安全チェック付き）"""

    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir

    @property
    def name(self) -> str:
        return "file_write"

    @property
    def description(self) -> str:
        return "ファイルに内容を書き込む（新規作成または上書き、最大5MB）"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "書き込み先のファイルパス"},
                "content": {"type": "string", "description": "書き込む内容"},
            },
            "required": ["path", "content"],
        }

    def execute(self, **kwargs) -> str:
        path = kwargs.get("path", "")
        content = kwargs.get("content", "")
        resolved, err = _safe_resolve(path, self.base_dir)
        if err:
            return f"エラー: {err}"

        if len(content.encode("utf-8")) > MAX_WRITE_BYTES:
            return f"エラー: 書き込み内容が大きすぎます (上限: {MAX_WRITE_BYTES:,}B)"

        try:
            parent = os.path.dirname(resolved)
            if parent:
                os.makedirs(parent, exist_ok=True)
            existed = os.path.exists(resolved)
            with open(resolved, "w", encoding="utf-8") as f:
                f.write(content)
            action = "上書き" if existed else "作成"
            return f"ファイルを{action}しました: {path} ({len(content):,}文字)"
        except OSError as e:
            return f"エラー: {e}"


class FileListTool(Tool):
    """ディレクトリ一覧ツール（パス安全チェック付き）"""

    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir

    @property
    def name(self) -> str:
        return "file_list"

    @property
    def description(self) -> str:
        return "ディレクトリ内のファイル一覧を取得する"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "対象ディレクトリ", "default": "."},
                "pattern": {"type": "string", "description": "globパターン", "default": "*"},
            },
        }

    def execute(self, **kwargs) -> str:
        directory = kwargs.get("directory", ".")
        pattern = kwargs.get("pattern", "*")
        resolved, err = _safe_resolve(directory, self.base_dir)
        if err:
            return f"エラー: {err}"

        try:
            full_pattern = os.path.join(resolved, pattern)
            entries = sorted(globmod.glob(full_pattern))
            if not entries:
                return f"ファイルが見つかりません: {directory}/{pattern}"
            result = []
            for entry in entries[:200]:  # 最大200件
                display = os.path.relpath(entry)
                if os.path.isdir(entry):
                    result.append(f"  📁 {display}/")
                else:
                    try:
                        size = os.path.getsize(entry)
                        result.append(f"  📄 {display} ({size:,}B)")
                    except OSError:
                        result.append(f"  📄 {display}")
            total_note = f" (上位200件)" if len(entries) > 200 else ""
            return f"[{directory}] {len(entries)}件{total_note}:\n" + "\n".join(result)
        except OSError as e:
            return f"エラー: {e}"
