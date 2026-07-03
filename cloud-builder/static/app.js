mermaid.initialize({ startOnLoad: false, theme: "default" });

const STEPS = [
  {
    id: "provider", title: "클라우드 제공자를 선택하세요",
    type: "single",
    options: [{ value: "aws", label: "AWS" }, { value: "azure", label: "Azure" }],
  },
  {
    id: "app_type", title: "애플리케이션 유형을 선택하세요",
    type: "single",
    options: [
      { value: "web", label: "웹앱" }, { value: "api", label: "API 서버" },
      { value: "batch", label: "배치" }, { value: "data_pipeline", label: "데이터 파이프라인" },
    ],
  },
  {
    id: "components", title: "사용할 컴포넌트를 선택하세요 (복수 선택 가능)",
    type: "multi",
    options: [
      { value: "db", label: "데이터베이스" }, { value: "cache", label: "캐시" },
      { value: "queue", label: "메시지 큐" }, { value: "cdn", label: "CDN" },
      { value: "storage", label: "스토리지" },
    ],
  },
  { id: "scale", title: "규모와 요구사항을 설정하세요", type: "scale" },
  { id: "notes", title: "추가 요구사항이 있으면 입력하세요 (선택)", type: "text" },
];

let state = {
  provider: null, app_type: null, components: [],
  scale: { traffic: "medium", ha: false, multi_region: false },
  notes: "",
};
let currentStep = 0;

function renderDots() {
  document.getElementById("step-dots").innerHTML = STEPS.map((_, i) =>
    `<div class="step-dot ${i < currentStep ? "done" : i === currentStep ? "active" : ""}"></div>`
  ).join("");
}

function renderStep() {
  renderDots();
  const step = STEPS[currentStep];
  const c = document.getElementById("step-container");

  if (step.type === "single") {
    c.innerHTML = `<h2>${step.title}</h2><div class="options">${
      step.options.map(o =>
        `<button class="opt-btn${state[step.id] === o.value ? " selected" : ""}" data-val="${o.value}">${o.label}</button>`
      ).join("")
    }</div><div class="nav">
      <button class="btn btn-secondary" id="btn-back" ${currentStep === 0 ? "disabled" : ""}>이전</button>
      <button class="btn btn-primary" id="btn-next" ${!state[step.id] ? "disabled" : ""}>다음</button>
    </div>`;
    c.querySelectorAll(".opt-btn").forEach(b => b.addEventListener("click", () => {
      state[step.id] = b.dataset.val;
      renderStep();
    }));

  } else if (step.type === "multi") {
    c.innerHTML = `<h2>${step.title}</h2><div class="check-group">${
      step.options.map(o =>
        `<label class="check-item"><input type="checkbox" value="${o.value}" ${state.components.includes(o.value) ? "checked" : ""}> ${o.label}</label>`
      ).join("")
    }</div><div class="nav">
      <button class="btn btn-secondary" id="btn-back">이전</button>
      <button class="btn btn-primary" id="btn-next">다음</button>
    </div>`;
    c.querySelectorAll("input[type=checkbox]").forEach(cb =>
      cb.addEventListener("change", () => {
        state.components = [...c.querySelectorAll("input:checked")].map(x => x.value);
      })
    );

  } else if (step.type === "scale") {
    const tv = { low: "낮음", medium: "보통", high: "높음" };
    const tIdx = ["low", "medium", "high"].indexOf(state.scale.traffic);
    c.innerHTML = `<h2>${step.title}</h2>
    <div class="range-row">
      <label>예상 트래픽</label>
      <input type="range" min="0" max="2" value="${tIdx}" id="traffic-slider">
      <span class="range-val" id="traffic-val">${tv[state.scale.traffic]}</span>
    </div>
    <div class="check-group">
      <label class="check-item"><input type="checkbox" id="ha-check" ${state.scale.ha ? "checked" : ""}> 고가용성(HA) 필요</label>
      <label class="check-item"><input type="checkbox" id="mr-check" ${state.scale.multi_region ? "checked" : ""}> 멀티 리전</label>
    </div>
    <div class="nav">
      <button class="btn btn-secondary" id="btn-back">이전</button>
      <button class="btn btn-primary" id="btn-next">다음</button>
    </div>`;
    const levels = ["low", "medium", "high"];
    c.querySelector("#traffic-slider").addEventListener("input", e => {
      state.scale.traffic = levels[+e.target.value];
      c.querySelector("#traffic-val").textContent = tv[state.scale.traffic];
    });
    c.querySelector("#ha-check").addEventListener("change", e => state.scale.ha = e.target.checked);
    c.querySelector("#mr-check").addEventListener("change", e => state.scale.multi_region = e.target.checked);

  } else if (step.type === "text") {
    c.innerHTML = `<h2>${step.title}</h2>
    <textarea placeholder="예: 한국어 지원 필요, 특정 리전 고정 등">${state.notes}</textarea>
    <div class="nav">
      <button class="btn btn-secondary" id="btn-back">이전</button>
      <button class="btn btn-primary" id="btn-generate">아키텍처 생성</button>
    </div>`;
    c.querySelector("textarea").addEventListener("input", e => state.notes = e.target.value);
    c.querySelector("#btn-generate").addEventListener("click", generate);
  }

  const backBtn = c.querySelector("#btn-back");
  if (backBtn) backBtn.addEventListener("click", () => { currentStep--; renderStep(); });
  const nextBtn = c.querySelector("#btn-next");
  if (nextBtn) nextBtn.addEventListener("click", () => { currentStep++; renderStep(); });
}

