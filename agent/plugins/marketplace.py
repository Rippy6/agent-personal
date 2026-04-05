"""プラグインマーケットプレイス — コミュニティ製ツールの検索・インストール・管理

プラグインはGitHubリポジトリまたはローカルファイルから読み込む。
メタデータはJSONで管理。
"""

import json
import os
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path


PLUGINS_DIR = "plugins"
REGISTRY_PATH = "data/plugin_registry.json"


@dataclass
class PluginInfo:
    """プラグインのメタデータ"""
    name: str
    description: str
    version: str = "0.1.0"
    author: str = ""
    url: str = ""  # GitHubリポジトリURL
    file_path: str = ""  # ローカルファイルパス
    installed: bool = False
    enabled: bool = True
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "url": self.url,
            "file_path": self.file_path,
            "installed": self.installed,
            "enabled": self.enabled,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PluginInfo":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class PluginMarketplace:
    """プラグインの検索・インストール・管理"""

    def __init__(
        self,
        plugins_dir: str = PLUGINS_DIR,
        registry_path: str = REGISTRY_PATH,
    ):
        self.plugins_dir = plugins_dir
        self.registry_path = registry_path
        self._plugins: dict[str, PluginInfo] = {}
        self._load_registry()

    def _load_registry(self):
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("plugins", []):
                    p = PluginInfo.from_dict(item)
                    self._plugins[p.name] = p
            except (json.JSONDecodeError, OSError):
                pass

    def _save_registry(self):
        os.makedirs(os.path.dirname(self.registry_path) or ".", exist_ok=True)
        data = {"plugins": [p.to_dict() for p in self._plugins.values()]}
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def register(self, plugin: PluginInfo):
        """プラグインを登録"""
        self._plugins[plugin.name] = plugin
        self._save_registry()

    def unregister(self, name: str):
        """プラグインを削除"""
        if name in self._plugins:
            del self._plugins[name]
            self._save_registry()

    def list_plugins(self, tag: str | None = None) -> list[PluginInfo]:
        """プラグイン一覧（タグフィルタ可）"""
        plugins = list(self._plugins.values())
        if tag:
            plugins = [p for p in plugins if tag in p.tags]
        return plugins

    def search(self, query: str) -> list[PluginInfo]:
        """キーワードでプラグインを検索"""
        query_lower = query.lower()
        return [
            p for p in self._plugins.values()
            if query_lower in p.name.lower()
            or query_lower in p.description.lower()
            or any(query_lower in t for t in p.tags)
        ]

    def install_from_url(self, name: str, url: str) -> str:
        """URLからプラグインをダウンロードしてインストール"""
        os.makedirs(self.plugins_dir, exist_ok=True)
        dest = os.path.join(self.plugins_dir, f"{name}.py")

        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read()

            # 基本的なセキュリティチェック
            text = content.decode("utf-8", errors="replace")
            dangerous = ["os.system", "subprocess.call", "eval(", "exec(", "__import__"]
            for d in dangerous:
                if d in text:
                    return f"セキュリティ警告: '{d}' が含まれています。インストールを中止しました。"

            with open(dest, "wb") as f:
                f.write(content)

            plugin = PluginInfo(
                name=name,
                description=f"URLからインストール: {url}",
                url=url,
                file_path=dest,
                installed=True,
            )
            self.register(plugin)
            return f"プラグイン '{name}' をインストールしました: {dest}"

        except Exception as e:
            return f"インストール失敗: {e}"

    def install_local(self, name: str, file_path: str) -> str:
        """ローカルファイルからプラグインをインストール"""
        if not os.path.exists(file_path):
            return f"ファイルが見つかりません: {file_path}"

        plugin = PluginInfo(
            name=name,
            description=f"ローカルプラグイン: {file_path}",
            file_path=os.path.abspath(file_path),
            installed=True,
        )
        self.register(plugin)
        return f"プラグイン '{name}' を登録しました: {file_path}"

    def enable(self, name: str) -> bool:
        if name in self._plugins:
            self._plugins[name].enabled = True
            self._save_registry()
            return True
        return False

    def disable(self, name: str) -> bool:
        if name in self._plugins:
            self._plugins[name].enabled = False
            self._save_registry()
            return True
        return False

    def get_enabled_paths(self) -> list[str]:
        """有効なプラグインのファイルパス一覧"""
        return [
            p.file_path for p in self._plugins.values()
            if p.installed and p.enabled and p.file_path
        ]

    def scan_directory(self) -> int:
        """プラグインディレクトリをスキャンして新しいプラグインを自動登録"""
        if not os.path.exists(self.plugins_dir):
            return 0

        count = 0
        for fname in os.listdir(self.plugins_dir):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            name = fname[:-3]
            if name not in self._plugins:
                fpath = os.path.join(self.plugins_dir, fname)
                self.register(PluginInfo(
                    name=name,
                    description=f"自動検出: {fname}",
                    file_path=os.path.abspath(fpath),
                    installed=True,
                ))
                count += 1
        return count
