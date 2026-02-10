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
    # Fetch issue data
    async with AsyncSessionLocal() as session:
        issue = await ChatRepository.ensure_issue(session, issueId)

    issue_title = escape(issue.title if issue else "오늘의 이슈", quote=False)
    issue_summary = escape(issue.summary if issue else "", quote=False)
    issue_content = escape(issue.content if issue else "", quote=False)
    issue_category = escape(issue.category if issue else "정치", quote=False)

    host = request.headers.get("x-forwarded-host") or request.url.netloc
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0]
    scheme = forwarded_proto.strip().lower() or request.url.scheme
    ws_scheme = "wss" if scheme == "https" else "ws"
    ws_url = f"{ws_scheme}://{host}/v1/chat/{issueId}"
    safe_issue_id = escape(issueId, quote=True)
    safe_ws_url = escape(ws_url, quote=True)

    html = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no" />
  <title>OLaLA 실시간 채팅</title>
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }

    :root {
      --primary: #4683F6;
      --primary-dark: #3567d6;
      --secondary: #f0f4ff;
      --success: #10b981;
      --text: #1f2937;
      --text-light: #6b7280;
      --text-lighter: #9ca3af;
      --bg: #f9fafb;
      --bg-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      --card: #ffffff;
      --border: #e5e7eb;
      --shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
      --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05);
      --bubble-me: #4683F6;
      --bubble-other: #f3f4f6;
      --radius: 16px;
      --radius-sm: 8px;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
      background: var(--bg);
      color: var(--text);
      height: 100vh;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }

    .header {
      background: var(--bg-gradient);
      color: white;
      padding: 16px 20px;
      box-shadow: var(--shadow-lg);
      z-index: 10;
    }

    .header-content {
      max-width: 900px;
      margin: 0 auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
    }

    .header h1 {
      font-size: 20px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .logo {
      font-size: 24px;
    }

    .online-badge {
      display: flex;
      align-items: center;
      gap: 6px;
      background: rgba(255,255,255,0.2);
      padding: 6px 12px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 600;
      backdrop-filter: blur(10px);
    }

    .online-dot {
      width: 8px;
      height: 8px;
      background: var(--success);
      border-radius: 50%;
      animation: pulse 2s infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }

    .container {
      flex: 1;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      max-width: 900px;
      width: 100%;
      margin: 0 auto;
      padding: 0;
    }

    .article-section {
      background: var(--card);
      margin: 16px 16px 8px 16px;
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: hidden;
      animation: slideDown 0.3s ease;
    }

    .article-header {
      padding: 16px 20px;
      cursor: pointer;
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
      border-bottom: 1px solid var(--border);
    }

    .article-header:hover {
      background: linear-gradient(135deg, #667eea25 0%, #764ba225 100%);
    }

    .article-title-area {
      flex: 1;
      min-width: 0;
    }

    .article-category {
      display: inline-block;
      background: var(--primary);
      color: white;
      font-size: 11px;
      font-weight: 700;
      padding: 4px 10px;
      border-radius: 12px;
      margin-bottom: 8px;
    }

    .article-title {
      font-size: 16px;
      font-weight: 700;
      color: var(--text);
      line-height: 1.4;
      margin-bottom: 6px;
    }

    .article-summary {
      font-size: 13px;
      color: var(--text-light);
      line-height: 1.5;
    }

    .article-toggle {
      flex-shrink: 0;
      margin-left: 12px;
      font-size: 20px;
      color: var(--primary);
      transition: transform 0.3s;
    }

    .article-toggle.expanded {
      transform: rotate(180deg);
    }

    .article-content {
      max-height: 0;
      overflow: hidden;
      transition: max-height 0.3s ease;
      background: white;
    }

    .article-content.expanded {
      max-height: 400px;
      overflow-y: auto;
    }

    .article-body {
      padding: 20px;
      font-size: 14px;
      line-height: 1.8;
      color: var(--text);
      white-space: pre-wrap;
      word-wrap: break-word;
    }

    .join-section {
      background: var(--card);
      margin: 16px;
      padding: 20px;
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      animation: slideDown 0.3s ease;
    }

    @keyframes slideDown {
      from {
        opacity: 0;
        transform: translateY(-20px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .status {
      color: var(--text-light);
      font-size: 14px;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .status::before {
      content: "💬";
      font-size: 18px;
    }

    .join-form {
      display: flex;
      gap: 10px;
    }

    input {
      flex: 1;
      padding: 14px 16px;
      border: 2px solid var(--border);
      border-radius: var(--radius-sm);
      font-size: 15px;
      transition: all 0.2s;
      outline: none;
      background: var(--bg);
    }

    input:focus {
      border-color: var(--primary);
      background: white;
      box-shadow: 0 0 0 3px rgba(70, 131, 246, 0.1);
    }

    input:disabled {
      background: var(--border);
      cursor: not-allowed;
      opacity: 0.6;
    }

    button {
      padding: 14px 24px;
      border: none;
      border-radius: var(--radius-sm);
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
      white-space: nowrap;
      outline: none;
    }

    button.primary {
      background: var(--primary);
      color: white;
      box-shadow: 0 2px 4px rgba(70, 131, 246, 0.3);
    }

    button.primary:hover:not(:disabled) {
      background: var(--primary-dark);
      transform: translateY(-1px);
      box-shadow: 0 4px 8px rgba(70, 131, 246, 0.4);
    }

    button.primary:active:not(:disabled) {
      transform: translateY(0);
    }

    button:disabled {
      background: var(--text-lighter);
      cursor: not-allowed;
      box-shadow: none;
    }

    .hint {
      margin-top: 10px;
      font-size: 13px;
      color: var(--text-lighter);
      text-align: center;
    }

    .messages-container {
      flex: 1;
      overflow-y: auto;
      padding: 20px 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      scroll-behavior: smooth;
    }

    .messages-container::-webkit-scrollbar {
      width: 6px;
    }

    .messages-container::-webkit-scrollbar-track {
      background: transparent;
    }

    .messages-container::-webkit-scrollbar-thumb {
      background: var(--border);
      border-radius: 3px;
    }

    .messages-container::-webkit-scrollbar-thumb:hover {
      background: var(--text-lighter);
    }

    .message {
      display: flex;
      gap: 8px;
      align-items: flex-end;
      animation: fadeIn 0.3s ease;
      max-width: 85%;
    }

    @keyframes fadeIn {
      from {
        opacity: 0;
        transform: translateY(10px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .message.me {
      align-self: flex-end;
      flex-direction: row-reverse;
    }

    .message.system {
      align-self: center;
      max-width: 100%;
    }

    .message-content {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .message.me .message-content {
      align-items: flex-end;
    }

    .message-author {
      font-size: 12px;
      font-weight: 600;
      color: var(--text-light);
      padding: 0 8px;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .admin-badge {
      display: inline-block;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      font-size: 10px;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 6px;
      text-transform: uppercase;
    }

    .message-bubble {
      padding: 12px 16px;
      border-radius: var(--radius);
      word-wrap: break-word;
      max-width: 100%;
      position: relative;
      line-height: 1.5;
    }

    .message:not(.me) .message-bubble {
      background: var(--bubble-other);
      color: var(--text);
      border-bottom-left-radius: 4px;
    }

    .message.me .message-bubble {
      background: var(--bubble-me);
      color: white;
      border-bottom-right-radius: 4px;
    }

    .message.system .message-bubble {
      background: transparent;
      color: var(--text-lighter);
      font-size: 13px;
      text-align: center;
      padding: 6px 12px;
    }

    .message-time {
      font-size: 11px;
      color: var(--text-lighter);
      padding: 0 4px;
      white-space: nowrap;
    }

    .message-reaction {
      display: flex;
      align-items: center;
      gap: 4px;
      margin-top: 6px;
    }

    .reaction-button {
      background: transparent;
      border: 1px solid #E6E9EF;
      padding: 4px 8px;
      cursor: pointer;
      border-radius: 12px;
      transition: all 180ms ease-out;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      user-select: none;
      font-family: inherit;
    }

    .reaction-button:hover {
      background: rgba(229, 72, 77, 0.08);
      border-color: rgba(229, 72, 77, 0.2);
    }

    .reaction-button.reacted {
      background: rgba(229, 72, 77, 0.12);
      border-color: rgba(229, 72, 77, 0.2);
    }

    .reaction-icon {
      font-size: 16px;
      line-height: 1;
      color: #9AA1AD;
    }

    .reaction-button.reacted .reaction-icon {
      color: #E5484D;
    }

    .reaction-count {
      font-size: 12px;
      font-weight: 600;
      color: #9AA1AD;
      line-height: 1;
    }

    .reaction-button.reacted .reaction-count {
      color: #E5484D;
    }

    .input-container {
      background: var(--card);
      padding: 16px;
      border-top: 1px solid var(--border);
      box-shadow: 0 -2px 10px rgba(0,0,0,0.05);
    }

    .input-container-inner {
      max-width: 900px;
      margin: 0 auto;
      display: flex;
      gap: 10px;
      align-items: flex-end;
    }

    .input-wrapper {
      flex: 1;
      position: relative;
    }

    #msg {
      width: 100%;
      padding: 14px 16px;
      border: 2px solid var(--border);
      border-radius: 24px;
      font-size: 15px;
      resize: none;
      max-height: 120px;
      font-family: inherit;
    }

    #send {
      border-radius: 50%;
      width: 48px;
      height: 48px;
      padding: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      flex-shrink: 0;
    }

    .empty-state {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: var(--text-lighter);
      gap: 12px;
      padding: 40px 20px;
    }

    .empty-state-icon {
      font-size: 48px;
      opacity: 0.5;
    }

    .empty-state-text {
      font-size: 15px;
      text-align: center;
    }

    @media (max-width: 600px) {
      .header h1 {
        font-size: 18px;
      }

      .message {
        max-width: 90%;
      }

      .join-form {
        flex-direction: column;
      }

      button {
        width: 100%;
      }
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="header-content">
      <h1>
        <span class="logo">💬</span>
        <span>오늘의 이슈</span>
      </h1>
      <div class="online-badge">
        <span class="online-dot"></span>
        <span id="onlineCount">0</span>명 접속중
      </div>
    </div>
  </div>

  <div class="container">
    <!-- 기사 섹션 -->
    <div class="article-section">
      <div class="article-header" onclick="toggleArticle()">
        <div class="article-title-area">
          <div class="article-category">__ISSUE_CATEGORY__</div>
          <div class="article-title">__ISSUE_TITLE__</div>
          <div class="article-summary">__ISSUE_SUMMARY__</div>
        </div>
        <div class="article-toggle" id="articleToggle">📰</div>
      </div>
      <div class="article-content" id="articleContent">
        <div class="article-body">__ISSUE_CONTENT__</div>
      </div>
    </div>

    <div id="joinSection" class="join-section">
      <div class="status" id="status">
        닉네임을 입력하고 입장하세요
      </div>
      <div class="join-form">
        <input
          id="nickname"
          type="text"
          maxlength="20"
          placeholder="닉네임 (최대 20자)"
          autocomplete="off"
        />
        <button id="joinBtn" class="primary">입장하기</button>
      </div>
      <div class="hint">
        앱 사용자와 실시간으로 대화할 수 있습니다
      </div>
    </div>

    <div class="messages-container" id="messages">
      <div class="empty-state">
        <div class="empty-state-icon">💭</div>
        <div class="empty-state-text">
          아직 메시지가 없습니다<br>
          첫 메시지를 보내보세요!
        </div>
      </div>
    </div>

    <div class="input-container" style="display: none;" id="inputContainer">
      <div class="input-container-inner">
        <div class="input-wrapper">
          <input
            id="msg"
            type="text"
            placeholder="메시지를 입력하세요..."
            disabled
            autocomplete="off"
          />
        </div>
        <button id="send" class="primary" disabled>📤</button>
      </div>
    </div>
  </div>

  <script>
    const issueId = "__ISSUE_ID__";
    const wsUrl = "__WS_URL__";
    const userId = "web_" + Math.random().toString(36).slice(2, 10);
    let nickname = "관객-" + Math.floor(Math.random() * 1000);
    let ws = null;
    let isJoined = false;
    const messageMap = new Map(); // messageId -> message element

    const messagesEl = document.getElementById("messages");
    const onlineCountEl = document.getElementById("onlineCount");
    const statusEl = document.getElementById("status");
    const joinSectionEl = document.getElementById("joinSection");
    const nicknameEl = document.getElementById("nickname");
    const joinBtnEl = document.getElementById("joinBtn");
    const inputContainerEl = document.getElementById("inputContainer");
    const msgEl = document.getElementById("msg");
    const sendBtnEl = document.getElementById("send");

    nicknameEl.value = nickname;

    function formatTime(date) {
      return date.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
    }

    function clearEmptyState() {
      const emptyState = messagesEl.querySelector('.empty-state');
      if (emptyState) {
        emptyState.remove();
      }
    }

    function addMessage(content, author = null, isMe = false, isSystem = false, messageId = null, reactionCount = 0, isReacted = false, authorUserId = null) {
      clearEmptyState();

      const msgDiv = document.createElement("div");
      msgDiv.className = "message" + (isMe ? " me" : "") + (isSystem ? " system" : "");
      if (messageId) {
        msgDiv.dataset.messageId = messageId;
        messageMap.set(messageId, msgDiv);
      }

      const contentDiv = document.createElement("div");
      contentDiv.className = "message-content";

      if (author && !isSystem) {
        const authorDiv = document.createElement("div");
        authorDiv.className = "message-author";

        // Add author name
        const nameSpan = document.createElement("span");
        nameSpan.textContent = author;
        authorDiv.appendChild(nameSpan);

        // Add admin badge if not a web user
        const isAdmin = authorUserId && !authorUserId.startsWith("web_");
        if (isAdmin) {
          const badge = document.createElement("span");
          badge.className = "admin-badge";
          badge.textContent = "관리자";
          authorDiv.appendChild(badge);
        }

        contentDiv.appendChild(authorDiv);
      }

      const bubbleDiv = document.createElement("div");
      bubbleDiv.className = "message-bubble";
      bubbleDiv.textContent = content;
      contentDiv.appendChild(bubbleDiv);

      // Add reaction button (only for non-system messages)
      if (!isSystem && messageId) {
        const reactionDiv = document.createElement("div");
        reactionDiv.className = "message-reaction";

        const reactionBtn = document.createElement("button");
        reactionBtn.className = "reaction-button" + (isReacted ? " reacted" : "");
        reactionBtn.onclick = () => toggleReaction(messageId);

        const iconSpan = document.createElement("span");
        iconSpan.className = "reaction-icon";
        iconSpan.textContent = isReacted ? "❤" : "♡";
        reactionBtn.appendChild(iconSpan);

        if (reactionCount > 0) {
          const countSpan = document.createElement("span");
          countSpan.className = "reaction-count";
          countSpan.textContent = reactionCount;
          reactionBtn.appendChild(countSpan);
        }

        reactionDiv.appendChild(reactionBtn);
        contentDiv.appendChild(reactionDiv);
      }

      msgDiv.appendChild(contentDiv);

      if (!isSystem) {
        const timeDiv = document.createElement("div");
        timeDiv.className = "message-time";
        timeDiv.textContent = formatTime(new Date());
        msgDiv.appendChild(timeDiv);
      }

      messagesEl.appendChild(msgDiv);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function addSystemMessage(text) {
      addMessage(text, null, false, true);
    }

    function setJoinedState(joined) {
      isJoined = joined;
      msgEl.disabled = !joined;
      sendBtnEl.disabled = !joined;

      if (joined) {
        joinSectionEl.style.display = "none";
        inputContainerEl.style.display = "block";
        msgEl.focus();
      } else {
        joinSectionEl.style.display = "block";
        inputContainerEl.style.display = "none";
        nicknameEl.disabled = false;
        joinBtnEl.disabled = false;
      }
    }

    function connect() {
      const rawNickname = nicknameEl.value.trim();
      if (!rawNickname) {
        statusEl.textContent = "⚠️ 닉네임을 입력해주세요";
        nicknameEl.focus();
        return;
      }

      nickname = rawNickname.slice(0, 20);
      statusEl.textContent = "🔄 연결 중...";
      joinBtnEl.disabled = true;
      nicknameEl.disabled = true;

      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        ws.send(JSON.stringify({
          type: "join",
          issueId: issueId,
          userId: userId,
          nickname: nickname,
          sentAt: new Date().toISOString()
        }));
        setJoinedState(true);
        addSystemMessage(nickname + "님이 입장하셨습니다");
      };

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);

          if (data.type === "presence") {
            const count = Number(data.onlineCount || 0);
            onlineCountEl.textContent = String(count);
            return;
          }

          if (data.type === "message.created" && data.message) {
            const msg = data.message;
            const isMyMessage = msg.userId === userId;
            const author = msg.username || "익명";

            addMessage(
              msg.content,
              author,
              isMyMessage,
              false,
              msg.id,
              msg.reactionCount || 0,
              msg.isReactedByMe || false,
              msg.userId
            );
            return;
          }

          if (data.type === "reaction.updated") {
            updateReaction(data.messageId, data.count, data.isReactedByMe);
            return;
          }

          if (data.type === "error") {
            addSystemMessage("⚠️ " + (data.message || "오류가 발생했습니다"));
            return;
          }
        } catch (err) {
          console.error("메시지 파싱 실패:", err);
        }
      };

      ws.onerror = () => {
        statusEl.textContent = "❌ 연결 오류가 발생했습니다";
        if (!isJoined) {
          joinBtnEl.disabled = false;
          nicknameEl.disabled = false;
        } else {
          addSystemMessage("연결이 끊어졌습니다");
        }
      };

      ws.onclose = () => {
        if (isJoined) {
          addSystemMessage("연결이 종료되었습니다");
        }
        setJoinedState(false);
      };
    }

    function sendMessage() {
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        addSystemMessage("연결이 끊어졌습니다. 다시 입장해주세요.");
        setJoinedState(false);
        return;
      }

      const content = msgEl.value.trim();
      if (!content) return;

      ws.send(JSON.stringify({
        type: "message.create",
        issueId: issueId,
        clientId: "web_" + Date.now(),
        userId: userId,
        nickname: nickname,
        content: content,
        sentAt: new Date().toISOString()
      }));

      msgEl.value = "";
      msgEl.focus();
    }

    function toggleArticle() {
      const contentEl = document.getElementById("articleContent");
      const toggleEl = document.getElementById("articleToggle");
      const isExpanded = contentEl.classList.contains("expanded");

      if (isExpanded) {
        contentEl.classList.remove("expanded");
        toggleEl.classList.remove("expanded");
        toggleEl.textContent = "📰";
      } else {
        contentEl.classList.add("expanded");
        toggleEl.classList.add("expanded");
        toggleEl.textContent = "🔼";
      }
    }

    function toggleReaction(messageId) {
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        addSystemMessage("연결이 끊어졌습니다.");
        return;
      }

      ws.send(JSON.stringify({
        type: "reaction.toggle",
        messageId: messageId,
        userId: userId,
        sentAt: new Date().toISOString()
      }));
    }

    function updateReaction(messageId, count, isReacted) {
      const msgDiv = messageMap.get(messageId);
      if (!msgDiv) return;

      const reactionBtn = msgDiv.querySelector(".reaction-button");
      if (!reactionBtn) return;

      // Update button class
      if (isReacted) {
        reactionBtn.classList.add("reacted");
      } else {
        reactionBtn.classList.remove("reacted");
      }

      // Update icon and count
      reactionBtn.innerHTML = "";

      const iconSpan = document.createElement("span");
      iconSpan.className = "reaction-icon";
      iconSpan.textContent = isReacted ? "❤" : "♡";
      reactionBtn.appendChild(iconSpan);

      if (count > 0) {
        const countSpan = document.createElement("span");
        countSpan.className = "reaction-count";
        countSpan.textContent = count;
        reactionBtn.appendChild(countSpan);
      }
    }

    joinBtnEl.onclick = connect;
    sendBtnEl.onclick = sendMessage;

    nicknameEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !joinBtnEl.disabled) {
        connect();
      }
    });

    msgEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    msgEl.addEventListener("input", () => {
      sendBtnEl.disabled = !msgEl.value.trim();
    });
  </script>
</body>
</html>"""

    html = (
        html.replace("__ISSUE_ID__", safe_issue_id)
            .replace("__WS_URL__", safe_ws_url)
            .replace("__ISSUE_TITLE__", issue_title)
            .replace("__ISSUE_SUMMARY__", issue_summary)
            .replace("__ISSUE_CONTENT__", issue_content)
            .replace("__ISSUE_CATEGORY__", issue_category)
    )
    return HTMLResponse(content=html)
