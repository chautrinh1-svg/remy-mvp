/* ── Config ─────────────────────────────────────────── */
const API = "";

/* ── State ──────────────────────────────────────────── */
let analysisCtx  = null;  // last full analysis result (context cho follow-up)
let chatHistory  = [];    // [{role, content}] — lịch sử hội thoại

/* ── DOM ────────────────────────────────────────────── */
const chatBody  = document.getElementById("chatBody");
const msgList   = document.getElementById("msgList");
const welcome   = document.getElementById("welcome");
const chatForm  = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const sendBtn   = document.getElementById("sendBtn");
const newChatBtn = document.getElementById("newChatBtn");

/* ── Init ───────────────────────────────────────────── */
chatInput.addEventListener("input", () => {
  sendBtn.disabled = !chatInput.value.trim();
});

chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = chatInput.value.trim();
  if (text) handleSend(text);
});

newChatBtn.addEventListener("click", resetChat);

// Welcome chips
document.querySelectorAll(".w-chip").forEach((btn) => {
  btn.addEventListener("click", () => handleSend(btn.dataset.q));
});

/* ── Core send handler ──────────────────────────────── */
async function handleSend(text) {
  if (!text.trim()) return;

  hideWelcome();
  appendUserMsg(text);
  chatInput.value = "";
  sendBtn.disabled = true;

  const typingId = appendTyping();

  try {
    // ── /api/smart tự detect: địa điểm mới vs follow-up ──
    const response = await apiSmart(text, chatHistory, analysisCtx);
    removeTyping(typingId);

    if (response.type === "analysis") {
      appendAnalysisMsg(response.data);
      analysisCtx = response.data;
      chatHistory.push({ role: "user",      content: text });
      chatHistory.push({ role: "assistant", content: `Đã phân tích ${response.data.destination}: ${response.data.neutral_summary}` });
    } else {
      appendRemyMsg(response.reply);
      chatHistory.push({ role: "user",      content: text });
      chatHistory.push({ role: "assistant", content: response.reply });
    }
  } catch (err) {
    removeTyping(typingId);
    const msg = err.message.includes("429") || err.message.includes("rate_limit")
      ? "⏳ Remy đang nghỉ ngơi chút — đã dùng hết quota AI cho hôm nay. Thử lại sau khoảng 15 phút nhé!"
      : err.message.includes("Failed to fetch") || err.message.includes("NetworkError")
      ? "🔌 Không kết nối được server. Kiểm tra backend đang chạy tại localhost:5000."
      : `⚠️ ${err.message}`;
    appendRemyMsg(msg);
  }

  scrollBottom();
}

/* ── API calls ──────────────────────────────────────── */
async function apiSmart(message, history, context) {
  const res = await fetch(`${API}/api/smart`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history, context }),
  });
  const json = await res.json();
  if (!res.ok) throw new Error(json.error || `Error ${res.status}`);
  return json;
}

/* ── Message renderers ──────────────────────────────── */
function appendUserMsg(text) {
  const div = document.createElement("div");
  div.className = "msg user";
  div.innerHTML = `<div class="bubble user-bubble">${escHtml(text)}</div>`;
  msgList.appendChild(div);
}

function appendRemyMsg(text) {
  const div = document.createElement("div");
  div.className = "msg";
  div.innerHTML = `
    <div class="msg-avatar">🧳</div>
    <div class="bubble remy-bubble">${formatReply(text)}</div>
  `;
  msgList.appendChild(div);
}

function appendTyping() {
  const id = "typing-" + Date.now();
  const div = document.createElement("div");
  div.className = "msg";
  div.id = id;
  div.innerHTML = `
    <div class="msg-avatar">🧳</div>
    <div class="bubble remy-bubble typing-bubble">
      <span class="dot"></span><span class="dot"></span><span class="dot"></span>
    </div>
  `;
  msgList.appendChild(div);
  scrollBottom();
  return id;
}

function removeTyping(id) {
  document.getElementById(id)?.remove();
}

function appendAnalysisMsg(data) {
  const div = document.createElement("div");
  div.className = "msg";
  div.innerHTML = `
    <div class="msg-avatar">🧳</div>
    <div class="bubble remy-bubble analysis-bubble">
      ${buildAnalysisHTML(data)}
    </div>
  `;
  msgList.appendChild(div);

  // Wire up follow-up chip clicks
  div.querySelectorAll(".fup-chip").forEach((btn) => {
    btn.addEventListener("click", () => handleSend(btn.dataset.q));
  });
}

