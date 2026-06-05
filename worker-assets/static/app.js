// Personal Finance Advisor — vanilla front-end (HLD §8).
// Posts to /api/chat, renders the chat transcript, populates the three
// side cards, and streams plan_trace lines sequentially for a visible
// agentic trace. No frameworks, no build step.

const SESSION_ID = "web-session";

const chatEl   = document.getElementById("chat");
const formEl   = document.getElementById("chat-form");
const inputEl  = document.getElementById("msg");
const insEl    = document.getElementById("card-insights");
const recsEl   = document.getElementById("card-recs");
const alertsEl = document.getElementById("card-alerts");
const traceEl  = document.getElementById("trace");
const traceToggle = document.getElementById("trace-toggle");

function bubble(role, text) {
  const div = document.createElement("div");
  div.className = "bubble " + role;
  div.textContent = text;
  chatEl.appendChild(div);
  chatEl.scrollTop = chatEl.scrollHeight;
  return div;
}

function renderInsights(insights) {
  if (!insights) { insEl.className = "card-body muted"; insEl.textContent = "No insights yet."; return; }
  insEl.className = "card-body";
  const totals = insights.totals_by_category || {};
  const rows = Object.keys(totals).sort()
    .map(c => `<li><span>${c}</span><span>₹${totals[c].toLocaleString("en-IN")}</span></li>`)
    .join("");
  const anomalies = (insights.anomalies || [])
    .map(a => `<div class="anom">⚠ ${a.category}: ${a.note}</div>`).join("");
  insEl.innerHTML =
    `<p class="summary">${insights.summary_text || ""}</p>` +
    `<ul class="totals">${rows}</ul>${anomalies}`;
}

function renderRecs(recs) {
  if (!recs || !recs.length) { recsEl.className = "card-body muted"; recsEl.textContent = "No recommendations yet."; return; }
  recsEl.className = "card-body";
  recsEl.innerHTML = recs.map(r =>
    `<div class="rec"><strong>${r.category}</strong> — ${r.action}` +
    `<div class="save">Saves ~₹${r.est_monthly_saving.toLocaleString("en-IN")}/mo</div>` +
    `<div class="why">${r.rationale}</div></div>`).join("");
}

function renderAlerts(alerts) {
  if (!alerts || !alerts.length) { alertsEl.className = "card-body muted"; alertsEl.textContent = "No alerts."; return; }
  alertsEl.className = "card-body";
  alertsEl.innerHTML = alerts.map(a =>
    `<div class="alert sev-${a.severity}"><strong>${a.category}</strong>: ${a.message}</div>`).join("");
}

// Stream plan_trace lines in one at a time for a visible agentic trace.
function renderTrace(lines) {
  traceEl.innerHTML = "";
  (lines || []).forEach((line, i) => {
    setTimeout(() => {
      const li = document.createElement("li");
      li.textContent = line;
      li.className = "trace-line";
      traceEl.appendChild(li);
    }, i * 220);
  });
}

traceToggle.addEventListener("click", () => {
  const collapsed = traceEl.classList.toggle("collapsed");
  traceToggle.setAttribute("aria-expanded", String(!collapsed));
  traceToggle.textContent = collapsed ? "Agent trace ▸" : "Agent trace ▾";
});

async function send(message) {
  bubble("user", message);
  const pending = bubble("assistant pending", "…");
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: SESSION_ID }),
    });
    const data = await res.json();
    pending.className = "bubble assistant";
    pending.textContent = data.answer_text || "(no answer)";
    renderInsights(data.insights);
    renderRecs(data.recommendations);
    renderAlerts(data.alerts);
    renderTrace(data.plan_trace);
  } catch (err) {
    pending.className = "bubble assistant error";
    pending.textContent = "Request failed: " + err;
  }
}

formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const message = inputEl.value.trim();
  if (!message) return;
  inputEl.value = "";
  send(message);
});

// Greeting on load.
bubble("assistant", "Hi Aarav — ask me how to improve your savings, or about any spending category.");
