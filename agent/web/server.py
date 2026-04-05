"""Web UIダッシュボード — ブラウザからエージェントを監視・操作

stdlib のみで実装（外部依存なし）。
http.server + threading でAPIとフロントエンドを提供。
"""

import json
import os
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse


class DashboardState:
    """エージェントの状態を保持し、Web UIに提供するブリッジ"""

    def __init__(self):
        self.logs: list[dict] = []
        self.goals: list[dict] = []
        self.stats: dict = {}
        self.is_running: bool = False
        self.brain_name: str = ""
        self.pending_goals: list[str] = []  # UIから追加されたゴール
        self._lock = threading.Lock()

    def add_log(self, phase: str, message: str):
        with self._lock:
            self.logs.append({
                "phase": phase,
                "message": message,
                "timestamp": time.time(),
            })
            # Keep last 200 logs
            if len(self.logs) > 200:
                self.logs = self.logs[-200:]

    def update_goals(self, goals: list[dict]):
        with self._lock:
            self.goals = goals

    def update_stats(self, stats: dict):
        with self._lock:
            self.stats = stats

    def add_goal_from_ui(self, description: str):
        with self._lock:
            self.pending_goals.append(description)

    def pop_pending_goals(self) -> list[str]:
        with self._lock:
            goals = list(self.pending_goals)
            self.pending_goals.clear()
            return goals

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "logs": self.logs[-50:],
                "goals": self.goals,
                "stats": self.stats,
                "is_running": self.is_running,
                "brain_name": self.brain_name,
            }


