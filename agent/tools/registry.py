"""ツールレジストリ — ツールの登録・検索・実行・プラグイン動的読み込み

プラグインの追加方法:
  1. agent/tools/ に Tool を継承したクラスを書く
  2. ToolRegistry.discover() で自動検出
  3. または ToolRegistry.load_plugin("path/to/plugin.py") で手動読み込み
"""

import importlib
import importlib.util
import inspect
import os
import sys
from pathlib import Path

from agent.tools.base import Tool


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """ツールを登録"""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> bool:
        """ツールを登録解除"""
        return self._tools.pop(name, None) is not None

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict]:
        return [t.to_dict() for t in self._tools.values()]

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def run(self, tool_name: str, **kwargs) -> str:
        tool = self._tools.get(tool_name)
        if tool is None:
            return f"エラー: ツールが見つかりません: {tool_name}"
        try:
            return tool.execute(**kwargs)
        except Exception as e:
            return f"ツール実行エラー [{tool_name}]: {e}"

    def discover(self, directory: str | None = None) -> list[str]:
        """ディレクトリ内のToolサブクラスを自動検出して登録。

        Returns: 新しく登録したツール名のリスト
        """
        if directory is None:
            directory = str(Path(__file__).parent)

        discovered = []
        for filename in sorted(os.listdir(directory)):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue
            if filename in ("base.py", "registry.py"):
                continue

            module_path = os.path.join(directory, filename)
            tools = self._load_tools_from_file(module_path)
            for tool in tools:
                if tool.name not in self._tools:
                    self.register(tool)
                    discovered.append(tool.name)

        return discovered

    def load_plugin(self, path: str) -> list[str]:
        """外部プラグインファイルからツールを読み込み。

        Returns: 新しく登録したツール名のリスト
        """
        if not os.path.isfile(path):
            raise FileNotFoundError(f"プラグインが見つかりません: {path}")

        tools = self._load_tools_from_file(path)
        loaded = []
        for tool in tools:
            self.register(tool)
            loaded.append(tool.name)
        return loaded

    @staticmethod
    def _load_tools_from_file(filepath: str) -> list[Tool]:
        """Pythonファイルから Tool サブクラスのインスタンスを取得"""
        module_name = Path(filepath).stem
        spec = importlib.util.spec_from_file_location(f"plugin_{module_name}", filepath)
        if spec is None or spec.loader is None:
            return []

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception:
            return []

        tools = []
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, Tool) and obj is not Tool and not inspect.isabstract(obj):
                try:
                    tools.append(obj())
                except Exception:
                    pass  # Skip tools that fail to instantiate without args
        return tools

    @staticmethod
    def create_default_registry(dry_run: bool = False) -> "ToolRegistry":
        """デフォルトのビルトインツールセットで構築"""
        from agent.tools.file_ops import FileReadTool, FileWriteTool, FileListTool
        from agent.tools.shell import ShellTool
        from agent.tools.web import WebFetchTool
        from agent.tools.notes import NoteTool

        registry = ToolRegistry()
        registry.register(FileReadTool())
        registry.register(FileWriteTool())
        registry.register(FileListTool())
        registry.register(ShellTool(dry_run=dry_run))
        registry.register(WebFetchTool())
        registry.register(NoteTool())
        return registry
