import logging
from html import escape
from urllib.parse import quote

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
    route_prefix = "/v1" if request.url.path.startswith("/v1/") else ""
    verify_home_url = f"{scheme}://{host}{route_prefix}/home-input"
    safe_issue_id = escape(issueId, quote=True)
    safe_ws_url = escape(ws_url, quote=True)
    safe_verify_home_url = escape(verify_home_url, quote=True)

    html = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no" />
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'self'; connect-src 'self' ws: wss:; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'">
  <title>OLaLA 실시간 채팅</title>
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }

    :root {
      /* OLaLA Design Tokens */
      --primary: #4683F6;
      --primary-600: #3567d6;
      --primary-050: #E9F3FF;

      --bg: #F6F8FC;
      --card: #ffffff;

      --text: #111827;
      --muted: #6b7280;
      --muted2: #9ca3af;

      --border: #E6E9EF;

      --shadow: 0 6px 16px rgba(17,24,39,.08);
      --shadow-lg: 0 12px 28px rgba(17,24,39,.14);

      --bubble-me: var(--primary);
      --bubble-other: #F3F6FB;

      --radius: 16px;
      --radius-sm: 12px;

      --focus: 0 0 0 4px rgba(70,131,246,.18);

      --header-gradient: linear-gradient(135deg,#4683F6 0%, #5A9CFF 55%, #7C5CFF 100%);
      --success: #10b981;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
      background: var(--bg);
      color: var(--text);
      height: 100dvh;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }

    .header {
      background: var(--header-gradient);
      color: white;
      padding: 14px 16px calc(14px + env(safe-area-inset-top));
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
      min-width: 0;
    }

    .header h1 {
      font-size: 18px;
      font-weight: 800;
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
    }

    .logo { font-size: 22px; }

    #headerTitle {
      display: inline-block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 52vw;
    }

    .online-badge {
      display: flex;
      align-items: center;
      gap: 8px;
      background: rgba(255,255,255,0.18);
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      backdrop-filter: blur(10px);
      white-space: nowrap;
    }

    .online-dot {
      width: 8px;
      height: 8px;
      background: var(--success);
      border-radius: 50%;
      animation: pulse 2s infinite;
    }

    #connState {
      opacity: .95;
      font-weight: 800;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.55; }
    }

    .container {
      flex: 1;
      min-height: 0;
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
      margin: 12px 12px 8px 12px;
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: hidden;
      border: 1px solid rgba(0,0,0,.04);
      animation: slideDown 0.25s ease;
    }

    .article-header {
      padding: 14px 16px;
      cursor: pointer;
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: linear-gradient(135deg, rgba(70,131,246,.10) 0%, rgba(124,92,255,.08) 100%);
      border-bottom: 1px solid var(--border);
      gap: 12px;
    }

    .article-header:hover {
      background: linear-gradient(135deg, rgba(70,131,246,.14) 0%, rgba(124,92,255,.10) 100%);
    }

    .article-title-area {
      flex: 1;
      min-width: 0;
    }

    .article-category {
      display: inline-block;
      background: var(--primary-050);
      color: var(--primary);
      border: 1px solid rgba(70,131,246,.18);
      font-size: 11px;
      font-weight: 800;
      padding: 4px 10px;
      border-radius: 999px;
      margin-bottom: 8px;
    }

    .article-title {
      font-size: 15px;
      font-weight: 800;
      color: var(--text);
      line-height: 1.35;
      margin-bottom: 6px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .article-summary {
      font-size: 13px;
      color: var(--muted);
      line-height: 1.5;
      overflow: hidden;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
    }

    .article-toggle {
      flex-shrink: 0;
      font-size: 18px;
      color: rgba(255,255,255,.96);
      background: rgba(70,131,246,.35);
      width: 36px;
      height: 36px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.25s, background 0.2s;
    }
    .article-toggle.expanded { transform: rotate(180deg); }
    .article-header:hover .article-toggle { background: rgba(70,131,246,.45); }

    .article-content {
      max-height: 0;
      overflow: hidden;
      transition: max-height 0.28s ease;
      background: white;
    }
    .article-content.expanded {
      max-height: 380px;
      overflow-y: auto;
    }
    .article-body {
      padding: 16px;
      font-size: 14px;
      line-height: 1.75;
      color: var(--text);
      white-space: pre-wrap;
      word-wrap: break-word;
    }

    .join-section {
      background: var(--card);
      margin: 12px;
      padding: 16px;
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      border: 1px solid rgba(0,0,0,.04);
      animation: slideDown 0.25s ease;
    }

    @keyframes slideDown {
      from { opacity: 0; transform: translateY(-12px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .status {
      color: var(--muted);
      font-size: 14px;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 700;
    }
    .status::before { content: "💬"; font-size: 18px; }

    .join-form { display: flex; gap: 10px; }

    input {
      flex: 1;
      padding: 13px 14px;
      border: 1.5px solid var(--border);
      border-radius: var(--radius-sm);
      font-size: 15px;
      transition: all 0.18s;
      outline: none;
      background: #fff;
    }
    input:focus { box-shadow: var(--focus); border-color: rgba(70,131,246,.55); }
    input:disabled { background: #f1f3f6; cursor: not-allowed; opacity: 0.7; }

    button {
      padding: 13px 16px;
      border: none;
      border-radius: var(--radius-sm);
      font-size: 15px;
      font-weight: 800;
      cursor: pointer;
      transition: all 0.18s;
      white-space: nowrap;
      outline: none;
    }

    button.primary {
      background: var(--primary);
      color: white;
      box-shadow: 0 10px 18px rgba(70,131,246,.22);
    }
    button.primary:hover:not(:disabled) {
      background: var(--primary-600);
      transform: translateY(-1px);
      box-shadow: 0 12px 22px rgba(70,131,246,.28);
    }
    button.primary:active:not(:disabled) { transform: translateY(0); }
    button:disabled { background: #a9b9d7; cursor: not-allowed; box-shadow: none; }

    button:focus-visible,
    input:focus-visible {
      outline: none;
      box-shadow: var(--focus);
    }

    .hint {
      margin-top: 10px;
      font-size: 12px;
      color: var(--muted2);
      text-align: center;
      font-weight: 600;
    }

    .messages-container {
      flex: 1;
      min-height: 0;
      overflow-y: auto;
      padding: 14px 12px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      scroll-behavior: smooth;
    }

    .messages-container::-webkit-scrollbar { width: 6px; }
    .messages-container::-webkit-scrollbar-thumb { background: rgba(17,24,39,.12); border-radius: 999px; }

    .message {
      display: flex;
      gap: 8px;
      align-items: flex-end;
      animation: fadeIn 0.22s ease;
      max-width: 85%;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .message.me { align-self: flex-end; flex-direction: row-reverse; }
    .message.system { align-self: center; max-width: 100%; }

    .message-content { display: flex; flex-direction: column; gap: 4px; }
    .message.me .message-content { align-items: flex-end; }

    .message-author {
      font-size: 12px;
      font-weight: 800;
      color: var(--muted);
      padding: 0 6px;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .admin-badge {
      display: inline-block;
      background: linear-gradient(135deg, #4683F6 0%, #7C5CFF 100%);
      color: white;
      font-size: 10px;
      font-weight: 900;
      padding: 2px 6px;
      border-radius: 8px;
      text-transform: uppercase;
    }

    .message-bubble {
      padding: 12px 14px;
      border-radius: var(--radius);
      word-wrap: break-word;
      max-width: 100%;
      position: relative;
      line-height: 1.5;
    }

    .message:not(.me) .message-bubble {
      background: var(--bubble-other);
      color: var(--text);
      border-bottom-left-radius: 6px;
      border: 1px solid rgba(17,24,39,.04);
    }

    .message.me .message-bubble {
      background: var(--bubble-me);
      color: white;
      border-bottom-right-radius: 6px;
      box-shadow: 0 10px 18px rgba(70,131,246,.18);
    }

    .message.system .message-bubble {
      background: rgba(17,24,39,.04);
      border: 1px dashed rgba(17,24,39,.10);
      color: var(--muted);
      font-size: 12px;
      text-align: center;
      padding: 8px 12px;
      border-radius: 999px;
    }

    .message-time {
      font-size: 11px;
      color: var(--muted2);
      padding: 0 4px;
      white-space: nowrap;
      font-weight: 700;
    }

    .message-reaction {
      display: flex;
      align-items: center;
      gap: 4px;
      margin-top: 6px;
    }

    .reaction-button {
      background: transparent;
      border: 1px solid rgba(17,24,39,.10);
      padding: 4px 8px;
      cursor: pointer;
      border-radius: 999px;
      transition: all 180ms ease-out;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      user-select: none;
      font-family: inherit;
      font-weight: 800;
    }

    .reaction-button:hover {
      background: rgba(229, 72, 77, 0.08);
      border-color: rgba(229, 72, 77, 0.18);
    }

    .reaction-button.reacted {
      background: rgba(229, 72, 77, 0.12);
      border-color: rgba(229, 72, 77, 0.22);
    }

    .reaction-icon { font-size: 16px; line-height: 1; color: #9AA1AD; }
    .reaction-button.reacted .reaction-icon { color: #E5484D; }

    .reaction-count { font-size: 12px; color: #9AA1AD; line-height: 1; }
    .reaction-button.reacted .reaction-count { color: #E5484D; }

    .delete-button {
      background: transparent;
      border: 1px solid rgba(220, 38, 38, 0.18);
      padding: 4px 8px;
      cursor: pointer;
      border-radius: 999px;
      transition: all 180ms ease-out;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      user-select: none;
      font-family: inherit;
      font-weight: 800;
      font-size: 11px;
      color: #dc2626;
      margin-left: 6px;
    }

    .delete-button:hover {
      background: rgba(220, 38, 38, 0.08);
      border-color: rgba(220, 38, 38, 0.28);
    }

    .delete-icon { font-size: 14px; line-height: 1; }

    .kick-button {
      background: transparent;
      border: 1px solid rgba(251, 146, 60, 0.18);
      padding: 4px 8px;
      cursor: pointer;
      border-radius: 999px;
      transition: all 180ms ease-out;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      user-select: none;
      font-family: inherit;
      font-weight: 800;
      font-size: 11px;
      color: #ea580c;
      margin-left: 6px;
    }

    .kick-button:hover {
      background: rgba(251, 146, 60, 0.08);
      border-color: rgba(251, 146, 60, 0.28);
    }

    .kick-icon { font-size: 14px; line-height: 1; }

    .verify-fab-wrap {
      max-width: 900px;
      width: 100%;
      margin: 0 auto 8px auto;
      padding: 0 12px;
      display: flex;
      justify-content: flex-end;
    }

    .verify-fab {
      width: 52px;
      height: 52px;
      padding: 0;
      border: 1px solid rgba(255,255,255,.55);
      border-radius: 50%;
      background: var(--primary);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 14px 26px rgba(70, 131, 246, 0.30);
      transition: all 180ms ease-out;
      transform: translate(1.5px, -1.5px);
    }
    .verify-fab:hover { background: var(--primary-600); transform: translate(1.5px, -2.5px); }
    .verify-fab:active { transform: translate(1.5px, -1.5px); }
    .verify-fab:focus-visible { outline: none; box-shadow: var(--focus); }

    .verify-fab svg {
      width: 24px;
      height: 24px;
      fill: none;
      stroke: white;
      stroke-width: 2.2;
      stroke-linecap: round;
      stroke-linejoin: round;
      display: block;
    }

    .input-container {
      position: sticky;
      bottom: 0;
      background: rgba(255,255,255,.92);
      backdrop-filter: blur(10px);
      padding: 12px 12px calc(12px + env(safe-area-inset-bottom));
      border-top: 1px solid var(--border);
      box-shadow: 0 -10px 24px rgba(17,24,39,.06);
    }

    .input-container-inner {
      max-width: 900px;
      margin: 0 auto;
      display: flex;
      gap: 10px;
      align-items: center;
    }

    .input-wrapper { flex: 1; position: relative; }

    #msg {
      width: 100%;
      padding: 13px 14px;
      border: 1.5px solid var(--border);
      border-radius: 999px;
      font-size: 15px;
      font-family: inherit;
      outline: none;
    }
    #msg:focus { box-shadow: var(--focus); border-color: rgba(70,131,246,.55); }

    #send {
      border-radius: 50%;
      width: 48px;
      height: 48px;
      padding: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    #send svg {
      width: 20px;
      height: 20px;
      fill: none;
      stroke: white;
      stroke-width: 2.2;
      stroke-linecap: round;
      stroke-linejoin: round;
    }

    .empty-state {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: var(--muted2);
      gap: 10px;
      padding: 40px 20px;
    }
    .empty-state-icon { font-size: 46px; opacity: 0.55; }
    .empty-state-text { font-size: 14px; text-align: center; font-weight: 700; }

    @media (max-width: 600px) {
      .message { max-width: 92%; }
      .join-form { flex-direction: column; }
      button:not(#send):not(.verify-fab) { width: 100%; }
      #headerTitle { max-width: 46vw; }
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="header-content">
      <h1>
        <span class="logo" aria-hidden="true">💬</span>
        <span id="headerTitle">오늘의 이슈</span>
      </h1>
      <div class="online-badge" aria-label="접속 상태">
        <span class="online-dot" aria-hidden="true"></span>
        <span id="onlineCount">0</span>명
        <span id="connState">• 연결 대기</span>
      </div>
    </div>
  </div>

  <div class="container">
    <!-- 기사 섹션 -->
    <div class="article-section">
      <div class="article-header" onclick="toggleArticle()" role="button" tabindex="0" aria-controls="articleContent" aria-expanded="false">
        <div class="article-title-area">
          <div class="article-category">__ISSUE_CATEGORY__</div>
          <div class="article-title">__ISSUE_TITLE__</div>
          <div class="article-summary">__ISSUE_SUMMARY__</div>
        </div>
        <div class="article-toggle" id="articleToggle" aria-hidden="true">📰</div>
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
          aria-label="닉네임 입력"
        />
        <button id="joinBtn" class="primary" aria-label="채팅방 입장">입장하기</button>
      </div>
      <div class="hint">
        다른 사용자와 실시간으로 대화할 수 있습니다
      </div>
    </div>

    <div class="messages-container" id="messages" role="log" aria-live="polite" aria-relevant="additions">
      <div class="empty-state">
        <div class="empty-state-icon" aria-hidden="true">💭</div>
        <div class="empty-state-text">
          아직 메시지가 없습니다<br>
          첫 메시지를 보내보세요 !
        </div>
      </div>
    </div>

    <div class="verify-fab-wrap" style="display: none;" id="verifyFabWrap">
      <button id="verifyFab" class="verify-fab" type="button" aria-label="검증 화면 열기">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="11" cy="11" r="6.5"></circle>
          <path d="M16 16L20.5 20.5"></path>
        </svg>
      </button>
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
            aria-label="메시지 입력"
          />
        </div>
        <button id="send" class="primary" disabled aria-label="메시지 전송">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M3 11.5L20 4L13 20L10 13L3 11.5Z"></path>
            <path d="M10 13L20 4"></path>
          </svg>
        </button>
      </div>
    </div>
  </div>

  <script>
    const issueId = "__ISSUE_ID__";
    const wsUrl = "__WS_URL__";
    const verifyHomeUrl = "__VERIFY_HOME_URL__";
    const issueTitle = "__ISSUE_TITLE__";

    // localStorage에서 userId와 nickname 복원 또는 새로 생성
    const STORAGE_KEY_USER_ID = "olala_web_user_id";
    const STORAGE_KEY_NICKNAME = "olala_web_nickname";
    const STORAGE_KEY_ISSUE_PREFIX = "olala_joined_";

    let userId = localStorage.getItem(STORAGE_KEY_USER_ID);
    if (!userId) {
      userId = "web_" + Math.random().toString(36).slice(2, 10);
      localStorage.setItem(STORAGE_KEY_USER_ID, userId);
    }

    let nickname = localStorage.getItem(STORAGE_KEY_NICKNAME) || ("사용자-" + Math.floor(Math.random() * 1000));

    let ws = null;
    let isJoined = false;
    let reconnectTimer = null;
    let reconnectAttempts = 0;

    const messageMap = new Map(); // messageId -> message element

    const messagesEl = document.getElementById("messages");
    const onlineCountEl = document.getElementById("onlineCount");
    const statusEl = document.getElementById("status");
    const joinSectionEl = document.getElementById("joinSection");
    const nicknameEl = document.getElementById("nickname");
    const joinBtnEl = document.getElementById("joinBtn");
    const inputContainerEl = document.getElementById("inputContainer");
    const verifyFabWrapEl = document.getElementById("verifyFabWrap");
    const verifyFabEl = document.getElementById("verifyFab");
    const msgEl = document.getElementById("msg");
    const sendBtnEl = document.getElementById("send");

    document.getElementById("headerTitle").textContent = "오늘의 이슈 실시간 채팅방";

    nicknameEl.value = nickname;

    function setConnState(text) {
      const el = document.getElementById("connState");
      if (el) el.textContent = "• " + text;
    }

    function formatTime(date) {
      return date.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
    }

    function hideEmptyState() {
      const emptyState = messagesEl.querySelector('.empty-state');
      if (emptyState) emptyState.style.display = "none";
    }

    function showEmptyStateIfNeeded() {
      const emptyState = messagesEl.querySelector('.empty-state');
      if (!emptyState) return;
      const hasAnyMessage = messagesEl.querySelector('.message') !== null;
      emptyState.style.display = (isJoined && !hasAnyMessage) ? "flex" : "none";
    }

    function addMessage(content, author = null, isMe = false, isSystem = false, messageId = null, reactionCount = 0, isReacted = false, authorUserId = null) {
      hideEmptyState();

      if (messageId && messageMap.has(messageId)) {
        return; // prevent duplicates on reconnect / re-delivery
      }

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

        const nameSpan = document.createElement("span");
        nameSpan.textContent = author;
        authorDiv.appendChild(nameSpan);

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

      if (!isSystem && messageId) {
        const reactionDiv = document.createElement("div");
        reactionDiv.className = "message-reaction";

        const reactionBtn = document.createElement("button");
        reactionBtn.className = "reaction-button" + (isReacted ? " reacted" : "");
        reactionBtn.type = "button";
        reactionBtn.setAttribute("aria-label", "좋아요 토글");
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

        // Add delete button for admins (non-web users)
        const currentUserIsAdmin = userId && !userId.startsWith("web_");
        if (currentUserIsAdmin) {
          const deleteBtn = document.createElement("button");
          deleteBtn.className = "delete-button";
          deleteBtn.type = "button";
          deleteBtn.setAttribute("aria-label", "메시지 삭제");
          deleteBtn.onclick = () => deleteMessage(messageId);

          const deleteIcon = document.createElement("span");
          deleteIcon.className = "delete-icon";
          deleteIcon.textContent = "🗑️";
          deleteBtn.appendChild(deleteIcon);

          const deleteText = document.createElement("span");
          deleteText.textContent = "삭제";
          deleteBtn.appendChild(deleteText);

          reactionDiv.appendChild(deleteBtn);

          // Add kick button for web users only (admins can kick web users)
          const isWebUser = authorUserId && authorUserId.startsWith("web_");
          if (isWebUser && !isMe) {
            const kickBtn = document.createElement("button");
            kickBtn.className = "kick-button";
            kickBtn.type = "button";
            kickBtn.setAttribute("aria-label", "사용자 퇴장");
            kickBtn.onclick = () => kickUser(authorUserId, author);

            const kickIcon = document.createElement("span");
            kickIcon.className = "kick-icon";
            kickIcon.textContent = "🚫";
            kickBtn.appendChild(kickIcon);

            const kickText = document.createElement("span");
            kickText.textContent = "퇴장";
            kickBtn.appendChild(kickText);

            reactionDiv.appendChild(kickBtn);
          }
        }

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
        verifyFabWrapEl.style.display = "flex";
        inputContainerEl.style.display = "block";
        showEmptyStateIfNeeded();
        msgEl.focus();
      } else {
        joinSectionEl.style.display = "block";
        verifyFabWrapEl.style.display = "none";
        inputContainerEl.style.display = "none";
        hideEmptyState();
        nicknameEl.disabled = false;
        joinBtnEl.disabled = false;
      }
    }

    function openVerifyHomeInput() {
      try {
        const target = new URL(verifyHomeUrl);
        target.searchParams.set("from", "web-chat");
        target.searchParams.set("issueId", issueId);
        window.location.assign(target.toString());
      } catch (_) {
        window.location.assign(verifyHomeUrl);
      }
    }

    function scheduleReconnect() {
      if (reconnectTimer) return;
      const delay = Math.min(15000, 800 * Math.pow(2, reconnectAttempts)); // 0.8s, 1.6s, 3.2s...
      reconnectAttempts += 1;
      setConnState("재연결 중...");
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        if (!isJoined) return;
        connectSocketOnly();
      }, delay);
    }

    function onWsMessage(e) {
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

        if (data.type === "message.deleted") {
          removeMessageFromUI(data.messageId);
          return;
        }

        if (data.type === "user.kicked") {
          // Current user was kicked
          addSystemMessage("🚫 " + (data.reason || "퇴장되었습니다"));
          isJoined = false;
          setJoinedState(false);
          if (ws) {
            ws.close();
            ws = null;
          }
          // Clear localStorage to force re-entry
          localStorage.removeItem(STORAGE_KEY_ISSUE_PREFIX + issueId);
          return;
        }

        if (data.type === "user.kicked.notification") {
          // Someone else was kicked
          addSystemMessage("🚫 사용자가 퇴장되었습니다");
          return;
        }

        if (data.type === "error") {
          addSystemMessage("⚠️ " + (data.message || "오류가 발생했습니다"));
          return;
        }
      } catch (err) {
        console.error("메시지 파싱 실패:", err);
      }
    }

    async function loadChatHistory() {
      try {
        const host = window.location.host;
        const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:';
        const pathPrefix = window.location.pathname.startsWith('/v1/') ? '/v1' : '';
        const apiUrl = `${protocol}//${host}${pathPrefix}/chat/messages/${issueId}?userId=${encodeURIComponent(userId)}&limit=100`;

        const response = await fetch(apiUrl);
        if (!response.ok) {
          console.warn("채팅 히스토리를 불러올 수 없습니다:", response.status);
          return;
        }

        const messages = await response.json();

        // 기존 메시지 초기화 및 히스토리 로드
        if (Array.isArray(messages)) {
          messages.forEach(msg => {
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
          });
        }
      } catch (err) {
        console.error("채팅 히스토리 로드 실패:", err);
      }
    }

    function connectSocketOnly() {
      setConnState("연결 중...");
      try {
        ws = new WebSocket(wsUrl);
      } catch (_) {
        scheduleReconnect();
        return;
      }

      ws.onopen = () => {
        setConnState("연결됨");
        reconnectAttempts = 0;

        ws.send(JSON.stringify({
          type: "join",
          issueId: issueId,
          userId: userId,
          nickname: nickname,
          sentAt: new Date().toISOString()
        }));
      };

      ws.onmessage = onWsMessage;

      ws.onerror = () => {
        setConnState("연결 오류");
      };

      ws.onclose = () => {
        setConnState("연결 끊김");
        if (isJoined) scheduleReconnect();
      };
    }

    async function connect() {
      const rawNickname = nicknameEl.value.trim();
      if (!rawNickname) {
        statusEl.textContent = "⚠️ 닉네임을 입력해주세요";
        nicknameEl.focus();
        return;
      }

      nickname = rawNickname.slice(0, 20);

      // localStorage에 닉네임과 입장 상태 저장
      localStorage.setItem(STORAGE_KEY_NICKNAME, nickname);
      localStorage.setItem(STORAGE_KEY_ISSUE_PREFIX + issueId, "true");

      statusEl.textContent = "🔄 연결 중...";
      joinBtnEl.disabled = true;
      nicknameEl.disabled = true;

      setJoinedState(true);

      // 채팅 히스토리를 먼저 불러온 후 WebSocket 연결
      await loadChatHistory();
      connectSocketOnly();
    }

    function sendMessage() {
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        addSystemMessage("연결이 끊겼습니다. 재연결 중입니다...");
        setConnState("재연결 중...");
        scheduleReconnect();
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
      sendBtnEl.disabled = true;
      msgEl.focus();
    }

    function toggleArticle() {
      const contentEl = document.getElementById("articleContent");
      const toggleEl = document.getElementById("articleToggle");
      const headerEl = document.querySelector(".article-header");
      const isExpanded = contentEl.classList.contains("expanded");

      if (isExpanded) {
        contentEl.classList.remove("expanded");
        toggleEl.classList.remove("expanded");
        toggleEl.textContent = "📰";
        headerEl.setAttribute("aria-expanded", "false");
      } else {
        contentEl.classList.add("expanded");
        toggleEl.classList.add("expanded");
        toggleEl.textContent = "🔼";
        headerEl.setAttribute("aria-expanded", "true");
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

    function deleteMessage(messageId) {
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        addSystemMessage("연결이 끊어졌습니다.");
        return;
      }

      if (!confirm("이 메시지를 삭제하시겠습니까?")) {
        return;
      }

      ws.send(JSON.stringify({
        type: "message.delete",
        messageId: messageId,
        userId: userId,
        sentAt: new Date().toISOString()
      }));
    }

    function kickUser(targetUserId, targetNickname) {
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        addSystemMessage("연결이 끊어졌습니다.");
        return;
      }

      if (!confirm(`${targetNickname || '사용자'}님을 퇴장시키시겠습니까?\n(10분간 재접속 불가)`)) {
        return;
      }

      ws.send(JSON.stringify({
        type: "user.kick",
        targetUserId: targetUserId,
        userId: userId,
        banDuration: 10,
        sentAt: new Date().toISOString()
      }));
    }

    function removeMessageFromUI(messageId) {
      const msgDiv = messageMap.get(messageId);
      if (msgDiv) {
        msgDiv.remove();
        messageMap.delete(messageId);
        showEmptyStateIfNeeded();
      }
    }

    function updateReaction(messageId, count, isReacted) {
      const msgDiv = messageMap.get(messageId);
      if (!msgDiv) return;

      const reactionBtn = msgDiv.querySelector(".reaction-button");
      if (!reactionBtn) return;

      if (isReacted) reactionBtn.classList.add("reacted");
      else reactionBtn.classList.remove("reacted");

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

    joinBtnEl.onclick = () => connect();
    sendBtnEl.onclick = sendMessage;
    verifyFabEl.onclick = openVerifyHomeInput;

    nicknameEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !joinBtnEl.disabled) connect();
    });

    msgEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        sendMessage();
      }
    });

    msgEl.addEventListener("input", () => {
      sendBtnEl.disabled = !msgEl.value.trim() || !isJoined;
    });

    // 페이지 로드 시 이전 입장 상태 확인 및 복원
    async function checkAndRestoreSession() {
      const wasJoined = localStorage.getItem(STORAGE_KEY_ISSUE_PREFIX + issueId);
      const savedNickname = localStorage.getItem(STORAGE_KEY_NICKNAME);

      if (wasJoined === "true" && savedNickname) {
        // 이전에 입장한 적이 있으면 자동으로 입장
        nickname = savedNickname;
        nicknameEl.value = nickname;
        setJoinedState(true);

        // 채팅 히스토리를 먼저 불러온 후 WebSocket 연결
        await loadChatHistory();
        connectSocketOnly();
      } else {
        // 입장 전 상태
        setJoinedState(false);
      }
    }

    // 페이지 로드 시 세션 복원 시도
    checkAndRestoreSession();

    // Allow keyboard toggle on article header
    document.querySelector(".article-header").addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggleArticle();
      }
    });
  </script>
</body>
</html>"""

    html = (
        html.replace("__ISSUE_ID__", safe_issue_id)
            .replace("__WS_URL__", safe_ws_url)
            .replace("__VERIFY_HOME_URL__", safe_verify_home_url)
            .replace("__ISSUE_TITLE__", issue_title)
            .replace("__ISSUE_SUMMARY__", issue_summary)
            .replace("__ISSUE_CONTENT__", issue_content)
            .replace("__ISSUE_CATEGORY__", issue_category)
    )
    return HTMLResponse(content=html)


@app.get("/home-input", response_class=HTMLResponse)
@app.get("/v1/home-input", response_class=HTMLResponse)
async def home_input_page(request: Request, issueId: str = "") -> HTMLResponse:
    requested_issue_id = issueId.strip()

    async with AsyncSessionLocal() as session:
        if requested_issue_id:
            issue = await ChatRepository.ensure_issue(session, requested_issue_id)
        else:
            issue = await ChatRepository.ensure_today_issue(session)

    issue_title = escape(issue.title, quote=False)
    issue_summary = escape(issue.summary, quote=False)
    issue_category = escape(issue.category, quote=False)
    safe_issue_id = escape(issue.id, quote=True)

    route_prefix = "/v1" if request.url.path.startswith("/v1/") else ""
    return_chat_url = f"{route_prefix}/web-chat?issueId={quote(issue.id)}"
    safe_return_chat_url = escape(return_chat_url, quote=True)
    verify_analyze_url = f"{settings.api_prefix}/verify/analyze"
    verify_search_url = f"{settings.api_prefix}/verify/search"
    safe_verify_analyze_url = escape(verify_analyze_url, quote=True)
    safe_verify_search_url = escape(verify_search_url, quote=True)

    html = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no" />
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'self'; connect-src 'self' ws: wss:; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'">
  <title>OLaLA 검증 입력</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }

    :root {
      --primary: #4683F6;
      --primary-dark: #3567d6;
      --surface: #ffffff;
      --page-bg: #F6F8FC;
      --line: #E6E9EF;
      --text: #111827;
      --muted: #6b7280;
      --warn: #ca8a04;
      --danger: #dc2626;
      --ok: #0f766e;
      --focus: 0 0 0 4px rgba(70,131,246,.18);
      --shadow: 0 6px 16px rgba(17,24,39,.08);
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
      color: var(--text);
      background: var(--page-bg);
      min-height: 100dvh;
      padding-bottom: env(safe-area-inset-bottom);
    }

    .topbar {
      height: 56px;
      background: rgba(255,255,255,.92);
      backdrop-filter: blur(10px);
      border-bottom: 1px solid rgba(70,131,246,.12);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 16px;
      position: sticky;
      top: 0;
      z-index: 5;
    }

    .brand {
      font-size: 22px;
      font-weight: 900;
      letter-spacing: -0.4px;
      color: var(--primary);
    }

    .back-btn {
      border: 0;
      background: transparent;
      color: var(--muted);
      font-size: 14px;
      font-weight: 800;
      cursor: pointer;
      padding: 8px 10px;
      border-radius: 12px;
    }
    .back-btn:hover { background: rgba(0, 0, 0, 0.05); color: var(--text); }
    .back-btn:focus-visible { outline: none; box-shadow: var(--focus); }

    .screen {
      width: 100%;
      max-width: 900px;
      margin: 0 auto;
      padding: 12px 16px 20px;
    }

    .issue-banner {
      background: var(--surface);
      border: 1px solid rgba(0,0,0,0.06);
      border-radius: 14px;
      padding: 14px;
      margin-bottom: 12px;
      box-shadow: var(--shadow);
    }

    .issue-category {
      display: inline-block;
      font-size: 11px;
      font-weight: 900;
      color: var(--primary);
      background: #e9f3ff;
      border-radius: 999px;
      padding: 4px 10px;
      margin-bottom: 8px;
      border: 1px solid rgba(70,131,246,.18);
    }

    .issue-title {
      font-size: 15px;
      font-weight: 900;
      line-height: 1.35;
      margin-bottom: 6px;
    }

    .issue-summary {
      font-size: 13px;
      line-height: 1.55;
      color: var(--muted);
      font-weight: 650;
    }

    .panel {
      background: var(--surface);
      border: 1px solid rgba(0,0,0,0.06);
      border-radius: 14px;
      padding: 14px;
      box-shadow: var(--shadow);
    }

    .state.hidden {
      display: none;
    }

    .mode-selector {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-bottom: 12px;
    }

    .mode-btn {
      border: 1px solid var(--line);
      background: #f5f7fb;
      color: var(--muted);
      font-size: 14px;
      font-weight: 900;
      border-radius: 12px;
      padding: 10px 12px;
      cursor: pointer;
      transition: all 160ms ease-out;
    }
    .mode-btn.active {
      color: white;
      background: var(--primary);
      border-color: var(--primary);
      box-shadow: 0 10px 18px rgba(70,131,246,.20);
    }
    .mode-btn:focus-visible { outline: none; box-shadow: var(--focus); }

    #verifyInput {
      width: 100%;
      min-height: 220px;
      border: 1.5px solid var(--line);
      border-radius: 14px;
      padding: 12px 14px;
      font-size: 15px;
      line-height: 1.55;
      resize: vertical;
      outline: none;
      background: #fff;
      margin-bottom: 12px;
      font-family: inherit;
    }
    #verifyInput:focus {
      border-color: rgba(70,131,246,.55);
      box-shadow: var(--focus);
    }

    #verifyBtn,
    .sub-btn {
      width: 100%;
      border: 0;
      border-radius: 999px;
      color: white;
      font-size: 16px;
      font-weight: 900;
      padding: 14px 16px;
      cursor: pointer;
      transition: all 160ms ease-out;
    }

    #verifyBtn {
      background: var(--primary);
      box-shadow: 0 12px 22px rgba(70,131,246,.24);
    }
    #verifyBtn:hover { background: var(--primary-dark); }
    #verifyBtn:disabled { background: #9fbef9; cursor: not-allowed; box-shadow: none; }
    #verifyBtn:focus-visible { outline: none; box-shadow: var(--focus); }

    .sub-btn {
      margin-top: 12px;
      background: #eef2ff;
      color: #374151;
      border: 1px solid var(--line);
    }

    .status-line {
      margin-top: 10px;
      min-height: 18px;
      font-size: 12px;
      color: var(--muted);
      font-weight: 700;
    }
    .status-line.error { color: var(--danger); font-weight: 900; }

    .search-preview {
      margin-bottom: 12px;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px;
      background: #f8fafc;
    }

    .search-preview-title {
      font-size: 12px;
      color: var(--muted);
      font-weight: 800;
      margin-bottom: 8px;
    }

    .search-preview-list {
      list-style: none;
      display: grid;
      gap: 8px;
    }

    .search-preview-item {
      border: 1px solid #e5e7eb;
      border-radius: 10px;
      padding: 8px;
      background: white;
    }

    .search-preview-link {
      color: #1d4ed8;
      font-size: 13px;
      font-weight: 800;
      text-decoration: none;
    }
    .search-preview-link:hover { text-decoration: underline; }

    .search-preview-meta {
      margin-top: 4px;
      font-size: 12px;
      color: var(--muted);
      line-height: 1.45;
    }

    .loading-state {
      min-height: 440px;
      border-radius: 16px;
      background: #5A88FF;
      color: white;
      padding: 22px 16px;
      text-align: center;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }

    .loading-center {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 12px;
    }

    .loading-badge {
      width: 92px;
      height: 92px;
      border-radius: 28px;
      border: 1px solid rgba(255,255,255,.20);
      background: rgba(255,255,255,.14);
      box-shadow: 0 12px 24px rgba(17,24,39,.2);
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .spinner {
      width: 34px;
      height: 34px;
      border-radius: 50%;
      border: 4px solid rgba(255,255,255,.24);
      border-top-color: rgba(255,255,255,.94);
      animation: spin 1.0s linear infinite;
    }

    @keyframes spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }

    .loading-headline {
      font-size: 24px;
      font-weight: 900;
      line-height: 1.15;
    }

    .loading-subtext {
      font-size: 14px;
      line-height: 1.45;
      color: rgba(255,255,255,.84);
      font-weight: 600;
      white-space: pre-line;
    }

    .loading-steps {
      margin-top: 6px;
      list-style: none;
      width: 100%;
      display: grid;
      gap: 8px;
    }

    .loading-step {
      border: 1px solid rgba(255,255,255,.22);
      border-radius: 12px;
      padding: 8px 10px;
      text-align: left;
      color: rgba(255,255,255,.72);
      font-size: 13px;
      font-weight: 700;
      background: rgba(255,255,255,.08);
    }
    .loading-step.active {
      color: #0f172a;
      background: rgba(255,255,255,.96);
      border-color: rgba(255,255,255,.96);
    }

    .loading-note {
      font-size: 12px;
      color: rgba(255,255,255,.78);
      line-height: 1.45;
      margin-top: 12px;
      font-weight: 650;
    }

    .result-state {
      display: grid;
      gap: 12px;
    }

    .result-pill {
      display: inline-flex;
      width: fit-content;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 900;
      padding: 6px 11px;
    }
    .result-pill.ok { color: var(--ok); background: rgba(15, 118, 110, 0.12); }
    .result-pill.warn { color: var(--warn); background: rgba(202, 138, 4, 0.12); }
    .result-pill.danger { color: var(--danger); background: rgba(220, 38, 38, 0.12); }
    .result-pill.neutral { color: #334155; background: rgba(148, 163, 184, 0.2); }

    .result-headline {
      font-size: 22px;
      font-weight: 900;
      line-height: 1.18;
    }

    .result-card {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      background: #f8fafc;
    }

    .result-card-title {
      font-size: 13px;
      font-weight: 900;
      color: #1f2937;
      margin-bottom: 8px;
    }

    .confidence-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
      font-size: 13px;
      font-weight: 800;
      color: #1f2937;
    }

    .confidence-track {
      width: 100%;
      height: 10px;
      border-radius: 999px;
      background: #e5e7eb;
      overflow: hidden;
    }

    .confidence-fill {
      height: 100%;
      width: 0%;
      background: var(--primary);
      transition: width 240ms ease-out;
    }

    .result-reason {
      font-size: 14px;
      color: #374151;
      line-height: 1.5;
      font-weight: 650;
      white-space: pre-line;
    }

    .evidence-header {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
      font-weight: 900;
      color: #111827;
      margin-bottom: 8px;
    }

    .evidence-count {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 24px;
      height: 24px;
      border-radius: 999px;
      font-size: 12px;
      color: #1f2937;
      background: #e5e7eb;
      padding: 0 8px;
      font-weight: 900;
    }

    .evidence-list {
      display: grid;
      gap: 8px;
    }

    .evidence-item {
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      padding: 10px;
      background: #fff;
      box-shadow: 0 4px 12px rgba(17,24,39,.04);
    }

    .evidence-link {
      display: block;
      color: #1d4ed8;
      font-size: 14px;
      font-weight: 900;
      text-decoration: none;
      margin-bottom: 6px;
    }
    .evidence-link:hover { text-decoration: underline; }

    .evidence-meta {
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 5px;
      font-weight: 700;
    }

    .evidence-snippet {
      font-size: 13px;
      color: #374151;
      line-height: 1.5;
      font-weight: 600;
      white-space: pre-line;
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand">OLaLA</div>
    <button class="back-btn" id="backToChatBtn" aria-label="채팅으로 돌아가기">채팅으로 돌아가기</button>
  </header>

  <main class="screen">
    <section class="issue-banner">
      <div class="issue-category">__ISSUE_CATEGORY__</div>
      <h1 class="issue-title">__ISSUE_TITLE__</h1>
      <p class="issue-summary">__ISSUE_SUMMARY__</p>
    </section>

    <section class="panel">
      <div id="inputState" class="state">
        <div class="mode-selector" role="tablist" aria-label="검증 모드 선택">
          <button id="modeUrl" class="mode-btn active" type="button" role="tab" aria-selected="true">URL</button>
          <button id="modeText" class="mode-btn" type="button" role="tab" aria-selected="false">텍스트</button>
        </div>

        <textarea id="verifyInput" placeholder="검증할 URL을 붙여넣어 주세요.&#10;예) https://example.com/news/123" aria-label="검증 입력"></textarea>

        <div class="search-preview" id="searchPreview" hidden>
          <div class="search-preview-title">관련 근거 미리보기</div>
          <ul class="search-preview-list" id="searchPreviewList"></ul>
        </div>

        <button id="verifyBtn" type="button" aria-label="검증 시작">검증 시작하기</button>
        <div class="status-line" id="statusLine" aria-live="polite"></div>
      </div>

      <div id="loadingState" class="state hidden" aria-live="polite">
        <div class="loading-state">
          <div class="loading-center">
            <div class="loading-badge" aria-hidden="true">
              <div class="spinner"></div>
            </div>

            <h2 class="loading-headline" id="loadingHeadline">주장을 분석하고 있어요</h2>
            <p class="loading-subtext" id="loadingSubtext">URL이나 문장에서 핵심을 추출하고 있어요.</p>

            <ul class="loading-steps" aria-label="검증 단계">
              <li class="loading-step active" id="loadingStep0">1. 주장/콘텐츠 추출</li>
              <li class="loading-step" id="loadingStep1">2. 관련 근거 수집</li>
              <li class="loading-step" id="loadingStep2">3. 근거 기반 판단 제공</li>
            </ul>
          </div>

          <div>
            <p class="loading-note">※ 결과는 참고용이며, 출처/링크를 함께 확인해 주세요.</p>
            <button id="cancelLoadingBtn" class="sub-btn" type="button" aria-label="검증 취소">취소</button>
          </div>
        </div>
      </div>

      <div id="resultState" class="state hidden">
        <span class="result-pill neutral" id="resultPill">추가 검증 필요</span>
        <h2 class="result-headline" id="resultHeadline">검증 결과</h2>

        <section class="result-card">
          <div class="result-card-title">신뢰도</div>
          <div class="confidence-row">
            <span>근거 기반 점수</span>
            <span id="confidencePercent">0%</span>
          </div>
          <div class="confidence-track">
            <div class="confidence-fill" id="confidenceFill"></div>
          </div>
        </section>

        <section class="result-card">
          <div class="result-card-title">요약</div>
          <p class="result-reason" id="resultReason"></p>
        </section>

        <section class="result-card">
          <div class="evidence-header">
            <span>근거</span>
            <span class="evidence-count" id="evidenceCount">0</span>
          </div>
          <div class="evidence-list" id="evidenceList"></div>
        </section>

        <button id="retryBtn" class="sub-btn" type="button" aria-label="다시 검증하기">다시 검증하기</button>
      </div>
    </section>
  </main>

  <script>
    const issueId = "__ISSUE_ID__";
    const returnChatUrl = "__RETURN_CHAT_URL__";
    const verifyAnalyzeUrl = "__VERIFY_ANALYZE_URL__";
    const verifySearchUrl = "__VERIFY_SEARCH_URL__";

    const modeUrlEl = document.getElementById("modeUrl");
    const modeTextEl = document.getElementById("modeText");
    const inputEl = document.getElementById("verifyInput");
    const verifyBtnEl = document.getElementById("verifyBtn");
    const statusLineEl = document.getElementById("statusLine");
    const backBtnEl = document.getElementById("backToChatBtn");
    const inputStateEl = document.getElementById("inputState");
    const loadingStateEl = document.getElementById("loadingState");
    const resultStateEl = document.getElementById("resultState");
    const loadingHeadlineEl = document.getElementById("loadingHeadline");
    const loadingSubtextEl = document.getElementById("loadingSubtext");
    const loadingStepEls = [
      document.getElementById("loadingStep0"),
      document.getElementById("loadingStep1"),
      document.getElementById("loadingStep2")
    ];
    const cancelLoadingBtnEl = document.getElementById("cancelLoadingBtn");
    const retryBtnEl = document.getElementById("retryBtn");
    const resultPillEl = document.getElementById("resultPill");
    const resultHeadlineEl = document.getElementById("resultHeadline");
    const resultReasonEl = document.getElementById("resultReason");
    const confidencePercentEl = document.getElementById("confidencePercent");
    const confidenceFillEl = document.getElementById("confidenceFill");
    const evidenceCountEl = document.getElementById("evidenceCount");
    const evidenceListEl = document.getElementById("evidenceList");
    const searchPreviewEl = document.getElementById("searchPreview");
    const searchPreviewListEl = document.getElementById("searchPreviewList");

    const placeholders = {
      url: "검증할 URL을 붙여넣어 주세요.\\n예) https://example.com/news/123",
      text: "검증할 문장을 입력해 주세요.\\n예) OOO는 2025년에 새로운 법안을 발표했다."
    };

    const loadingFrames = [
      {
        headline: "주장을 분석하고 있어요",
        subtext: "URL이나 문장에서 핵심을 추출하고 있어요."
      },
      {
        headline: "관련 근거를 찾고 있어요",
        subtext: "신뢰 가능한 출처와 기사를 수집하고 있어요."
      },
      {
        headline: "최종 판단을 만들고 있어요",
        subtext: "근거를 바탕으로 결과를 정리하고 있어요."
      }
    ];

    const verdictView = {
      true: { label: "대체로 사실", tone: "ok" },
      false: { label: "주의 필요", tone: "danger" },
      mixed: { label: "혼합 결과", tone: "warn" },
      unverified: { label: "추가 검증 필요", tone: "neutral" }
    };

    let mode = "url";
    let currentState = "input";
    let loadingTimer = null;
    let loadingStep = 0;
    let searchDebounceTimer = null;
    let searchAbortController = null;
    let analyzeAbortController = null;

    function setMode(nextMode) {
      mode = nextMode;
      modeUrlEl.classList.toggle("active", mode === "url");
      modeTextEl.classList.toggle("active", mode === "text");
      modeUrlEl.setAttribute("aria-selected", mode === "url" ? "true" : "false");
      modeTextEl.setAttribute("aria-selected", mode === "text" ? "true" : "false");
      inputEl.placeholder = placeholders[mode];
      clearStatus();
      if (mode === "url") {
        requestSearchPreview(inputEl.value.trim());
      } else {
        hideSearchPreview();
      }
    }

    function setState(nextState) {
      currentState = nextState;
      inputStateEl.classList.toggle("hidden", nextState !== "input");
      loadingStateEl.classList.toggle("hidden", nextState !== "loading");
      resultStateEl.classList.toggle("hidden", nextState !== "result");
    }

    function clearStatus() {
      statusLineEl.classList.remove("error");
      statusLineEl.textContent = "";
    }

    function showStatus(text, isError = false) {
      statusLineEl.textContent = text;
      statusLineEl.classList.toggle("error", isError);
    }

    function setLoading(isLoading) {
      verifyBtnEl.disabled = isLoading || currentState !== "input";
    }

    function hideSearchPreview() {
      searchPreviewEl.hidden = true;
      searchPreviewListEl.innerHTML = "";
    }

    function renderSearchPreview(items) {
      searchPreviewListEl.innerHTML = "";
      if (!Array.isArray(items) || items.length === 0) {
        hideSearchPreview();
        return;
      }

      items.forEach((item) => {
        const li = document.createElement("li");
        li.className = "search-preview-item";

        const link = document.createElement("a");
        link.className = "search-preview-link";
        link.rel = "noopener noreferrer";
        link.target = "_blank";
        link.href = String(item.url || "#");
        link.textContent = String(item.title || "근거 링크");
        li.appendChild(link);

        const meta = document.createElement("div");
        meta.className = "search-preview-meta";
        const source = String(item.source || "출처 미상");
        const snippet = String(item.snippet || "");
        meta.textContent = snippet ? source + " · " + snippet : source;
        li.appendChild(meta);

        searchPreviewListEl.appendChild(li);
      });

      searchPreviewEl.hidden = false;
    }

    async function requestSearchPreview(raw) {
      if (mode !== "url") {
        hideSearchPreview();
        return;
      }

      const query = String(raw || "").trim();
      if (query.length < 8) {
        hideSearchPreview();
        return;
      }

      if (searchAbortController) {
        searchAbortController.abort();
      }
      searchAbortController = new AbortController();

      const url = new URL(verifySearchUrl, window.location.origin);
      url.searchParams.set("q", query);
      url.searchParams.set("limit", "3");

      try {
        const response = await fetch(url.toString(), {
          method: "GET",
          headers: { "Accept": "application/json" },
          signal: searchAbortController.signal
        });
        if (!response.ok) {
          hideSearchPreview();
          return;
        }
        const payload = await response.json();
        const data = normalizeDataPayload(payload);
        const cards = extractEvidenceCards(data);
        renderSearchPreview(cards);
      } catch (error) {
        if (error && error.name === "AbortError") return;
        hideSearchPreview();
      }
    }

    function scheduleSearchPreview() {
      if (searchDebounceTimer) {
        window.clearTimeout(searchDebounceTimer);
      }
      searchDebounceTimer = window.setTimeout(() => {
        requestSearchPreview(inputEl.value);
      }, 260);
    }

    function setLoadingStep(step) {
      const safeStep = Math.max(0, Math.min(step, 2));
      loadingStep = safeStep;
      const frame = loadingFrames[safeStep];
      loadingHeadlineEl.textContent = frame.headline;
      loadingSubtextEl.textContent = frame.subtext;

      loadingStepEls.forEach((el, idx) => {
        el.classList.toggle("active", idx === safeStep);
      });
    }

    function startLoadingAnimation() {
      stopLoadingAnimation();
      setLoadingStep(0);
      loadingTimer = window.setInterval(() => {
        setLoadingStep((loadingStep + 1) % loadingFrames.length);
      }, 1000);
    }

    function stopLoadingAnimation() {
      if (!loadingTimer) return;
      window.clearInterval(loadingTimer);
      loadingTimer = null;
    }

    function normalizeDataPayload(payload) {
      if (payload && typeof payload === "object" && payload.data && typeof payload.data === "object") {
        return payload.data;
      }
      return payload || {};
    }

    function extractEvidenceCards(payload) {
      if (!payload || typeof payload !== "object") return [];
      if (Array.isArray(payload.evidence_cards)) return payload.evidence_cards;
      if (Array.isArray(payload.evidenceCards)) return payload.evidenceCards;
      return [];
    }

    function toNumber(value, fallback = 0) {
      const candidate = Number(value);
      if (!Number.isFinite(candidate)) return fallback;
      return candidate;
    }

    function renderResult(payload) {
      const verdictRaw = String(payload.verdict || "unverified").toLowerCase();
      const verdictKey = Object.prototype.hasOwnProperty.call(verdictView, verdictRaw)
        ? verdictRaw
        : "unverified";

      const view = verdictView[verdictKey];
      resultPillEl.className = "result-pill " + view.tone;
      resultPillEl.textContent = view.label;

      resultHeadlineEl.textContent = String(payload.headline || "검증 결과");
      resultReasonEl.textContent = String(payload.reason || "근거를 바탕으로 결과를 정리했어요.");

      let confidence = toNumber(payload.confidence, 0);
      if (confidence > 1) {
        confidence = confidence / 100;
      }
      confidence = Math.max(0, Math.min(confidence, 1));

      const percent = Math.round(confidence * 100);
      confidencePercentEl.textContent = percent + "%";
      confidenceFillEl.style.width = percent + "%";

      const cards = extractEvidenceCards(payload);
      evidenceCountEl.textContent = String(cards.length);
      evidenceListEl.innerHTML = "";

      if (cards.length === 0) {
        const empty = document.createElement("div");
        empty.className = "evidence-item";
        empty.textContent = "표시할 근거가 아직 없습니다.";
        evidenceListEl.appendChild(empty);
        return;
      }

      cards.forEach((card) => {
        const item = document.createElement("article");
        item.className = "evidence-item";

        const link = document.createElement("a");
        link.className = "evidence-link";
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.href = String(card.url || "#");
        link.textContent = String(card.title || "관련 근거");
        item.appendChild(link);

        const meta = document.createElement("div");
        meta.className = "evidence-meta";
        const source = String(card.source || "출처 미상");
        const publishedAt = String(card.published_at || card.publishedAt || "");
        meta.textContent = publishedAt ? source + " · " + publishedAt : source;
        item.appendChild(meta);

        const snippet = document.createElement("div");
        snippet.className = "evidence-snippet";
        snippet.textContent = String(card.snippet || "");
        item.appendChild(snippet);

        evidenceListEl.appendChild(item);
      });
    }

    async function callAnalyzeApi(raw) {
      if (analyzeAbortController) {
        analyzeAbortController.abort();
      }
      analyzeAbortController = new AbortController();

      const url = new URL(verifyAnalyzeUrl, window.location.origin);
      const response = await fetch(url.toString(), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        body: JSON.stringify({ input: raw, mode }),
        signal: analyzeAbortController.signal
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = (payload && payload.detail) ? String(payload.detail) : "검증 요청이 실패했습니다.";
        throw new Error(detail);
      }
      return normalizeDataPayload(payload);
    }

    async function startVerify() {
      const raw = inputEl.value.trim();
      if (!raw) {
        showStatus("검증할 내용을 입력해 주세요.", true);
        return;
      }

      clearStatus();
      setState("loading");
      setLoading(true);
      startLoadingAnimation();

      try {
        const result = await callAnalyzeApi(raw);
        stopLoadingAnimation();
        setLoadingStep(2);
        renderResult(result);
        setState("result");
      } catch (error) {
        if (!(error && error.name === "AbortError")) {
          const message = (error && error.message) ? error.message : "검증 중 오류가 발생했습니다.";
          showStatus(message, true);
        }
        setState("input");
      } finally {
        stopLoadingAnimation();
        setLoading(false);
      }
    }

    function cancelLoading() {
      if (analyzeAbortController) {
        analyzeAbortController.abort();
      }
      stopLoadingAnimation();
      setState("input");
      setLoading(false);
      showStatus("검증을 취소했어요.");
    }

    function goBackToChat() {
      const url = new URL(returnChatUrl, window.location.origin);
      if (!url.searchParams.get("issueId")) {
        url.searchParams.set("issueId", issueId);
      }
      window.location.assign(url.toString());
    }

    modeUrlEl.onclick = () => setMode("url");
    modeTextEl.onclick = () => setMode("text");
    verifyBtnEl.onclick = startVerify;
    cancelLoadingBtnEl.onclick = cancelLoading;
    retryBtnEl.onclick = () => {
      setState("input");
      clearStatus();
      setLoading(false);
    };
    backBtnEl.onclick = goBackToChat;

    inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) startVerify();
    });

    inputEl.addEventListener("input", () => {
      clearStatus();
      if (mode === "url") {
        scheduleSearchPreview();
      }
    });

    setMode("url");
    setState("input");
    setLoading(false);
  </script>
</body>
</html>"""

    html = (
        html.replace("__ISSUE_ID__", safe_issue_id)
        .replace("__ISSUE_TITLE__", issue_title)
        .replace("__ISSUE_SUMMARY__", issue_summary)
        .replace("__ISSUE_CATEGORY__", issue_category)
        .replace("__RETURN_CHAT_URL__", safe_return_chat_url)
        .replace("__VERIFY_ANALYZE_URL__", safe_verify_analyze_url)
        .replace("__VERIFY_SEARCH_URL__", safe_verify_search_url)
    )
    return HTMLResponse(content=html)
