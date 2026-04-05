"""Web取得ツール — URLからコンテンツを取得"""

import urllib.request
import urllib.error
from agent.tools.base import Tool


class WebFetchTool(Tool):
    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "URLからコンテンツを取得する"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "取得するURL"},
            },
            "required": ["url"],
        }

    def execute(self, **kwargs) -> str:
        url = kwargs.get("url", "")
        if not url:
            return "エラー: urlが指定されていません"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AgentPersonal/0.1"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode("utf-8", errors="replace")
                # Truncate if too long
                if len(content) > 5000:
                    content = content[:5000] + "\n... (以下省略)"
                return f"[{resp.status}] {url}\n{content}"
        except urllib.error.HTTPError as e:
            return f"HTTPエラー: {e.code} {e.reason}"
        except urllib.error.URLError as e:
            return f"URLエラー: {e.reason}"
        except Exception as e:
            return f"エラー: {e}"
