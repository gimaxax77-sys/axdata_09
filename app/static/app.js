const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const FILES = "/files/";

let CATALOG = null;
let ENTITY = "character";

// 엔티티별 role 라벨 힌트
const ROLE_LABEL = {
  character: "직업 / 역할",
  monster: "종족 / 유형",
  npc: "직업 / 역할",
};
const ROLE_PH = {
  character: "예: 전사, 마법사, 해커…",
  monster: "예: 드래곤, 골렘, 언데드…",
  npc: "예: 상인, 대장장이, 정보상…",
};

// ── 초기 로드 ────────────────────────────────────────────
async function init() {
  await loadStatus();
  CATALOG = await (await fetch("/api/catalog")).json();
  renderEntityTabs();
  renderAssetPicker();
}

async function loadStatus() {
  try {
    const s = await (await fetch("/api/status")).json();
    const pills = [
      ["GPT", s.gpt, s.openai_model],
      ["Gemini", s.gemini, s.gemini_model],
    ];
    $("#status").innerHTML = pills.map(([n, m, model]) =>
      `<span class="pill ${m}" title="${model}"><span class="dot"></span>${n}: ${m === "live" ? "연결됨" : "데모"}</span>`
    ).join("");
  } catch (e) {}
}

// ── 엔티티 탭 ────────────────────────────────────────────
function renderEntityTabs() {
  const tabs = Object.entries(CATALOG.entity_types);
  $("#entity-tabs").innerHTML = tabs.map(([key, label]) =>
    `<button type="button" class="etab ${key === ENTITY ? "on" : ""}" data-e="${key}">${label}</button>`
  ).join("");
  $$(".etab").forEach((b) => b.addEventListener("click", () => {
    ENTITY = b.dataset.e;
    $$(".etab").forEach((x) => x.classList.toggle("on", x.dataset.e === ENTITY));
    $("#role-label").childNodes[0].nodeValue = ROLE_LABEL[ENTITY] + " ";
    $('input[name="role"]').placeholder = ROLE_PH[ENTITY];
    renderAssetPicker();
  }));
}

// ── 에셋 선택기 (카테고리별) ─────────────────────────────
function renderAssetPicker() {
  const cats = CATALOG.categories;
  const grouped = {};
  CATALOG.assets
    .filter((a) => a.entities.includes(ENTITY))
    .forEach((a) => { (grouped[a.category] ||= []).push(a); });

  $("#asset-picker").innerHTML = Object.keys(cats)
    .filter((c) => grouped[c])
    .map((c) => `
      <div class="asset-group">
        <div class="group-title">${cats[c]}</div>
        <div class="group-items">
          ${grouped[c].map((a) => `
            <label class="asset-chip" title="${a.desc}">
              <input type="checkbox" name="asset" value="${a.key}" ${a.default ? "checked" : ""}/>
              <span>${a.label}${a.variants.length ? `<i>×${a.variants.length}</i>` : ""}</span>
            </label>`).join("")}
        </div>
      </div>`).join("");
}

function setAll(state) {
  $$('#asset-picker input[name="asset"]').forEach((c) => (c.checked = state));
}
function setDefaults() {
  const defs = new Set(CATALOG.assets.filter((a) => a.default).map((a) => a.key));
  $$('#asset-picker input[name="asset"]').forEach((c) => (c.checked = defs.has(c.value)));
}

// ── 진행 애니메이션 ──────────────────────────────────────
const STEP_TEXT = {
  gpt: "GPT가 기획하는 중…", gemini: "Gemini가 아트를 생성하는 중…",
  sheet: "시트를 조합하는 중…", video: "CapCut 쇼케이스를 구성하는 중…",
};
let stepTimer = null;
function runSteps() {
  const order = ["gpt", "gemini", "sheet", "video"];
  let i = 0;
  const step = () => {
    $$(".steps li").forEach((li) => {
      const idx = order.indexOf(li.dataset.step);
      li.classList.toggle("done", idx < i);
      li.classList.toggle("active", idx === i);
    });
    if (order[i]) $("#loading-text").textContent = STEP_TEXT[order[i]];
    i = Math.min(i + 1, order.length - 1);
  };
  step();
  stepTimer = setInterval(step, 1500);
}

// ── 제출 ─────────────────────────────────────────────────
$("#gen-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const assets = $$('#asset-picker input[name="asset"]:checked').map((c) => c.value);
  if (!assets.length) { alert("아트 요소를 하나 이상 선택하세요."); return; }

  const payload = {
    entity_type: ENTITY,
    name: fd.get("name") || "",
    genre: fd.get("genre"),
    role: fd.get("role") || "",
    art_style: fd.get("art_style") || "semi-realistic digital painting",
    keywords: fd.get("keywords") || "",
    assets,
  };

  $("#empty").classList.add("hidden");
  $("#result").classList.add("hidden");
  $("#loading").classList.remove("hidden");
  $("#submit-btn").disabled = true;
  runSteps();

  try {
    const res = await fetch("/api/generate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "생성 실패");
    renderResult(await res.json());
  } catch (err) {
    $("#result").innerHTML = `<div class="warn">⚠ ${err.message}</div>`;
    $("#result").classList.remove("hidden");
  } finally {
    clearInterval(stepTimer);
    $("#loading").classList.add("hidden");
    $("#submit-btn").disabled = false;
  }
});

