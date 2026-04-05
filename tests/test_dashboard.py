"""Web UIダッシュボードのテスト"""

import json
import threading
import time
import urllib.request
import urllib.error
import pytest

from agent.web.server import DashboardState, start_dashboard


class TestDashboardState:
    def test_initial_state(self):
        state = DashboardState()
        d = state.to_dict()
        assert d["logs"] == []
        assert d["goals"] == []
        assert d["stats"] == {}
        assert d["is_running"] is False
        assert d["brain_name"] == ""

    def test_add_log(self):
        state = DashboardState()
        state.add_log("think", "テスト思考")
        d = state.to_dict()
        assert len(d["logs"]) == 1
        assert d["logs"][0]["phase"] == "think"
        assert d["logs"][0]["message"] == "テスト思考"
        assert "timestamp" in d["logs"][0]

    def test_log_limit(self):
        state = DashboardState()
        for i in range(250):
            state.add_log("act", f"アクション{i}")
        d = state.to_dict()
        # to_dict returns last 50, but internal keeps 200
        assert len(d["logs"]) == 50

    def test_update_goals(self):
        state = DashboardState()
        goals = [{"id": "1", "description": "テスト", "status": "active"}]
        state.update_goals(goals)
        d = state.to_dict()
        assert d["goals"] == goals

    def test_update_stats(self):
        state = DashboardState()
        stats = {"actions": 5, "errors": 1}
        state.update_stats(stats)
        d = state.to_dict()
        assert d["stats"]["actions"] == 5

    def test_pending_goals(self):
        state = DashboardState()
        state.add_goal_from_ui("ゴール1")
        state.add_goal_from_ui("ゴール2")
        goals = state.pop_pending_goals()
        assert goals == ["ゴール1", "ゴール2"]
        # Second pop should be empty
        assert state.pop_pending_goals() == []

    def test_thread_safety(self):
        state = DashboardState()
        errors = []

        def writer():
            try:
                for i in range(100):
                    state.add_log("act", f"msg{i}")
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(100):
                    state.to_dict()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(3)]
        threads += [threading.Thread(target=reader) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []


class TestDashboardServer:
    @pytest.fixture(autouse=True)
    def setup_server(self):
        """Start server on port 0 (OS picks a free port)"""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        self.port = sock.getsockname()[1]
        sock.close()
        try:
            self.server = start_dashboard(port=self.port)
        except OSError:
            pytest.skip("Port in use")
        yield
        self.server.shutdown()

    def _get(self, path: str) -> tuple[int, str]:
        url = f"http://127.0.0.1:{self.port}{path}"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def test_dashboard_page(self):
        status, body = self._get("/")
        assert status == 200
        assert "Agent Dashboard" in body

    def test_api_state(self):
        status, body = self._get("/api/state")
        assert status == 200
        data = json.loads(body)
        assert "logs" in data
        assert "goals" in data
        assert "stats" in data

    def test_post_goal(self):
        url = f"http://127.0.0.1:{self.port}/api/goal"
        payload = json.dumps({"goal": "テストゴール"}).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200

    def test_404(self):
        status, _ = self._get("/nonexistent")
        assert status == 404


class TestLoggerDashboard:
    def test_logger_forwards_to_dashboard(self):
        from agent.utils.logger import AgentLogger

        state = DashboardState()
        logger = AgentLogger(verbose=False)
        logger.set_dashboard(state)

        logger.think("ダッシュボードテスト")
        d = state.to_dict()
        assert len(d["logs"]) == 1
        assert d["logs"][0]["phase"] == "think"
        assert d["logs"][0]["message"] == "ダッシュボードテスト"

    def test_logger_without_dashboard(self):
        from agent.utils.logger import AgentLogger
        logger = AgentLogger()
        # Should not raise
        logger.think("テスト")
