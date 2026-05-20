"""HabitGrid — Habit tracker with GitHub-style heatmap calendar."""
from __future__ import annotations
import json, sqlite3, time
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="HabitGrid", version="1.0.0")
DB = Path(__file__).parent / "habitgrid.db"

def get_db():
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            emoji TEXT DEFAULT '✅',
            color TEXT DEFAULT '#10b981',
            created_at REAL
        );
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER,
            done_date TEXT,
            note TEXT DEFAULT '',
            created_at REAL,
            FOREIGN KEY (habit_id) REFERENCES habits(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()

init_db()

class HabitIn(BaseModel):
    name: str
    emoji: str = "✅"
    color: str = "#10b981"

class LogIn(BaseModel):
    note: str = ""

@app.get("/api/habits")
def list_habits():
    conn = get_db()
    habits = [dict(r) for r in conn.execute("SELECT * FROM habits ORDER BY created_at DESC").fetchall()]
    for h in habits:
        logs = conn.execute("SELECT done_date,note FROM logs WHERE habit_id=? ORDER BY done_date DESC", (h["id"],)).fetchall()
        h["logs"] = [dict(r) for r in logs]
        h["total_done"] = len(h["logs"])
        dates = [r["done_date"] for r in logs]
        h["streak"] = calc_streak(dates)
    conn.close()
    return habits

def calc_streak(dates: list[str]) -> int:
    if not dates: return 0
    today = time.strftime("%Y-%m-%d")
    streak = 0
    d = today
    date_set = set(dates)
    # Check if today or yesterday is done to start streak
    if today not in date_set:
        from datetime import datetime, timedelta
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if yesterday not in date_set: return 0
        d = yesterday
    from datetime import datetime, timedelta
    dt = datetime.strptime(d, "%Y-%m-%d")
    while dt.strftime("%Y-%m-%d") in date_set:
        streak += 1
        dt -= timedelta(days=1)
    return streak

@app.post("/api/habits")
def create_habit(body: HabitIn):
    conn = get_db()
    conn.execute("INSERT INTO habits (name,emoji,color,created_at) VALUES (?,?,?,?)", (body.name, body.emoji, body.color, time.time()))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.delete("/api/habits/{hid}")
def delete_habit(hid: int):
    conn = get_db()
    conn.execute("DELETE FROM logs WHERE habit_id=?", (hid,))
    conn.execute("DELETE FROM habits WHERE id=?", (hid,))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.post("/api/habits/{hid}/log")
def toggle_log(hid: int, body: LogIn = LogIn()):
    conn = get_db()
    today = time.strftime("%Y-%m-%d")
    existing = conn.execute("SELECT id FROM logs WHERE habit_id=? AND done_date=?", (hid, today)).fetchone()
    if existing:
        conn.execute("DELETE FROM logs WHERE id=?", (existing["id"],))
        conn.commit()
        conn.close()
        return {"done": False}
    conn.execute("INSERT INTO logs (habit_id,done_date,note,created_at) VALUES (?,?,?,?)", (hid, today, body.note, time.time()))
    conn.commit()
    conn.close()
    return {"done": True}

@app.get("/api/habits/{hid}/heatmap")
def heatmap(hid: int, days: int = 365):
    conn = get_db()
    rows = conn.execute("SELECT done_date,COUNT(*) as cnt FROM logs WHERE habit_id=? GROUP BY done_date", (hid,)).fetchall()
    conn.close()
    return {r["done_date"]: r["cnt"] for r in rows}

@app.get("/health")
def health(): return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
def index(): return HTML

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HabitGrid</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='1' x2='0.5' y2='0'%3E%3Cstop offset='0%25' stop-color='%23ef4444'/%3E%3Cstop offset='50%25' stop-color='%23f97316'/%3E%3Cstop offset='100%25' stop-color='%23facc15'/%3E%3C/linearGradient%3E%3C/defs%3E%3Cpath d='M12 2C9 7 5 10 5 15c0 3.87 3.13 7 7 7s7-3.13 7-7c0-5-4-8-7-13zm0 18c-2.76 0-5-2.24-5-5 0-2 2-3.5 3.5-5.5.5-.7 1.5-.7 2 0 1.5 2 3.5 3.5 3.5 5.5 0 2.76-2.24 5-5 5z' fill='url(%23g)'/%3E%3C/svg%3E">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#0c1222;--surface:#141b2d;--card:#1a2236;--border:#1e293b;--text:#e2e8f0;--muted:#64748b;--accent:#3b82f6;--accent2:#8b5cf6;--green:#10b981;--red:#ef4444;--grad:linear-gradient(135deg,#3b82f6,#8b5cf6)}
body{background:var(--bg);color:var(--text);font-family:'Inter',sans-serif;min-height:100vh}
.container{max-width:900px;margin:0 auto;padding:0 1.5rem}
.nav{background:var(--surface);border-bottom:1px solid var(--border);padding:1rem 0;position:sticky;top:0;z-index:100}
.nav-inner{display:flex;align-items:center;justify-content:space-between}
.logo{display:flex;align-items:center;gap:.6rem;font-size:1.3rem;font-weight:700}
.logo-icon{width:32px;height:32px;background:var(--grad);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:1rem;color:#fff}
.logo span{background:var(--grad);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.logo{transition:transform .2s ease}
.logo:hover{transform:scale(1.03)}
.logo-icon{transition:transform .25s ease,box-shadow .25s ease}
.logo:hover .logo-icon{transform:rotate(-8deg) scale(1.1);box-shadow:0 0 18px rgba(249,115,22,.45)}
.logo-icon svg{width:18px;height:18px}
.btn{background:var(--grad);color:#fff;border:none;border-radius:8px;padding:.55rem 1.2rem;font-size:.85rem;font-weight:600;cursor:pointer;transition:transform .15s}
.btn:hover{transform:translateY(-1px)}
.btn-ghost{background:var(--card);border:1px solid var(--border);color:var(--muted);border-radius:8px;padding:.55rem 1rem;font-size:.85rem;cursor:pointer}
.btn-ghost:hover{border-color:var(--accent);color:var(--text)}
.main{padding:2rem 0}

.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem;margin-bottom:2rem}
.stat{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1rem;text-align:center}
.stat-val{font-size:1.6rem;font-weight:700;background:var(--grad);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.stat-label{color:var(--muted);font-size:.7rem;text-transform:uppercase;margin-top:.2rem}

/* Habit card */
.habit{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1.2rem;margin-bottom:1rem;transition:border-color .2s}
.habit:hover{border-color:var(--accent)}
.habit-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:.75rem}
.habit-name{font-size:1.1rem;font-weight:600;display:flex;align-items:center;gap:.5rem}
.habit-name .emoji{font-size:1.4rem}
.habit-meta{display:flex;gap:1rem;color:var(--muted);font-size:.8rem}
.habit-meta span{display:flex;align-items:center;gap:.3rem}

/* Heatmap */
.heatmap{display:flex;gap:2px;flex-wrap:wrap;margin-top:.5rem}
.heatmap-cell{width:12px;height:12px;border-radius:2px;background:var(--surface);transition:transform .1s}
.heatmap-cell:hover{transform:scale(1.4)}
.heatmap-cell.done{background:var(--green)}
.heatmap-cell.done-2{background:#059669}
.heatmap-cell.done-3{background:#047857}
.heatmap-cell.today{outline:2px solid var(--accent)}

.habit-actions{display:flex;gap:.5rem;margin-top:.75rem;align-items:center}
.check-btn{width:40px;height:40px;border-radius:10px;border:2px solid var(--border);background:var(--surface);display:flex;align-items:center;justify-content:center;font-size:1.2rem;cursor:pointer;transition:all .2s}
.check-btn.checked{border-color:var(--green);background:rgba(16,185,129,.15)}
.check-btn:hover{transform:scale(1.05)}
.delete-btn{background:none;border:none;color:var(--muted);cursor:pointer;font-size:.8rem;margin-left:auto}
.delete-btn:hover{color:var(--red)}

/* Modal */
.modal-bg{position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:200;display:flex;align-items:center;justify-content:center;opacity:0;pointer-events:none;transition:opacity .2s}
.modal-bg.open{opacity:1;pointer-events:auto}
.modal{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:2rem;width:90%;max-width:420px}
.modal h2{font-size:1.1rem;margin-bottom:1rem}
.form-group{margin-bottom:1rem}
.form-group label{display:block;color:var(--muted);font-size:.8rem;margin-bottom:.35rem}
.form-group input{width:100%;background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:.6rem .8rem;color:var(--text);font-size:.9rem;outline:none}
.form-group input:focus{border-color:var(--accent)}
.modal-actions{display:flex;justify-content:flex-end;gap:.5rem;margin-top:1rem}

.empty{text-align:center;padding:3rem;color:var(--muted)}
.fade-in{animation:fadeIn .3s ease-out}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
</style>
</head>
<body>
<nav class="nav"><div class="container nav-inner">
  <div class="logo"><div class="logo-icon"><svg viewBox="0 0 24 24" width="18" height="18"><defs><linearGradient id="logo-flame-grad" x1="0" y1="1" x2="0.5" y2="0"><stop offset="0%" stop-color="#ef4444"/><stop offset="50%" stop-color="#f97316"/><stop offset="100%" stop-color="#facc15"/></linearGradient></defs><path d="M12 2C9 7 5 10 5 15c0 3.87 3.13 7 7 7s7-3.13 7-7c0-5-4-8-7-13zm0 18c-2.76 0-5-2.24-5-5 0-2 2-3.5 3.5-5.5.5-.7 1.5-.7 2 0 1.5 2 3.5 3.5 3.5 5.5 0 2.76-2.24 5-5 5z" fill="url(#logo-flame-grad)"/></svg></div><span>HabitGrid</span></div>
  <button class="btn" onclick="openModal()">+ New Habit</button>
</div></nav>
<div class="container main">
  <div class="stats fade-in" id="statsRow"></div>
  <div id="habitsEl"></div>
</div>
<div class="modal-bg" id="modalBg" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <h2>New Habit</h2>
    <div class="form-group"><label>Habit Name *</label><input id="fName" placeholder="e.g. Read 30 minutes"></div>
    <div class="form-group"><label>Emoji</label><input id="fEmoji" value="✅" maxlength="4"></div>
    <div class="form-group"><label>Color</label><input id="fColor" type="color" value="#10b981"></div>
    <div class="modal-actions">
      <button class="btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn" onclick="createHabit()">Create</button>
    </div>
  </div>
</div>
<script>
function api(u,o){return fetch(u,o).then(r=>r.json())}

function fmtDate(ts){if(!ts)return'';const d=new Date(ts*1000);return d.toLocaleDateString('en-US',{month:'short',day:'numeric'})}

function buildHeatmap(logs){
  const dateMap={};logs.forEach(l=>{dateMap[l.done_date]=(dateMap[l.done_date]||0)+1});
  let html='<div class="heatmap">';
  const today=new Date();
  for(let i=364;i>=0;i--){
    const d=new Date(today);d.setDate(d.getDate()-i);
    const ds=d.toISOString().split('T')[0];
    const cnt=dateMap[ds]||0;
    const isToday=ds===today.toISOString().split('T')[0];
    let cls='heatmap-cell';
    if(cnt>=3)cls+=' done done-3';
    else if(cnt>=2)cls+=' done done-2';
    else if(cnt>=1)cls+=' done';
    if(isToday)cls+=' today';
    html+=`<div class="${cls}" title="${ds}: ${cnt}"></div>`;
  }
  html+='</div>';
  return html;
}

async function load(){
  const habits=await api('/api/habits');
  const totalDone=habits.reduce((s,h)=>s+h.total_done,0);
  const bestStreak=habits.reduce((s,h)=>Math.max(s,h.streak),0);
  const todayDone=habits.filter(h=>h.logs.some(l=>l.done_date===new Date().toISOString().split('T')[0])).length;

  document.getElementById('statsRow').innerHTML=`
    <div class="stat"><div class="stat-val">${habits.length}</div><div class="stat-label">Habits</div></div>
    <div class="stat"><div class="stat-val">${todayDone}/${habits.length}</div><div class="stat-label">Today</div></div>
    <div class="stat"><div class="stat-val">${totalDone}</div><div class="stat-label">Total Check-ins</div></div>
    <div class="stat"><div class="stat-val">${bestStreak}${flameSVG()}</div><div class="stat-label">Best Streak</div></div>`;

  if(!habits.length){document.getElementById('habitsEl').innerHTML=`<div class="empty">${flameSVG()} No habits yet. Create one to start tracking!</div>`;return}

  document.getElementById('habitsEl').innerHTML=habits.map(h=>{
    const today=new Date().toISOString().split('T')[0];
    const doneToday=h.logs.some(l=>l.done_date===today);
    return`<div class="habit fade-in">
      <div class="habit-header">
        <div class="habit-name"><span class="emoji">${h.emoji}</span>${esc(h.name)}</div>
        <div class="habit-meta">
          <span>${flameSVG()} ${h.streak} day streak</span>
          <span>📊 ${h.total_done} total</span>
        </div>
      </div>
      ${buildHeatmap(h.logs)}
      <div class="habit-actions">
        <div class="check-btn ${doneToday?'checked':''}" onclick="toggleLog(${h.id})" title="Toggle today">${doneToday?'✓':'○'}</div>
        <button class="delete-btn" onclick="deleteHabit(${h.id})">Delete</button>
      </div>
    </div>`;
  }).join('');
}

function openModal(){document.getElementById('modalBg').classList.add('open');document.getElementById('fName').focus()}
function closeModal(){document.getElementById('modalBg').classList.remove('open')}

async function createHabit(){
  const name=document.getElementById('fName').value.trim();
  if(!name){alert('Name required');return}
  await api('/api/habits',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,emoji:document.getElementById('fEmoji').value,color:document.getElementById('fColor').value})});
  closeModal();load();
}

async function toggleLog(hid){await api(`/api/habits/${hid}/log`,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});load()}
async function deleteHabit(hid){if(!confirm('Delete habit?'))return;await api(`/api/habits/${hid}`,{method:'DELETE'});load()}
function esc(s){if(!s)return'';const e=document.createElement('span');e.textContent=s;return e.innerHTML}
let _fgid=0;
function flameSVG(cls){
  const id='fg'+(_fgid++);
  return `<svg viewBox="0 0 24 24" width="16" height="16" class="${cls||''}" style="vertical-align:middle"><defs><linearGradient id="${id}" x1="0" y1="1" x2="0.5" y2="0"><stop offset="0%" stop-color="#ef4444"/><stop offset="50%" stop-color="#f97316"/><stop offset="100%" stop-color="#facc15"/></linearGradient></defs><path d="M12 2C9 7 5 10 5 15c0 3.87 3.13 7 7 7s7-3.13 7-7c0-5-4-8-7-13zm0 18c-2.76 0-5-2.24-5-5 0-2 2-3.5 3.5-5.5.5-.7 1.5-.7 2 0 1.5 2 3.5 3.5 3.5 5.5 0 2.76-2.24 5-5 5z" fill="url(#${id})"/></svg>`;
}

load();
</script>
</body>
</html>"""

if __name__=="__main__":
    import uvicorn
    uvicorn.run(app,host="0.0.0.0",port=8013)
