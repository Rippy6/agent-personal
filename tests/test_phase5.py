"""Phase 5 テスト — プラットフォーム（マーケットプレイス、ワークフロー、i18n）"""

import json
import os
import pytest

from agent.plugins.marketplace import PluginMarketplace, PluginInfo
from agent.workflow import Workflow, WorkflowStep, WorkflowRunner, save_workflow, load_workflow
from agent.i18n import t, set_language, get_language, available_languages, TRANSLATIONS


# === プラグインマーケットプレイス ===

class TestPluginMarketplace:
    @pytest.fixture
    def mp(self, tmp_path):
        return PluginMarketplace(
            plugins_dir=str(tmp_path / "plugins"),
            registry_path=str(tmp_path / "registry.json"),
        )

    def test_register_and_list(self, mp):
        plugin = PluginInfo(name="test-plugin", description="テスト用")
        mp.register(plugin)
        plugins = mp.list_plugins()
        assert len(plugins) == 1
        assert plugins[0].name == "test-plugin"

    def test_search(self, mp):
        mp.register(PluginInfo(name="file-tool", description="ファイル操作", tags=["file"]))
        mp.register(PluginInfo(name="web-tool", description="Web取得", tags=["web"]))
        results = mp.search("file")
        assert len(results) == 1
        assert results[0].name == "file-tool"

    def test_tag_filter(self, mp):
        mp.register(PluginInfo(name="a", description="", tags=["util"]))
        mp.register(PluginInfo(name="b", description="", tags=["io"]))
        results = mp.list_plugins(tag="util")
        assert len(results) == 1

    def test_enable_disable(self, mp):
        mp.register(PluginInfo(name="p", description=""))
        mp.disable("p")
        assert not mp._plugins["p"].enabled
        mp.enable("p")
        assert mp._plugins["p"].enabled

    def test_install_local(self, mp, tmp_path):
        plugin_file = tmp_path / "my_tool.py"
        plugin_file.write_text("# test plugin")
        result = mp.install_local("my_tool", str(plugin_file))
        assert "登録" in result

    def test_install_local_missing(self, mp):
        result = mp.install_local("missing", "/nonexistent.py")
        assert "見つかりません" in result

    def test_unregister(self, mp):
        mp.register(PluginInfo(name="rm-me", description=""))
        mp.unregister("rm-me")
        assert "rm-me" not in mp._plugins

    def test_persistence(self, tmp_path):
        path = str(tmp_path / "reg.json")
        mp1 = PluginMarketplace(registry_path=path, plugins_dir=str(tmp_path))
        mp1.register(PluginInfo(name="persist", description="永続化テスト"))

        mp2 = PluginMarketplace(registry_path=path, plugins_dir=str(tmp_path))
        assert "persist" in mp2._plugins

    def test_scan_directory(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        (plugins_dir / "auto_tool.py").write_text("# auto detected")
        (plugins_dir / "__init__.py").write_text("")  # should be ignored

        mp = PluginMarketplace(
            plugins_dir=str(plugins_dir),
            registry_path=str(tmp_path / "reg.json"),
        )
        count = mp.scan_directory()
        assert count == 1
        assert "auto_tool" in mp._plugins

    def test_get_enabled_paths(self, mp, tmp_path):
        f = tmp_path / "tool.py"
        f.write_text("")
        mp.register(PluginInfo(name="t", description="", file_path=str(f), installed=True))
        paths = mp.get_enabled_paths()
        assert len(paths) == 1


# === ワークフロー ===

class TestWorkflow:
    def test_create_workflow(self):
        wf = Workflow(name="test")
        wf.steps.append(WorkflowStep(id="s1", action="log", params={"message": "hello"}))
        wf.start_step = "s1"
        assert wf.validate() == []

    def test_validate_empty(self):
        wf = Workflow(name="")
        errors = wf.validate()
        assert any("名" in e for e in errors)

    def test_validate_missing_start(self):
        wf = Workflow(name="test")
        wf.steps.append(WorkflowStep(id="s1", action="log"))
        wf.start_step = "missing"
        errors = wf.validate()
        assert any("見つかりません" in e for e in errors)

    def test_to_dict_and_from_dict(self):
        wf = Workflow(name="roundtrip", description="テスト")
        wf.steps.append(WorkflowStep(id="s1", action="goal", params={"description": "テスト"}))
        wf.start_step = "s1"

        d = wf.to_dict()
        wf2 = Workflow.from_dict(d)
        assert wf2.name == "roundtrip"
        assert len(wf2.steps) == 1

    def test_save_and_load(self, tmp_path):
        wf = Workflow(name="file-test")
        wf.steps.append(WorkflowStep(id="s1", action="log", params={"message": "test"}))
        wf.start_step = "s1"

        path = str(tmp_path / "wf.json")
        save_workflow(wf, path)

        loaded = load_workflow(path)
        assert loaded.name == "file-test"
        assert len(loaded.steps) == 1


class TestWorkflowRunner:
    def test_run_log_step(self):
        wf = Workflow(name="test")
        wf.steps.append(WorkflowStep(id="s1", action="log", params={"message": "ログテスト"}))
        wf.start_step = "s1"

        runner = WorkflowRunner()
        results = runner.run(wf)
        assert len(results) == 1
        assert results[0]["result"] == "ログテスト"

    def test_run_chain(self):
        wf = Workflow(name="chain")
        wf.steps.append(WorkflowStep(id="s1", action="log", params={"message": "1"}, next_step="s2"))
        wf.steps.append(WorkflowStep(id="s2", action="log", params={"message": "2"}))
        wf.start_step = "s1"

        runner = WorkflowRunner()
        results = runner.run(wf)
        assert len(results) == 2

    def test_run_goal_step(self):
        wf = Workflow(name="goal-test")
        wf.steps.append(WorkflowStep(id="s1", action="goal", params={"description": "テストゴール"}))
        wf.start_step = "s1"

        runner = WorkflowRunner()
        results = runner.run(wf)
        assert "ゴール追加" in results[0]["result"]

    def test_validation_error(self):
        wf = Workflow(name="")
        runner = WorkflowRunner()
        results = runner.run(wf)
        assert "error" in results[0]

    def test_max_steps_limit(self):
        wf = Workflow(name="loop")
        wf.steps.append(WorkflowStep(id="s1", action="log", params={"message": "loop"}, next_step="s1"))
        wf.start_step = "s1"

        runner = WorkflowRunner()
        results = runner.run(wf, max_steps=5)
        assert len(results) == 5


# === i18n ===

class TestI18n:
    def test_default_language_is_ja(self):
        set_language("ja")
        assert get_language() == "ja"

    def test_translate_ja(self):
        set_language("ja")
        result = t("agent.started")
        assert result == "エージェント起動"

    def test_translate_en(self):
        set_language("en")
        result = t("agent.started")
        assert result == "Agent started"
        set_language("ja")  # reset

    def test_translate_with_params(self):
        set_language("ja")
        result = t("goal.new", description="テスト")
        assert "テスト" in result

    def test_missing_key_returns_key(self):
        result = t("nonexistent.key")
        assert result == "nonexistent.key"

    def test_available_languages(self):
        langs = available_languages()
        assert "ja" in langs
        assert "en" in langs
        assert "zh" in langs
        assert "ko" in langs

    def test_set_language_with_region(self):
        set_language("en-US")
        assert get_language() == "en"
        set_language("ja")
