import logging
from html import escape

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.api.router import api_router
from app.api.routes.chat import handle_bus_event
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.repository import ChatRepository
from app.db.session import AsyncSessionLocal, close_db, init_db
from app.services.runtime import event_bus

configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        await ChatRepository.ensure_today_issue(session)

    await event_bus.start(handle_bus_event)
    logger.info("FastAPI backend started")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await event_bus.stop()
    await close_db()
    logger.info("FastAPI backend shutdown complete")

@app.get("/web-chat", response_class=HTMLResponse)
@app.get("/v1/web-chat", response_class=HTMLResponse)
async def web_chat_page(request: Request, issueId: str):
    host = request.headers.get("x-forwarded-host") or request.url.netloc
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0]
    scheme = forwarded_proto.strip().lower() or request.url.scheme
    ws_scheme = "wss" if scheme == "https" else "ws"
    http_scheme = "https" if scheme == "https" else "http"
    api_base = f"{http_scheme}://{host}/v1"
    ws_url = f"{ws_scheme}://{host}/v1/chat/{issueId}"
    safe_issue_id = escape(issueId, quote=True)
    safe_ws_url = escape(ws_url, quote=True)
    safe_api_base = escape(api_base, quote=True)

    html = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no" />
  <title>OLaLA 실시간 채팅</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }

    :root {
      --primary: #4683F6;
      --primary-dark: #3567d6;
      --bg: #121212;
      --bg-card: #1e1e1e;
      --bg-input: #2a2a2a;
      --text: #f0f0f0;
      --text-secondary: #9ca3af;
      --text-muted: #6b7280;
      --border: #333333;
      --bubble-me: #4683F6;
      --bubble-other: #2a2a2a;
      --category-bg: rgba(70,131,246,0.15);
      --category-text: #6ba3ff;
      --gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      --shadow: 0 2px 8px rgba(0,0,0,0.3);
      --radius: 16px;
      --radius-sm: 8px;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      height: 100vh;
      height: 100dvh;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }

    /* ─── Header ─── */
    .header {
      background: var(--gradient);
      color: white;
      padding: 14px 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-shrink: 0;
      z-index: 10;
    }
    .header-left {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 17px;
      font-weight: 700;
    }
    .header-right {
      display: flex;
      align-items: center;
      gap: 6px;
      background: rgba(255,255,255,0.18);
      padding: 5px 12px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 600;
      backdrop-filter: blur(8px);
    }
    .online-dot {
      width: 8px; height: 8px;
      background: #10b981;
      border-radius: 50%;
      animation: pulse 2s infinite;
    }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }

    /* ─── Issue Card ─── */
    .issue-card {
      background: var(--bg-card);
      margin: 12px;
      padding: 14px 16px;
      border-radius: var(--radius);
      border: 1px solid var(--border);
      flex-shrink: 0;
      animation: slideDown .3s ease;
    }
    @keyframes slideDown { from{opacity:0;transform:translateY(-12px)} to{opacity:1;transform:translateY(0)} }

    .issue-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }
    .category-badge {
      background: var(--category-bg);
      color: var(--category-text);
      padding: 3px 10px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 700;
      border: 1px solid rgba(70,131,246,0.25);
    }
    .participant-info {
      font-size: 12px;
      color: var(--text-secondary);
      display: flex;
      align-items: center;
      gap: 4px;
    }
    .issue-title {
      font-size: 16px;
      font-weight: 700;
      line-height: 1.4;
      margin-bottom: 6px;
    }
    .issue-summary {
      font-size: 13px;
      color: var(--text-secondary);
      line-height: 1.5;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .issue-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 10px;
      padding-top: 8px;
      border-top: 1px solid var(--border);
    }
    .issue-time {
      font-size: 11px;
      color: var(--text-muted);
    }
    .issue-link {
      font-size: 12px;
      color: var(--primary);
      text-decoration: none;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 2px;
    }

    /* ─── Messages ─── */
    .messages-area {
      flex: 1;
      overflow-y: auto;
      padding: 12px 16px;
      display: flex;
      flex-direction: column;
      gap: 6px;
      scroll-behavior: smooth;
    }
    .messages-area::-webkit-scrollbar { width: 4px; }
    .messages-area::-webkit-scrollbar-thumb { background: #444; border-radius: 2px; }

    .msg-row {
      display: flex;
      flex-direction: column;
      animation: fadeIn .25s ease;
      max-width: 80%;
    }
    @keyframes fadeIn { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:translateY(0)} }

    .msg-row.me { align-self: flex-end; align-items: flex-end; }
    .msg-row.other { align-self: flex-start; align-items: flex-start; }
    .msg-row.system { align-self: center; max-width: 100%; align-items: center; }

    .msg-author {
      font-size: 12px;
      font-weight: 600;
      color: var(--text-secondary);
      padding: 0 4px;
      margin-bottom: 2px;
    }

    .msg-bubble-wrap {
      display: flex;
      align-items: flex-end;
      gap: 6px;
    }
    .msg-row.me .msg-bubble-wrap { flex-direction: row-reverse; }

    .msg-bubble {
      padding: 10px 14px;
      border-radius: var(--radius);
      line-height: 1.5;
      font-size: 15px;
      word-break: break-word;
      max-width: 100%;
    }
    .msg-row.other .msg-bubble {
      background: var(--bubble-other);
      color: var(--text);
      border-bottom-left-radius: 4px;
    }
    .msg-row.me .msg-bubble {
      background: var(--bubble-me);
      color: white;
      border-bottom-right-radius: 4px;
    }
    .msg-row.system .msg-bubble {
      background: transparent;
      color: var(--text-muted);
      font-size: 12px;
      padding: 4px 0;
    }

    .msg-time {
      font-size: 10px;
      color: var(--text-muted);
      white-space: nowrap;
      flex-shrink: 0;
    }

    .msg-reaction {
      display: flex;
      align-items: center;
      gap: 2px;
      margin-top: 2px;
    }
    .msg-reaction button {
      background: none;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 2px 8px;
      font-size: 13px;
      cursor: pointer;
      color: var(--text-secondary);
      display: flex;
      align-items: center;
      gap: 3px;
      transition: all .15s;
    }
    .msg-reaction button:hover { border-color: #e74c3c; color: #e74c3c; }
    .msg-reaction button.active { border-color: #e74c3c; color: #e74c3c; background: rgba(231,76,60,.1); }

    .empty-state {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: var(--text-muted);
      gap: 8px;
      padding: 40px;
    }
    .empty-state-icon { font-size: 40px; opacity: .4; }
    .empty-state-text { font-size: 14px; text-align: center; line-height: 1.6; }

    /* ─── Chat Input ─── */
    .chat-input {
      background: var(--bg-card);
      padding: 10px 12px;
      padding-bottom: calc(10px + env(safe-area-inset-bottom, 0));
      border-top: 1px solid var(--border);
      display: flex;
      gap: 8px;
      align-items: flex-end;
      flex-shrink: 0;
    }
    .chat-input input {
      flex: 1;
      padding: 12px 16px;
      background: var(--bg-input);
      border: 1px solid var(--border);
      border-radius: 24px;
      color: var(--text);
      font-size: 15px;
      outline: none;
      transition: border-color .2s;
      font-family: inherit;
    }
    .chat-input input::placeholder { color: var(--text-muted); }
    .chat-input input:focus { border-color: var(--primary); }
    .chat-input .send-btn {
      width: 44px;
      height: 44px;
      border-radius: 50%;
      border: none;
      background: var(--primary);
      color: white;
      font-size: 18px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      transition: all .15s;
      padding: 0;
    }
    .chat-input .send-btn:hover { background: var(--primary-dark); transform: scale(1.05); }
    .chat-input .send-btn:disabled { background: #444; cursor: not-allowed; transform: none; }

    /* ─── Nickname Modal ─── */
    .modal-overlay {
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,.6);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 100;
      backdrop-filter: blur(4px);
    }
    .modal-card {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 28px 24px;
      width: 90%;
      max-width: 360px;
      animation: slideDown .3s ease;
    }
    .modal-title {
      font-size: 18px;
      font-weight: 700;
      margin-bottom: 6px;
      text-align: center;
    }
    .modal-desc {
      font-size: 13px;
      color: var(--text-secondary);
      text-align: center;
      margin-bottom: 20px;
    }
    .modal-input {
      width: 100%;
      padding: 12px 16px;
      background: var(--bg-input);
      border: 1.5px solid var(--border);
      border-radius: var(--radius-sm);
      color: var(--text);
      font-size: 15px;
      outline: none;
      margin-bottom: 16px;
    }
    .modal-input:focus { border-color: var(--primary); }
    .modal-btn {
      width: 100%;
      padding: 14px;
      border: none;
      border-radius: var(--radius-sm);
      background: var(--primary);
      color: white;
      font-size: 16px;
      font-weight: 700;
      cursor: pointer;
      transition: background .2s;
    }
    .modal-btn:hover { background: var(--primary-dark); }

    @media (max-width: 480px) {
      .issue-card { margin: 8px; padding: 12px; }
      .msg-row { max-width: 85%; }
    }
  </style>
</head>
<body>
  <!-- Header -->
  <div class="header">
    <div class="header-left">
      <span>💬</span><span>오늘의 이슈</span>
    </div>
    <div class="header-right">
      <span class="online-dot"></span>
      <span id="onlineCount">0</span> 명 접속중
    </div>
  </div>

  <!-- Issue Card -->
  <div class="issue-card" id="issueCard" style="display:none;">
    <div class="issue-top">
      <span class="category-badge" id="issueCat"></span>
      <span class="participant-info">👥 <span id="issuePart">0</span>명 참여 중</span>
    </div>
    <div class="issue-title" id="issueTitle"></div>
    <div class="issue-summary" id="issueSummary"></div>
    <div class="issue-footer">
      <span class="issue-time" id="issueTime"></span>
    </div>
  </div>

  <!-- Messages -->
  <div class="messages-area" id="messages">
    <div class="empty-state" id="emptyState">
      <div class="empty-state-icon">💭</div>
      <div class="empty-state-text">아직 메시지가 없습니다<br>첫 메시지를 보내보세요!</div>
    </div>
  </div>

  <!-- Chat Input -->
  <div class="chat-input" id="chatInput" style="display:none;">
    <input id="msgInput" type="text" placeholder="메시지를 입력하세요..." autocomplete="off" />
    <button class="send-btn" id="sendBtn" disabled>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
    </button>
  </div>

  <!-- Nickname Modal -->
  <div class="modal-overlay" id="modal">
    <div class="modal-card">
      <div class="modal-title">채팅 참여</div>
      <div class="modal-desc">닉네임을 입력하고 채팅에 참여하세요</div>
      <input class="modal-input" id="nicknameInput" type="text" maxlength="20" placeholder="닉네임 (최대 20자)" autocomplete="off" />
      <button class="modal-btn" id="joinBtn">입장하기</button>
    </div>
  </div>

  <script>
    const issueId = "__ISSUE_ID__";
    const wsUrl = "__WS_URL__";
    const apiBase = "__API_BASE__";
    const userId = "web_" + Math.random().toString(36).slice(2, 10);
    let nickname = "관객-" + Math.floor(Math.random() * 1000);
    let ws = null;

    const $ = id => document.getElementById(id);
    const messagesEl = $("messages");
    const emptyStateEl = $("emptyState");
    const modalEl = $("modal");
    const nicknameInputEl = $("nicknameInput");
    const joinBtnEl = $("joinBtn");
    const chatInputEl = $("chatInput");
    const msgInputEl = $("msgInput");
    const sendBtnEl = $("sendBtn");
    const onlineCountEl = $("onlineCount");

    nicknameInputEl.value = nickname;

    /* ─── Load issue info ─── */
    (async () => {
      try {
        const res = await fetch(apiBase + "/issues/today");
        if (!res.ok) return;
        const issue = await res.json();
        $("issueCat").textContent = issue.category || "기타";
        $("issueTitle").textContent = issue.title || "";
        $("issueSummary").textContent = issue.summary || "";
        $("issuePart").textContent = String(issue.participantCount || 0);
        const pub = new Date(issue.publishedAt);
        const diff = Math.floor((Date.now() - pub.getTime()) / 60000);
        $("issueTime").textContent = diff < 60
          ? diff + "분 전 발행"
          : Math.floor(diff / 60) + "시간 전 발행";
        $("issueCard").style.display = "block";
      } catch (e) { console.warn("이슈 로드 실패", e); }
    })();

    /* ─── Load chat history ─── */
    async function loadHistory() {
      try {
        const res = await fetch(apiBase + "/chat/messages/" + issueId + "?limit=50");
        if (!res.ok) return;
        const data = await res.json();
        const msgs = data.messages || data;
        if (!Array.isArray(msgs) || msgs.length === 0) return;
        msgs.forEach(m => {
          const isMe = m.userId === userId || m.user_id === userId;
          addMessage(m.content, m.username || m.nickname || "익명", isMe, false, m.id);
        });
      } catch (e) { console.warn("히스토리 로드 실패", e); }
    }

    /* ─── Time format ─── */
    function formatTime(d) {
      return d.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });
    }

    /* ─── Add message ─── */
    function addMessage(content, author, isMe, isSystem, msgId) {
      if (emptyStateEl) emptyStateEl.remove();

      const row = document.createElement("div");
      row.className = "msg-row " + (isSystem ? "system" : isMe ? "me" : "other");

      if (!isSystem && !isMe) {
        const authorEl = document.createElement("div");
        authorEl.className = "msg-author";
        authorEl.textContent = author;
        row.appendChild(authorEl);
      }

      const wrap = document.createElement("div");
      wrap.className = "msg-bubble-wrap";

      const bubble = document.createElement("div");
      bubble.className = "msg-bubble";
      bubble.textContent = content;
      wrap.appendChild(bubble);

      if (!isSystem) {
        const timeEl = document.createElement("div");
        timeEl.className = "msg-time";
        timeEl.textContent = formatTime(new Date());
        wrap.appendChild(timeEl);
      }

      row.appendChild(wrap);

      /* Reaction button */
      if (!isSystem && msgId) {
        const reactDiv = document.createElement("div");
        reactDiv.className = "msg-reaction";
        const btn = document.createElement("button");
        btn.innerHTML = "♡ <span>0</span>";
        btn.onclick = () => {
          btn.classList.toggle("active");
          const span = btn.querySelector("span");
          const n = parseInt(span.textContent || "0");
          span.textContent = btn.classList.contains("active") ? n + 1 : Math.max(0, n - 1);
          btn.innerHTML = (btn.classList.contains("active") ? "♥ " : "♡ ") + "<span>" + span.textContent + "</span>";
        };
        reactDiv.appendChild(btn);
        row.appendChild(reactDiv);
      }

      messagesEl.appendChild(row);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function addSystem(text) { addMessage(text, null, false, true, null); }

    /* ─── WebSocket ─── */
    function connect() {
      const raw = nicknameInputEl.value.trim();
      if (!raw) { nicknameInputEl.focus(); return; }
      nickname = raw.slice(0, 20);
      modalEl.style.display = "none";
      chatInputEl.style.display = "flex";

      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        ws.send(JSON.stringify({
          type: "join", issueId, userId, nickname,
          sentAt: new Date().toISOString()
        }));
        addSystem(nickname + "님이 입장하셨습니다");
        msgInputEl.disabled = false;
        msgInputEl.focus();
        loadHistory();
      };

      ws.onmessage = e => {
        try {
          const d = JSON.parse(e.data);
          if (d.type === "presence") {
            onlineCountEl.textContent = String(d.onlineCount || 0);
            return;
          }
          if (d.type === "message.created" && d.message) {
            const m = d.message;
            if (m.userId === userId) return; // skip own echo
            addMessage(m.content, m.username || "익명", false, false, m.id);
            return;
          }
          if (d.type === "error") {
            addSystem("⚠️ " + (d.message || "오류"));
          }
        } catch (err) { console.error(err); }
      };

      ws.onerror = () => { addSystem("⚠️ 연결 오류가 발생했습니다"); };
      ws.onclose = () => { addSystem("연결이 종료되었습니다. 새로고침 해주세요."); msgInputEl.disabled = true; };
    }

    /* ─── Send ─── */
    function send() {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      const text = msgInputEl.value.trim();
      if (!text) return;

      addMessage(text, nickname, true, false, "local_" + Date.now());

      ws.send(JSON.stringify({
        type: "message.create", issueId,
        clientId: "web_" + Date.now(),
        userId, nickname,
        content: text,
        sentAt: new Date().toISOString()
      }));

      msgInputEl.value = "";
      sendBtnEl.disabled = true;
      msgInputEl.focus();
    }

    joinBtnEl.onclick = connect;
    sendBtnEl.onclick = send;
    nicknameInputEl.addEventListener("keydown", e => { if (e.key === "Enter") connect(); });
    msgInputEl.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } });
    msgInputEl.addEventListener("input", () => { sendBtnEl.disabled = !msgInputEl.value.trim(); });
  </script>
</body>
</html>"""

    html = (
        html.replace("__ISSUE_ID__", safe_issue_id)
            .replace("__WS_URL__", safe_ws_url)
            .replace("__API_BASE__", safe_api_base)
    )
    return HTMLResponse(content=html)

