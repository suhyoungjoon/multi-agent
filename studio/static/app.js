function getToken() {
  return localStorage.getItem("studioToken") || "";
}

document.getElementById("save-token").addEventListener("click", () => {
  const value = document.getElementById("token-input").value;
  localStorage.setItem("studioToken", value);
});

async function apiGet(path) {
  const res = await fetch(path, { headers: { "X-Studio-Token": getToken() } });
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "X-Studio-Token": getToken(), "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.json();
}

function makeActionButton(action, idx, label) {
  const button = document.createElement("button");
  button.dataset.action = action;
  button.dataset.idx = idx;
  button.textContent = label;
  return button;
}

function renderPanes(panes) {
  const container = document.getElementById("panes");
  container.innerHTML = "";
  for (const [idx, pane] of Object.entries(panes)) {
    const card = document.createElement("div");
    card.className = "pane-card" + (pane.stuck ? " stuck" : "");

    const header = document.createElement("strong");
    header.textContent = pane.name;
    card.appendChild(header);
    card.appendChild(document.createTextNode(` (pane ${idx}) — ${pane.stuck ? "STUCK" : "정상"}`));
    card.appendChild(document.createElement("br"));

    const code = document.createElement("code");
    code.textContent = (pane.last_line || "").slice(0, 80);
    card.appendChild(code);
    card.appendChild(document.createElement("br"));

    card.appendChild(makeActionButton("check", idx, "지금 확인"));
    card.appendChild(makeActionButton("wake", idx, "깨우기"));
    card.appendChild(makeActionButton("restart", idx, "역할 재주입"));
    card.appendChild(makeActionButton("compact", idx, "compact"));

    container.appendChild(card);
  }
}

document.getElementById("panes").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  await apiPost(`/api/pane/${button.dataset.idx}/${button.dataset.action}`);
  refreshStatus();
});

document.getElementById("stuck-toggle").addEventListener("change", async (event) => {
  await apiPost("/api/watchdog/settings", { stuck_check_enabled: event.target.checked });
});

async function refreshStatus() {
  const status = await apiGet("/api/status");
  renderPanes(status.panes || {});
  const settings = await apiGet("/api/watchdog/settings");
  document.getElementById("stuck-toggle").checked = settings.stuck_check_enabled;
}

async function refreshHotCache() {
  const hot = await apiGet("/api/wiki/hot");
  document.getElementById("hot-cache").textContent = hot.content || "(hot cache 없음)";
}

refreshStatus();
refreshHotCache();
setInterval(refreshStatus, 2500);
setInterval(refreshHotCache, 10000);
