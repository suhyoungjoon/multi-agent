function getToken() {
  return localStorage.getItem("studioToken") || "";
}

document.getElementById("save-token").addEventListener("click", () => {
  const value = document.getElementById("token-input").value;
  localStorage.setItem("studioToken", value);
});

function showError(message) {
  const banner = document.getElementById("error-banner");
  banner.textContent = message;
  banner.style.display = "block";
}

function clearError() {
  const banner = document.getElementById("error-banner");
  banner.style.display = "none";
}

async function apiRequest(path, options) {
  let res;
  try {
    res = await fetch(path, options);
  } catch (err) {
    return { ok: false, status: null, error: err.message };
  }

  if (!res.ok) {
    return { ok: false, status: res.status, error: `${res.status} ${res.statusText}` };
  }

  try {
    const data = await res.json();
    return { ok: true, status: res.status, data };
  } catch (err) {
    return { ok: false, status: res.status, error: `invalid JSON response: ${err.message}` };
  }
}

async function apiGet(path) {
  return apiRequest(path, { headers: { "X-Studio-Token": getToken() } });
}

async function apiPost(path, body) {
  return apiRequest(path, {
    method: "POST",
    headers: { "X-Studio-Token": getToken(), "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
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
  const result = await apiPost(`/api/pane/${button.dataset.idx}/${button.dataset.action}`);
  if (!result.ok) {
    showError(`${button.dataset.action} 실패 (pane ${button.dataset.idx}): ${result.error}`);
  } else {
    clearError();
  }
  refreshStatus();
});

document.getElementById("stuck-toggle").addEventListener("change", async (event) => {
  const result = await apiPost("/api/watchdog/settings", { stuck_check_enabled: event.target.checked });
  if (!result.ok) {
    showError(`정체 감지 토글 실패: ${result.error}`);
  } else {
    clearError();
  }
});

async function refreshStatus() {
  const statusResult = await apiGet("/api/status");
  if (!statusResult.ok) {
    showError(`상태 조회 실패: ${statusResult.error}`);
    return;
  }
  clearError();
  renderPanes(statusResult.data.panes || {});

  const settingsResult = await apiGet("/api/watchdog/settings");
  if (settingsResult.ok) {
    document.getElementById("stuck-toggle").checked = settingsResult.data.stuck_check_enabled;
  }
}

async function refreshHotCache() {
  const hotResult = await apiGet("/api/wiki/hot");
  const el = document.getElementById("hot-cache");
  if (!hotResult.ok) {
    el.textContent = `(hot cache 조회 실패: ${hotResult.error})`;
    return;
  }
  el.textContent = hotResult.data.content || "(hot cache 없음)";
}

refreshStatus();
refreshHotCache();
setInterval(refreshStatus, 2500);
setInterval(refreshHotCache, 10000);