/* ── Analysis HTML builder ──────────────────────────── */
function buildAnalysisHTML(d) {
  const liked       = d.liked       || [];
  const complaints  = d.complaints  || [];
  const patterns    = d.truth_patterns || [];
  const bestFor     = d.traveler_fit?.best_for || [];
  const avoidIf     = d.traveler_fit?.avoid_if || [];
  const sources     = d.sources     || [];
  const followups   = d.follow_up_questions || [];

  /* Liked list */
  const likedHTML = liked.map((item) => `
    <li class="an-li">
      <div class="an-li-top">
        <span class="an-li-text">${escHtml(item.text)}</span>
        ${item.count ? `<span class="an-cnt cnt-green">${item.count}×</span>` : ""}
      </div>
      ${item.quote ? `<div class="an-quote">"${escHtml(item.quote)}"</div>` : ""}
    </li>`).join("");

  /* Complaints list */
  const compHTML = complaints.map((item) => `
    <li class="an-li">
      <div class="an-li-top">
        <span class="an-li-text">${escHtml(item.text)}</span>
        ${item.count ? `<span class="an-cnt cnt-amber">${item.count}×</span>` : ""}
      </div>
      ${item.quote ? `<div class="an-quote">"${escHtml(item.quote)}"</div>` : ""}
    </li>`).join("");

  /* Truth patterns */
  const truthHTML = patterns.map((p) => `
    <div class="truth-item">
      <div class="truth-name">💡 ${escHtml(p.pattern)}</div>
      <div class="truth-desc">${escHtml(p.insight)}</div>
    </div>`).join("");

  /* Traveler fit */
  const fitHTML = [
    ...bestFor.map((t) => `<span class="fit-tag fit-good">✓ ${escHtml(t)}</span>`),
    ...avoidIf.map((t) => `<span class="fit-tag fit-bad">✗ ${escHtml(t)}</span>`),
  ].join("");

  /* Sources */
  const srcHTML = sources.map((s) => `
    <a href="${escHtml(s.url)}" target="_blank" rel="noopener noreferrer" class="source-link">
      🔗 ${escHtml(s.domain)}
    </a>`).join("");

  /* Follow-up chips */
  const fupHTML = followups.map((q) => `
    <button class="fup-chip" data-q="${escHtml(q)}">${escHtml(q)}</button>`).join("");

  return `
    <!-- Header -->
    <div class="an-header">
      <span class="an-dest">📍 ${escHtml(d.destination || "")}</span>
      <span class="an-badge">${d.sources_analyzed || 0} nguồn phân tích</span>
    </div>

    <!-- Summary -->
    <div class="an-summary">${escHtml(d.neutral_summary || "")}</div>

    <!-- Liked + Complaints -->
    <div class="an-grid">
      <div class="an-col">
        <div class="an-col-title liked-title">✅ Mọi người thích</div>
        <ul class="an-list">${likedHTML || "<li class='an-li' style='color:var(--text-dim)'>Chưa có dữ liệu</li>"}</ul>
      </div>
      <div class="an-col">
        <div class="an-col-title warn-title">⚠️ Phàn nàn phổ biến</div>
        <ul class="an-list">${compHTML || "<li class='an-li' style='color:var(--text-dim)'>Chưa có dữ liệu</li>"}</ul>
      </div>
    </div>

    ${truthHTML ? `
    <div class="an-section">
      <div class="an-section-title">🔍 Sự thật ẩn giấu</div>
      <div class="truth-list">${truthHTML}</div>
    </div>` : ""}

    ${fitHTML ? `
    <div class="an-section">
      <div class="an-section-title">👥 Phù hợp với ai?</div>
      <div class="fit-tags">${fitHTML}</div>
    </div>` : ""}

    ${srcHTML ? `
    <div class="an-section">
      <div class="an-section-title">🔗 Nguồn tham khảo</div>
      <div class="sources-row">${srcHTML}</div>
    </div>` : ""}

    ${fupHTML ? `
    <div class="an-section">
      <div class="an-section-title">💬 Hỏi tiếp Remy</div>
      <div class="followup-chips">${fupHTML}</div>
    </div>` : ""}
  `;
}

/* ── Helpers ────────────────────────────────────────── */
function resetChat() {
  analysisCtx       = null;
  chatHistory       = [];
  msgList.innerHTML = "";
  welcome.style.display = "";
  chatInput.value   = "";
  sendBtn.disabled  = true;
  scrollBottom();
}

function hideWelcome() {
  welcome.style.display = "none";
}

function scrollBottom() {
  requestAnimationFrame(() => {
    chatBody.scrollTo({ top: chatBody.scrollHeight, behavior: "smooth" });
  });
}

function formatReply(text) {
  // Convert newlines to <br> for readability
  return escHtml(text).replace(/\n/g, "<br>");
}

function escHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
