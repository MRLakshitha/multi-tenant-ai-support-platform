const API = "/api/v1";
let token = "";
let user = null;
let tenantId = "";
let conversationId = "";
let awaitingInput = "";
let selectedTicket = "";

const $ = id => document.getElementById(id);
const headers = () => ({
  "Content-Type": "application/json",
  ...(token ? { Authorization: `Bearer ${token}` } : {}),
  ...(tenantId ? { "X-Tenant-ID": tenantId } : {})
});

async function api(path, options = {}) {
  const response = await fetch(API + path, {
    ...options,
    headers: { ...headers(), ...(options.headers || {}) }
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}

function showError(id, error) { $(id).textContent = error.message || String(error); }
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  }[c]));
}

async function loadTenants() {
  const tenants = await api("/tenants");
  $("tenantSelect").innerHTML = tenants.map(t =>
    `<option value="${escapeHtml(t.id)}">${escapeHtml(t.name)}</option>`
  ).join("");
  tenantId = $("tenantSelect").value;
  updateChatTitle();
}
function updateChatTitle() {
  const option = $("tenantSelect").selectedOptions[0];
  $("chatTitle").textContent = option?.textContent
    ? `${option.textContent} Support Assistant` : "Support Assistant";
}

$("tenantSelect").addEventListener("change", () => {
  tenantId = $("tenantSelect").value;
  conversationId = "";
  awaitingInput = "";
  $("chatMessages").innerHTML = '<div class="empty">Start a new conversation.</div>';
  updateChatTitle();
});

function addMessage(content, role = "bot", options = []) {
  const wrap = document.createElement("div");
  const msg = document.createElement("div");
  msg.className = `message ${role}`;
  msg.textContent = content || "Please continue.";
  wrap.appendChild(msg);

  if (Array.isArray(options) && options.length) {
    const buttons = document.createElement("div");
    buttons.className = "message-options";
    options.forEach(option => {
      const btn = document.createElement("button");
      btn.textContent = option.label || option.id;
      btn.onclick = () => chooseOption(option.id);
      buttons.appendChild(btn);
    });
    wrap.appendChild(buttons);
  }
  $("chatMessages").appendChild(wrap);
  $("chatMessages").scrollTop = $("chatMessages").scrollHeight;
}

function showChatResult(data) {
  if (!data) return;
  if (data.awaiting_input) awaitingInput = data.awaiting_input;
  if (data.metadata?.field) awaitingInput = data.metadata.field;

  let content = data.message || data.response || data.reply ||
    data.content || data.assistant_message || data.detail;

  if (!content && Array.isArray(data.messages)) {
    data.messages.forEach(m => addMessage(m.content, m.role === "USER" ? "user" : "bot", m.options));
  } else if (content) {
    const options = data.options || data.messages?.[data.messages.length - 1]?.options || [];
    addMessage(typeof content === "string" ? content : JSON.stringify(content), "bot", options);
  } else {
    addMessage(JSON.stringify(data, null, 2));
  }
  if (data.ticket_id) addMessage(`Support ticket created: ${data.ticket_id}`);
}

async function startChat() {
  if (!tenantId) throw new Error("Please select an organization.");
  $("chatMessages").innerHTML = "";
  awaitingInput = "";
  const data = await api("/chat/start", {
    method: "POST",
    body: JSON.stringify({ customer_id: "web-guest", customer_name: "Web Customer" })
  });
  conversationId = data.conversation_id;
  if (!conversationId) throw new Error("The API did not return a conversation ID.");
  addMessage(data.message || data.welcome_message || "Welcome! How can we help you today?");
  const options = data.options || data.messages?.[data.messages.length - 1]?.options || [];
  if (options.length) {
    const wrap = document.createElement("div");
    wrap.className = "message-options";
    options.forEach(o => {
      const b = document.createElement("button");
      b.textContent = o.label || o.id;
      b.onclick = () => chooseOption(o.id);
      wrap.appendChild(b);
    });
    $("chatMessages").appendChild(wrap);
  }
}

