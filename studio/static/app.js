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

function renderPanes(panes) {
  const container = document.getElementById("panes");
  container.innerHTML = "";
  for (const [idx, pane] of Object.entries(panes)) {
    const card = document.createElement("div");
    card.className = "pane-card" + (pane.stuck ? " stuck" : "");
    card.innerHTML = `
      <strong>${pane.name}</strong> (pane ${idx}) — ${pane.stuck ? "STUCK" : "정상"}<br>
      <code>${(pane.last_line || "").slice(0, 80)}</code><br>
      <button data-action="check" data-idx="${idx}">지금 확인</button>
      <button data-action="wake" data-idx="${idx}">깨우기</button>
      <button data-action="restart" data-idx="${idx}">역할 재주입</button>
      <button data-action="compact" data-idx="${idx}">compact</button>
    `;
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
