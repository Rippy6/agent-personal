"""FileOpsツールのテスト — パストラバーサル防止・読み書き"""

import os
import tempfile
import pytest
from agent.tools.file_ops import FileReadTool, FileWriteTool, FileListTool, _safe_resolve


class TestSafeResolve:
    """パストラバーサル防止テスト"""

    def test_normal_path(self, tmp_path):
        resolved, err = _safe_resolve("test.txt", str(tmp_path))
        assert err is None
        assert str(tmp_path) in resolved

    def test_traversal_blocked(self, tmp_path):
        _, err = _safe_resolve("../../etc/passwd", str(tmp_path))
        assert err is not None
        assert "アクセス拒否" in err

    def test_absolute_path_outside_base(self, tmp_path):
        _, err = _safe_resolve("/etc/passwd", str(tmp_path))
        assert err is not None

    def test_empty_path(self, tmp_path):
        _, err = _safe_resolve("", str(tmp_path))
        assert err is not None


class TestFileReadTool:
    def test_read_existing_file(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("Hello World", encoding="utf-8")
        tool = FileReadTool(base_dir=str(tmp_path))
        result = tool.execute(path="hello.txt")
        assert "Hello World" in result
        assert "1行" in result

    def test_read_missing_file(self, tmp_path):
        tool = FileReadTool(base_dir=str(tmp_path))
        result = tool.execute(path="nonexistent.txt")
        assert "エラー" in result

    def test_read_empty_path(self, tmp_path):
        tool = FileReadTool(base_dir=str(tmp_path))
        result = tool.execute(path="")
        assert "エラー" in result

    def test_traversal_blocked(self, tmp_path):
        tool = FileReadTool(base_dir=str(tmp_path))
        result = tool.execute(path="../../etc/passwd")
        assert "エラー" in result


class TestFileWriteTool:
    def test_write_new_file(self, tmp_path):
        tool = FileWriteTool(base_dir=str(tmp_path))
        result = tool.execute(path="output.txt", content="test content")
        assert "作成" in result
        assert (tmp_path / "output.txt").read_text() == "test content"

    def test_overwrite_file(self, tmp_path):
        f = tmp_path / "existing.txt"
        f.write_text("old", encoding="utf-8")
        tool = FileWriteTool(base_dir=str(tmp_path))
        result = tool.execute(path="existing.txt", content="new")
        assert "上書き" in result
        assert f.read_text() == "new"

    def test_write_creates_subdirectories(self, tmp_path):
        tool = FileWriteTool(base_dir=str(tmp_path))
        tool.execute(path="sub/dir/file.txt", content="nested")
        assert (tmp_path / "sub" / "dir" / "file.txt").read_text() == "nested"

    def test_traversal_blocked(self, tmp_path):
        tool = FileWriteTool(base_dir=str(tmp_path))
        result = tool.execute(path="../../evil.txt", content="hack")
        assert "エラー" in result


class TestFileListTool:
    def test_list_directory(self, tmp_path):
        (tmp_path / "a.txt").touch()
        (tmp_path / "b.py").touch()
        (tmp_path / "subdir").mkdir()
        tool = FileListTool(base_dir=str(tmp_path))
        result = tool.execute(directory=".")
        assert "3件" in result

    def test_list_empty_directory(self, tmp_path):
        (tmp_path / "empty").mkdir()
        tool = FileListTool(base_dir=str(tmp_path))
        result = tool.execute(directory="empty")
        assert "見つかりません" in result

    def test_glob_pattern(self, tmp_path):
        (tmp_path / "a.py").touch()
        (tmp_path / "b.py").touch()
        (tmp_path / "c.txt").touch()
        tool = FileListTool(base_dir=str(tmp_path))
        result = tool.execute(directory=".", pattern="*.py")
        assert "2件" in result