async function chooseOption(categoryId) {
  try {
    addMessage(categoryId, "user");
    const data = await api("/chat/select-option", {
      method: "POST",
      body: JSON.stringify({ conversation_id: conversationId, category_id: categoryId })
    });
    showChatResult(data);
  } catch (e) { showError("chatError", e); }
}

$("newChatBtn").onclick = async () => {
  try { await startChat(); } catch (e) { showError("chatError", e); }
};

$("chatForm").onsubmit = async e => {
  e.preventDefault();
  const message = $("chatInput").value.trim();
  if (!message) return;
  $("chatInput").value = "";
  try {
    if (!conversationId) await startChat();
    addMessage(message, "user");
    let data;
    if (awaitingInput === "order_id") {
      data = await api("/chat/order-input", {
        method: "POST",
        body: JSON.stringify({ conversation_id: conversationId, input_text: message })
      });
      awaitingInput = "";
    } else {
      data = await api("/chat/message", {
        method: "POST",
        body: JSON.stringify({ conversation_id: conversationId, message })
      });
    }
    showChatResult(data);
  } catch (e) { showError("chatError", e); }
};

$("loginForm").onsubmit = async e => {
  e.preventDefault();
  $("loginError").textContent = "";
  try {
    const data = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: $("email").value, password: $("password").value })
    });
    token = data.access_token;
    user = data;
    if (data.tenant_id) {
      tenantId = data.tenant_id;
      $("tenantSelect").value = tenantId;
      $("tenantSelect").disabled = true;
    } else {
      $("tenantSelect").disabled = false;
    }
    $("loginPanel").classList.add("hidden");
    $("userLabel").textContent = `${data.full_name} · ${data.role}`;
    $("logoutBtn").classList.remove("hidden");
    await loadTickets();
    await loadAnalytics();
  } catch (e) { showError("loginError", e); }
};

function logout() {
  token = ""; user = null; selectedTicket = "";
  $("loginPanel").classList.remove("hidden");
  $("userLabel").textContent = "Customer Portal";
  $("logoutBtn").classList.add("hidden");
  $("tenantSelect").disabled = false;
  $("ticketList").innerHTML = '<div class="empty">Sign in to view tickets.</div>';
  $("ticketDetails").innerHTML = '<div class="empty">Sign in to view ticket details.</div>';
  $("metricCards").innerHTML = '<div class="empty">Sign in to load analytics.</div>';
}

async function loadTickets() {
  if (!token) return;
  $("ticketList").innerHTML = '<div class="empty">Loading tickets...</div>';
  try {
    const data = await api("/tickets");
    const tickets = Array.isArray(data) ? data : data.tickets || [];
    if (!tickets.length) {
      $("ticketList").innerHTML = '<div class="empty">No tickets found for this organization.</div>';
      return;
    }
    $("ticketList").innerHTML = "";
    tickets.forEach(t => {
      const b = document.createElement("button");
      b.className = "ticket-item";
      b.innerHTML = `<strong>${escapeHtml(t.id || t.ticket_id)}</strong><small>${escapeHtml(t.issue_category || "Support request")} · ${escapeHtml(t.status || "")}</small>`;
      b.onclick = () => {
        document.querySelectorAll(".ticket-item").forEach(x => x.classList.remove("selected"));
        b.classList.add("selected");
        openTicket(t.id || t.ticket_id);
      };
      $("ticketList").appendChild(b);
    });
  } catch (e) { $("ticketList").innerHTML = `<p class="error">${escapeHtml(e.message)}</p>`; }
}

