/* Meteor web chat — SSE-driven agent loop client. Simple dark theme. */

const chat = document.getElementById("chat");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const modelBadge = document.getElementById("model-badge");
const btnTools = document.getElementById("btn-tools");
const btnClear = document.getElementById("btn-clear");
const modeFast = document.getElementById("mode-fast");
const modeSmart = document.getElementById("mode-smart");

const SESSION_ID = `web-${Math.random().toString(36).slice(2, 10)}`;

// ── Danger confirm modal ───────────────────────────────────────────
const confirmOverlay = document.getElementById("confirm-overlay");
const confirmReason = document.getElementById("confirm-reason");
const confirmCmd = document.getElementById("confirm-cmd");
const confirmRun = document.getElementById("confirm-run");
const confirmCancel = document.getElementById("confirm-cancel");

function describeCall(p) {
  if (p.tool === "shell") return p.params?.command || "";
  const args = p.params ? JSON.stringify(p.params) : "";
  return `${p.tool}.${p.operation}(${args})`;
}

async function resolveConfirm(id, approved) {
  confirmOverlay.hidden = true;
  try {
    await fetch("/api/v1/agent/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, approved }),
    });
  } catch (e) {
    console.error("confirm failed", e);
  }
}

function showConfirm(payload) {
  confirmReason.textContent = `Meteor wants to ${payload.reason}. This can't be undone.`;
  confirmCmd.textContent = describeCall(payload);
  confirmOverlay.hidden = false;
  confirmRun.onclick = () => resolveConfirm(payload.id, true);
  confirmCancel.onclick = () => resolveConfirm(payload.id, false);
  confirmRun.focus();
}

// ── Model badge + mode toggle ──────────────────────────────────────
async function refreshModelBadge() {
  try {
    const res = await fetch("/api/v1/agent/model");
    const data = await res.json();
    // Meteor is the model. The underlying engine stays in the tooltip only.
    modelBadge.textContent = data.model || "Meteor";
    modelBadge.title = `engine=${data.engine || "?"} · backend=${data.backend} · ${data.role}`;
    if (data.role === "heavy") {
      modeSmart.classList.add("active");
      modeFast.classList.remove("active");
    } else {
      modeFast.classList.add("active");
      modeSmart.classList.remove("active");
    }
  } catch (e) {
    modelBadge.textContent = "offline";
  }
}

async function switchMode(role) {
  try {
    const res = await fetch("/api/v1/agent/model", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
    const data = await res.json();
    if (data.ok) await refreshModelBadge();
  } catch (e) {
    console.error(e);
  }
}
modeFast.addEventListener("click", () => switchMode("fast"));
modeSmart.addEventListener("click", () => switchMode("heavy"));

// ── DOM helpers ────────────────────────────────────────────────────
function clearWelcome() {
  const w = chat.querySelector(".welcome");
  if (w) w.remove();
}

function scrollBottom() {
  chat.scrollTop = chat.scrollHeight;
}

function addMessage(role, text) {
  clearWelcome();
  const msg = document.createElement("div");
  msg.className = `msg ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  msg.appendChild(bubble);
  chat.appendChild(msg);
  scrollBottom();
  return bubble;
}

function addTrace(tag, body, klass = "") {
  clearWelcome();
  const wrap = document.createElement("div");
  wrap.className = "trace";
  const card = document.createElement("div");
  card.className = `trace-card ${klass}`;
  const tagEl = document.createElement("div");
  tagEl.className = "tag";
  tagEl.textContent = tag;
  const bodyEl = document.createElement("div");
  bodyEl.className = "body";
  bodyEl.textContent = body;
  card.appendChild(tagEl);
  card.appendChild(bodyEl);
  wrap.appendChild(card);
  chat.appendChild(wrap);
  scrollBottom();
}

function renderMarkdown(bubble, text) {
  // Minimal render: fenced code blocks + inline code. Everything else is
  // plain text (already whitespace-preserved by CSS).
  const parts = text.split(/```([\s\S]*?)```/g);
  bubble.innerHTML = "";
  parts.forEach((part, i) => {
    if (i % 2 === 1) {
      const pre = document.createElement("pre");
      const code = document.createElement("code");
      const nl = part.indexOf("\n");
      code.textContent = nl >= 0 ? part.slice(nl + 1) : part;
      pre.appendChild(code);
      bubble.appendChild(pre);
    } else {
      const frag = document.createDocumentFragment();
      part.split(/(`[^`\n]+`)/g).forEach((seg) => {
        if (seg.startsWith("`") && seg.endsWith("`")) {
          const c = document.createElement("code");
          c.textContent = seg.slice(1, -1);
          frag.appendChild(c);
        } else {
          frag.appendChild(document.createTextNode(seg));
        }
      });
      bubble.appendChild(frag);
    }
  });
}

// ── Copy to clipboard ──────────────────────────────────────────────
function copyToClipboard(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
  } else {
    fallbackCopy(text);
  }
}