$("#sel-all").addEventListener("click", (e) => { e.preventDefault(); setAll(true); });
$("#sel-none").addEventListener("click", (e) => { e.preventDefault(); setAll(false); });
$("#sel-default").addEventListener("click", (e) => { e.preventDefault(); setDefaults(); });

// ── 결과 렌더링 ──────────────────────────────────────────
function renderResult(data) {
  const c = data.concept;
  const a = data.assets;
  const cats = CATALOG.categories;

  const byKind = (k) => a.find((x) => x.kind === k);
  const portrait = a.find((x) => x.is_image && x.category === "character") || byKind("sheet_png");

  const warnHtml = data.warnings.length
    ? `<div class="warn"><b>안내</b><ul>${data.warnings.map((w) => `<li>${w}</li>`).join("")}</ul></div>` : "";

  const palette = (c.color_palette || [])
    .map((h) => `<span style="background:${h}" title="${h}"></span>`).join("");

  const stats = (c.stats || []).map((s) => `
    <div class="stat-row"><span>${s.name}</span>
      <div class="stat-bar"><div class="stat-fill" style="width:${s.value}%"></div></div>
      <span class="stat-val">${s.value}</span></div>`).join("");

  const abilities = (c.abilities || []).map((x) => `<span>${x}</span>`).join("");
  const extra = (c.extra || []).map((x) =>
    `<div class="info-row"><b>${x.label}</b><span>${x.value}</span></div>`).join("");

  const entityLabel = CATALOG.entity_types[c.entity_type] || "캐릭터";

  // 이미지 에셋을 카테고리별 그룹으로
  const imgAssets = a.filter((x) => x.is_image && x.kind !== "sheet_png" && x.kind !== "video");
  const groups = {};
  imgAssets.forEach((x) => { (groups[x.category] ||= []).push(x); });

  const assetGroups = Object.keys(cats).filter((cat) => groups[cat]).map((cat) => `
    <div><p class="section-title">${cats[cat]}</p>
      <div class="assets-grid">${groups[cat].map((x) => `
        <div class="asset-card">
          <div class="media"><img src="${FILES}${x.path}" alt="${x.label}" loading="lazy"/></div>
          <div class="asset-meta"><span class="lbl">${x.label}${x.demo ? '<span class="badge-demo">DEMO</span>' : ""}</span>
            <a href="${FILES}${x.path}" download>⬇</a></div>
        </div>`).join("")}
      </div>
    </div>`).join("");

  // 시트 / 영상
  const sheetPng = byKind("sheet_png"), sheetPdf = byKind("sheet_pdf");
  const draft = byKind("capcut_draft");
  const videos = a.filter((x) => x.kind === "video");

  const sheetBlock = sheetPng ? `
    <div><p class="section-title">캐릭터 시트</p>
      <div class="asset-card" style="max-width:340px;margin-top:10px">
        <div class="media" style="aspect-ratio:1240/1754"><img src="${FILES}${sheetPng.path}" alt="시트"/></div>
        <div class="asset-meta"><span class="lbl">캐릭터 시트</span>
          <span><a href="${FILES}${sheetPng.path}" download>PNG</a>${sheetPdf ? ` · <a href="${FILES}${sheetPdf.path}" download>PDF</a>` : ""}</span>
        </div>
      </div></div>` : "";

  const videoBlock = videos.length ? `
    <div class="showcase"><p class="section-title">쇼케이스 영상</p>
      <img src="${FILES}${videos[0].path}" alt="쇼케이스"/>
      <div class="dl-row">
        ${videos.map((v) => `<a href="${FILES}${v.path}" download>${v.label} ⬇</a>`).join("")}
        ${draft ? `<a href="${FILES}${draft.path}/capcut_storyboard.json" download>CapCut 스토리보드 ⬇</a>` : ""}
      </div></div>` : "";

  $("#result").innerHTML = `
    ${warnHtml}
    <div class="char-head">
      ${portrait ? `<img src="${FILES}${portrait.path}" alt="${c.name}"/>` : ""}
      <div>
        <div class="entity-badge">${entityLabel}</div>
        <h3>${c.name}</h3>
        <p class="title">${[c.title, c.role, c.genre].filter(Boolean).join(" · ")}</p>
        <p class="tag">“${c.tagline || ""}”</p>
        <div class="palette">${palette}</div>
      </div>
    </div>

    ${assetGroups}

    <div class="two-col">
      <div><p class="section-title">스탯</p><div class="stats">${stats}</div></div>
      ${extra ? `<div><p class="section-title">정보</p><div class="info-list">${extra}</div></div>` : ""}
    </div>

    <div class="lore">
      <h4>외형</h4>${c.appearance || ""}
      <h4>${c.entity_type === "monster" ? "행동 양식" : "성격"}</h4>${c.personality || ""}
      <h4>${c.entity_type === "monster" ? "서식지 · 전승" : "배경"}</h4>${c.backstory || ""}
      <h4>${c.entity_type === "monster" ? "공격 패턴" : "시그니처 능력"}</h4>
      <div class="abilities">${abilities}</div>
    </div>

    ${sheetBlock}
    ${videoBlock}`;
  $("#result").classList.remove("hidden");
}

init();
