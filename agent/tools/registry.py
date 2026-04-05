"""ツールレジストリ — ツールの登録・検索・実行"""

from agent.tools.base import Tool


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

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

    @staticmethod
    def create_default_registry(dry_run: bool = False) -> "ToolRegistry":
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