function fallbackCopy(text) {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.left = "-9999px";
  ta.style.top = "-9999px";
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  try { document.execCommand("copy"); } catch (_) {}
  document.body.removeChild(ta);
}

function attachCopyButton(container, text) {
  const tpl = document.getElementById("copy-btn-tpl");
  if (!tpl) return;
  const btn = tpl.content.firstElementChild.cloneNode(true);
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    copyToClipboard(text);
    btn.classList.add("copied");
    setTimeout(() => btn.classList.remove("copied"), 1200);
  });
  container.style.position = container.style.position || "relative";
  container.appendChild(btn);
  return btn;
}

function attachCopyToCodeBlocks(bubble) {
  bubble.querySelectorAll("pre").forEach((pre) => {
    if (pre.querySelector(".copy-btn")) return;
    const text = pre.textContent || "";
    attachCopyButton(pre, text);
  });
}

// ── SSE agent send ─────────────────────────────────────────────────
async function send() {
  const prompt = input.value.trim();
  if (!prompt) return;

  input.value = "";
  autoResize();
  sendBtn.disabled = true;

  addMessage("user", prompt);
  const assistantBubble = addMessage("assistant", "");
  assistantBubble.classList.add("streaming");

  let finalText = "";

  try {
    const res = await fetch("/api/v1/agent/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, session_id: SESSION_ID }),
    });

    if (!res.ok || !res.body) {
      throw new Error(`HTTP ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });

      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const evt = parseSSE(chunk);
        if (!evt) continue;
        handleEvent(evt, assistantBubble, (t) => { finalText = t; });
      }
    }
  } catch (err) {
    addTrace("error", err.message || String(err), "error");
  } finally {
    assistantBubble.classList.remove("streaming");
    if (finalText) {
      renderMarkdown(assistantBubble, finalText);
      attachCopyToCodeBlocks(assistantBubble);
      attachCopyButton(assistantBubble, finalText);
    }
    sendBtn.disabled = false;
    input.focus();
    scrollBottom();
  }
}

function parseSSE(chunk) {
  const lines = chunk.split("\n");
  let event = "message";
  const data = [];
  for (const line of lines) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trim());
  }
  if (!data.length) return null;
  try {
    return { event, payload: JSON.parse(data.join("\n")) };
  } catch {
    return { event, payload: { raw: data.join("\n") } };
  }
}

function handleEvent(evt, bubble, setFinal) {
  const { event, payload } = evt;
  switch (event) {
    // Streamed final answer — the agent loop emits these once it stops using
    // tools and starts writing the reply.
    case "token":
    case "final_token": {
      const t = payload.token || "";
      if (bubble.textContent === "…") bubble.textContent = "";
      bubble.textContent += t;
      setFinal(bubble.textContent);
      scrollBottom();
      break;
    }
    case "final_start":
      if (bubble.textContent === "…") bubble.textContent = "";
      break;
    case "confirm_required":
      // Serious, irreversible action — pause and ask before it runs.
      showConfirm(payload);
      break;
    case "thinking":
    case "tool_call":
    case "tool_result":
      // Inline & silent: Meteor uses tools invisibly and weaves the findings
      // into its final answer. We only surface a subtle "working…" hint while
      // it's still deciding / calling tools.
      if (event === "tool_call" && !bubble.textContent) {
        bubble.textContent = "…";
      }
      break;
    case "final":
    case "final_done": {
      const text = payload.text || payload.response_text || bubble.textContent;
      if (text) { setFinal(text); bubble.textContent = text; }
      break;
    }
    case "iteration_limit":
      if (bubble.textContent === "…") {
        bubble.textContent = "Meteor hit its tool-iteration limit without finishing. Try narrowing the request.";
      }
      break;
    case "error": {
      addTrace("error", payload.message || JSON.stringify(payload), "error");
      break;
    }
    case "done":
      break;
    default:
      break;
  }
}

// ── Composer wiring ────────────────────────────────────────────────
function autoResize() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 240) + "px";
}
input.addEventListener("input", autoResize);
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});
sendBtn.addEventListener("click", send);

btnClear.addEventListener("click", async () => {
  try {
    await fetch(`/api/v1/agent/clear?session_id=${encodeURIComponent(SESSION_ID)}`, {
      method: "POST",
    });
  } catch {}
  chat.innerHTML = "";
  const w = document.createElement("div");
  w.className = "welcome";
  w.innerHTML = `
    <div class="welcome-mark">☄</div>
    <div class="welcome-title">Meteor</div>
    <div class="welcome-sub">Local-first agentic AI · runs anything on your machine · shell, files, network, recon</div>`;
  chat.appendChild(w);
});

btnTools.addEventListener("click", async () => {
  try {
    const res = await fetch("/api/v1/agent/tools");
    const data = await res.json();
    const names = (data.tools || []).map((t) => t.name || t).join(", ");
    addTrace("tools", names || "(none registered)");
  } catch (e) {
    addTrace("error", String(e), "error");
  }
});

refreshModelBadge();