async function generate() {
  document.getElementById("wizard-section").classList.add("hidden");
  document.getElementById("loading").classList.remove("hidden");
  document.getElementById("error-message").classList.add("hidden");
  try {
    const resp = await fetch("/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state),
    });
    if (!resp.ok) {
      throw new Error(`서버 오류: ${resp.status}`);
    }
    const data = await resp.json();
    document.getElementById("loading").classList.add("hidden");
    renderResult(data);
  } catch (err) {
    document.getElementById("loading").classList.add("hidden");
    document.getElementById("wizard-section").classList.remove("hidden");
    const errEl = document.getElementById("error-message");
    errEl.textContent = err.message || "아키텍처 생성 중 오류가 발생했습니다.";
    errEl.classList.remove("hidden");
  }
}

function renderResult(data) {
  const sec = document.getElementById("result-section");
  sec.classList.remove("hidden");

  document.getElementById("tab-summary").innerHTML =
    `<p style="line-height:1.7">${data.summary}</p>`;

  const mc = document.getElementById("mermaid-container");
  mc.innerHTML = `<div class="mermaid">${data.diagram}</div>`;

  const terraformEntries = Object.entries(data.terraform);
  document.getElementById("tf-files").innerHTML = terraformEntries.map(([name, code], i) =>
    `<h3 style="margin:16px 0 8px">${name}</h3>
     <button class="copy-btn" data-index="${i}">복사</button>
     <pre><code>${code.replace(/</g, "&lt;")}</code></pre>`
  ).join("");
  document.querySelectorAll("#tf-files .copy-btn").forEach((btn, i) => {
    btn.addEventListener("click", () => navigator.clipboard.writeText(terraformEntries[i][1]));
  });

  document.querySelectorAll(".tab").forEach(t => t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(x => x.classList.remove("active"));
    t.classList.add("active");
    document.getElementById("tab-" + t.dataset.tab).classList.add("active");
    if (t.dataset.tab === "diagram" && !mc.querySelector("svg")) {
      const source = mc.querySelector(".mermaid").textContent.trim();
      mermaid.render("mermaid-graph", source).then(({ svg }) => {
        mc.innerHTML = svg;
      }).catch(err => {
        mc.innerHTML = "<p style=\"color:#c00;padding:16px\">다이어그램 렌더링 실패: " + err.message + "</p>";
      });
    }
  }));

  document.getElementById("dl-btn").addEventListener("click", () => {
    const params = new URLSearchParams({
      provider: state.provider, app_type: state.app_type,
      traffic: state.scale.traffic, ha: state.scale.ha, multi_region: state.scale.multi_region,
    });
    state.components.forEach(c => params.append("components", c));
    window.location.href = `/download/terraform?${params}`;
  });
}

renderStep();