# Global state instance
dashboard_state = DashboardState()

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agent Dashboard</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  :root { --bg:#0a0a0f; --surface:#13131a; --card:#1a1a25; --accent:#6c5ce7;
          --accent2:#00cec9; --text:#e8e8f0; --dim:#8888aa; --green:#27c93f;
          --red:#ff5f56; --yellow:#ffbd2e; }
  body { font-family:system-ui,-apple-system,sans-serif; background:var(--bg);
         color:var(--text); min-height:100vh; }
  .header { background:var(--surface); padding:16px 24px; border-bottom:1px solid #222;
            display:flex; justify-content:space-between; align-items:center; }
  .header h1 { font-size:1.3rem; }
  .status { display:flex; align-items:center; gap:8px; }
  .status-dot { width:10px; height:10px; border-radius:50%; }
  .status-dot.on { background:var(--green); animation:pulse 2s infinite; }
  .status-dot.off { background:var(--red); }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }
  .main { display:grid; grid-template-columns:1fr 300px; gap:16px; padding:16px; height:calc(100vh - 60px); }
  .log-panel { background:var(--surface); border-radius:12px; overflow:hidden;
               display:flex; flex-direction:column; }
  .log-header { padding:12px 16px; border-bottom:1px solid #222; font-weight:700; }
  .log-body { flex:1; overflow-y:auto; padding:12px; font-family:'Courier New',monospace;
              font-size:0.85rem; line-height:1.8; }
  .log-entry { padding:2px 0; opacity:0; animation:fadeIn 0.3s forwards; }
  @keyframes fadeIn { to{opacity:1} }
  .log-entry .phase { font-weight:700; margin-right:8px; }
  .phase-observe { color:var(--dim); } .phase-think { color:var(--accent); }
  .phase-plan { color:var(--yellow); } .phase-act { color:var(--green); }
  .phase-reflect { color:#fd79a8; } .phase-system { color:var(--accent2); }
  .phase-goal { color:var(--yellow); } .phase-error { color:var(--red); }
  .sidebar { display:flex; flex-direction:column; gap:12px; }
  .card { background:var(--surface); border-radius:12px; padding:16px; }
  .card h3 { font-size:0.9rem; color:var(--dim); margin-bottom:12px; }
  .stat-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
  .stat { text-align:center; }
  .stat-value { font-size:1.5rem; font-weight:700; color:var(--accent); }
  .stat-label { font-size:0.75rem; color:var(--dim); }
  .goal-list { max-height:200px; overflow-y:auto; }
  .goal-item { padding:6px 0; border-bottom:1px solid #222; font-size:0.85rem; }
  .goal-item .icon { margin-right:6px; }
  .goal-input { display:flex; gap:8px; margin-top:12px; }
  .goal-input input { flex:1; background:var(--card); border:1px solid #333;
    border-radius:8px; padding:8px 12px; color:var(--text); font-size:0.85rem; }
  .goal-input button { background:var(--accent); color:white; border:none;
    border-radius:8px; padding:8px 16px; cursor:pointer; font-size:0.85rem; }
  .goal-input button:hover { opacity:0.8; }
  @media(max-width:768px) { .main{grid-template-columns:1fr;} }
</style>
</head>
<body>
<div class="header">
  <h1>🤖 Agent Dashboard</h1>
  <div class="status">
    <div class="status-dot" id="statusDot"></div>
    <span id="statusText">接続中...</span>
    <span style="color:var(--dim);margin-left:12px" id="brainName"></span>
  </div>
</div>
<div class="main">
  <div class="log-panel">
    <div class="log-header">📋 エージェントログ</div>
    <div class="log-body" id="logBody"></div>
  </div>
  <div class="sidebar">
    <div class="card">
      <h3>📊 統計</h3>
      <div class="stat-grid">
        <div class="stat"><div class="stat-value" id="statActions">0</div><div class="stat-label">アクション</div></div>
        <div class="stat"><div class="stat-value" id="statGoals">0</div><div class="stat-label">完了ゴール</div></div>
        <div class="stat"><div class="stat-value" id="statIter">0</div><div class="stat-label">イテレーション</div></div>
        <div class="stat"><div class="stat-value" id="statErrors">0</div><div class="stat-label">エラー</div></div>
      </div>
    </div>
    <div class="card" style="flex:1;">
      <h3>🎯 ゴール</h3>
      <div class="goal-list" id="goalList"></div>
      <div class="goal-input">
        <input type="text" id="goalInput" placeholder="新しいゴール..." onkeydown="if(event.key==='Enter')addGoal()">
        <button onclick="addGoal()">追加</button>
      </div>
    </div>
  </div>
</div>
<script>
const ICONS={observe:'🔍',think:'💭',plan:'📋',act:'⚡',reflect:'📝',system:'🔧',goal:'🎯',error:'❌'};
const GOAL_ICONS={pending:'⏳',active:'🔄',done:'✅',failed:'❌'};
let lastLogCount=0;

async function fetchState(){
  try{
    const r=await fetch('/api/state');
    const d=await r.json();
    document.getElementById('statusDot').className='status-dot '+(d.is_running?'on':'off');
    document.getElementById('statusText').textContent=d.is_running?'実行中':'停止中';
    document.getElementById('brainName').textContent=d.brain_name;
    document.getElementById('statActions').textContent=d.stats.actions||0;
    document.getElementById('statGoals').textContent=d.stats.goals_completed||0;
    document.getElementById('statIter').textContent=d.stats.iterations||0;
    document.getElementById('statErrors').textContent=d.stats.errors||0;
    if(d.logs.length!==lastLogCount){
      const body=document.getElementById('logBody');
      body.innerHTML=d.logs.map(l=>`<div class="log-entry"><span class="phase phase-${l.phase}">${ICONS[l.phase]||'•'}</span>${esc(l.message)}</div>`).join('');
      body.scrollTop=body.scrollHeight;
      lastLogCount=d.logs.length;
    }
    const gl=document.getElementById('goalList');
    gl.innerHTML=d.goals.map(g=>`<div class="goal-item"><span class="icon">${GOAL_ICONS[g.status]||'?'}</span>${esc(g.description)}</div>`).join('')||'<div style="color:var(--dim)">ゴールなし</div>';
  }catch(e){}
}

function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

async function addGoal(){
  const input=document.getElementById('goalInput');
  const goal=input.value.trim();
  if(!goal)return;
  await fetch('/api/goal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({goal})});
  input.value='';
}

setInterval(fetchState,1000);
fetchState();
</script>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/" or parsed.path == "/dashboard":
            self._respond(200, "text/html", DASHBOARD_HTML)
        elif parsed.path == "/api/state":
            data = json.dumps(dashboard_state.to_dict(), ensure_ascii=False)
            self._respond(200, "application/json", data)
        else:
            self._respond(404, "text/plain", "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/goal":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                goal = data.get("goal", "").strip()
                if goal:
                    dashboard_state.add_goal_from_ui(goal)
                    self._respond(200, "application/json", '{"ok":true}')
                else:
                    self._respond(400, "application/json", '{"error":"empty goal"}')
            except json.JSONDecodeError:
                self._respond(400, "application/json", '{"error":"invalid json"}')
        else:
            self._respond(404, "text/plain", "Not Found")

    def _respond(self, code: int, content_type: str, body: str):
        self.send_response(code)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Suppress default logging


def start_dashboard(port: int = 8080) -> HTTPServer:
    """ダッシュボードサーバーをバックグラウンドで起動"""
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