async function openTicket(id) {
  selectedTicket = id;
  $("ticketDetails").innerHTML = '<div class="empty">Loading ticket...</div>';
  try {
    const result = await api(`/tickets/${encodeURIComponent(id)}`);
    const t = result.ticket || result;
    $("ticketDetails").innerHTML = `
      <h3>${escapeHtml(t.id)}</h3>
      <div class="detail-grid">
        <div class="detail"><small>Customer</small>${escapeHtml(t.customer_name)}</div>
        <div class="detail"><small>Priority</small>${escapeHtml(t.priority)}</div>
        <div class="detail"><small>Status</small>${escapeHtml(t.status)}</div>
        <div class="detail"><small>Assigned agent</small>${escapeHtml(t.assigned_agent_name)}</div>
        <div class="detail"><small>Issue</small>${escapeHtml(t.issue_category)}</div>
        <div class="detail"><small>Tenant</small>${escapeHtml(t.tenant_id)}</div>
      </div>
      <p>${escapeHtml(t.ai_summary || "")}</p>
      <h4>Send agent reply</h4>
      <textarea id="replyText" placeholder="Write a reply to the customer..."></textarea>
      <div class="ticket-actions">
        <button class="primary" onclick="sendReply()">Send reply</button>
        <button class="secondary" onclick="changeStatus('IN_PROGRESS')">In progress</button>
        <button class="secondary" onclick="changeStatus('RESOLVED')">Resolve ticket</button>
      </div>
      <p id="ticketError" class="error"></p>
      <h4>Conversation messages</h4>
      <div>${(result.messages || []).slice(-5).map(m =>
        `<div class="detail"><small>${escapeHtml(m.sender || m.role)}</small>${escapeHtml(m.content)}</div>`
      ).join("") || "No messages"}</div>
    `;
  } catch (e) { $("ticketDetails").innerHTML = `<p class="error">${escapeHtml(e.message)}</p>`; }
}

async function sendReply() {
  const content = $("replyText")?.value.trim();
  if (!content) return;
  try {
    await api(`/tickets/${encodeURIComponent(selectedTicket)}/message`, {
      method: "POST", body: JSON.stringify({ content })
    });
    await openTicket(selectedTicket);
  } catch (e) { showError("ticketError", e); }
}

async function changeStatus(status) {
  try {
    await api(`/tickets/${encodeURIComponent(selectedTicket)}/status`, {
      method: "POST",
      body: JSON.stringify({ status, resolution_notes: status === "RESOLVED" ? "Resolved through support dashboard." : null })
    });
    await loadTickets();
    await openTicket(selectedTicket);
  } catch (e) { showError("ticketError", e); }
}

async function loadAnalytics() {
  if (!token) return;
  try {
    const suffix = user?.role === "SUPER_ADMIN" && tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}&days=30` : "?days=30";
    const data = await api("/analytics/dashboard" + suffix);
    const metrics = [
      ["Conversations", data.total_conversations],
      ["L1 Resolutions", data.l1_resolutions],
      ["L3 Escalations", data.l3_escalations],
      ["Open Tickets", data.open_tickets],
      ["Pending Tickets", data.pending_tickets],
      ["Resolved Tickets", data.resolved_tickets],
      ["Resolution Rate", `${data.resolution_rate_percent ?? 0}%`],
      ["Average CSAT", data.avg_csat ?? "—"]
    ];
    $("metricCards").innerHTML = metrics.map(([label, value]) =>
      `<div class="metric"><small>${escapeHtml(label)}</small><strong>${escapeHtml(value ?? 0)}</strong></div>`
    ).join("");
    $("analyticsExtra").textContent = `Reporting period: ${data.timeframe_days || 30} days`;
  } catch (e) { $("metricCards").innerHTML = `<p class="error">${escapeHtml(e.message)}</p>`; }
}

document.querySelectorAll(".tab").forEach(btn => btn.onclick = () => {
  document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  document.querySelectorAll(".page").forEach(p => p.classList.add("hidden"));
  $(`${btn.dataset.page}Page`).classList.remove("hidden");
  if (btn.dataset.page === "tickets") loadTickets();
  if (btn.dataset.page === "analytics") loadAnalytics();
});
$("refreshTickets").onclick = loadTickets;
$("refreshAnalytics").onclick = loadAnalytics;

(async function init() {
  try {
    await loadTenants();
    $("chatMessages").innerHTML = '<div class="empty">Click New conversation to begin.</div>';
  } catch (e) {
    $("chatMessages").innerHTML = `<div class="error">${escapeHtml(e.message)}. Check that the backend is running.</div>`;
  }
})();
// '@ | Set-Content .\static\script.js -Encoding UTF8

