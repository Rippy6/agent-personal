"""ファイル操作ツール — 読み込み・書き込み・一覧"""

import os
import glob as globmod
from agent.tools.base import Tool


class FileReadTool(Tool):
    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return "ファイルの内容を読み込む"

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
        if not path:
            return "エラー: pathが指定されていません"
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            lines = content.count("\n") + 1
            return f"[{path}] ({lines}行)\n{content}"
        except FileNotFoundError:
            return f"エラー: ファイルが見つかりません: {path}"
        except Exception as e:
            return f"エラー: {e}"


class FileWriteTool(Tool):
    @property
    def name(self) -> str:
        return "file_write"

    @property
    def description(self) -> str:
        return "ファイルに内容を書き込む（新規作成または上書き）"

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
        if not path:
            return "エラー: pathが指定されていません"
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"ファイルを書き込みました: {path} ({len(content)}文字)"
        except Exception as e:
            return f"エラー: {e}"


class FileListTool(Tool):
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
        try:
            full_pattern = os.path.join(directory, pattern)
            entries = sorted(globmod.glob(full_pattern))
            if not entries:
                return f"ファイルが見つかりません: {full_pattern}"
            result = []
            for entry in entries:
                if os.path.isdir(entry):
                    result.append(f"  📁 {entry}/")
                else:
                    size = os.path.getsize(entry)
                    result.append(f"  📄 {entry} ({size}B)")
            return f"[{directory}] {len(entries)}件:\n" + "\n".join(result)
        except Exception as e:
            return f"エラー: {e}"
