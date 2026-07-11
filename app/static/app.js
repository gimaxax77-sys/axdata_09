const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const FILES = "/files/";

let CATALOG = null;
let ENTITY = "character";
let MODE = "single"; // single | batch

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
  renderGenres();
  renderRoles();
  renderArtStyles();
  renderModels();
  wireModeToggle();
  $("#hist-refresh").addEventListener("click", renderHistoryList);
  wirePathSettings();
  wirePresets();
  loadSettings();
  loadPresets();
  loadUsage();
  renderHistoryList();
}

// ── 프리셋 저장/불러오기 ─────────────────────────────────
let PRESETS = {};
async function loadPresets(selectName) {
  try { PRESETS = await (await fetch("/api/presets")).json(); } catch (e) { PRESETS = {}; }
  const s = $("#preset-select");
  s.innerHTML = '<option value="">📁 프리셋 불러오기…</option>' +
    Object.keys(PRESETS).map((n) => `<option value="${n}">${n}</option>`).join("");
  if (selectName) s.value = selectName;
}
function gatherConfig() {
  const fd = new FormData($("#gen-form"));
  return {
    mode: MODE, entity: ENTITY,
    name: fd.get("name") || "", genre: fd.get("genre"), role: fd.get("role") || "",
    art_style: fd.get("art_style") || "", keywords: fd.get("keywords") || "",
    image_scale: fd.get("image_scale"), variant_count: fd.get("variant_count"),
    image_model: fd.get("image_model") || "",
    consistency: fd.get("consistency") !== null, style_lock: fd.get("style_lock") !== null,
    transparent: fd.get("transparent") !== null, sprite_sheet: fd.get("sprite_sheet") !== null,
    count: fd.get("count"), make_codex: fd.get("make_codex") !== null, roles: fd.get("roles") || "",
    assets: $$('#asset-picker input[name="asset"]:checked').map((c) => c.value),
  };
}
function applyConfig(cfg) {
  if (!cfg) return;
  MODE = cfg.mode === "batch" ? "batch" : "single";
  $$(".mtab").forEach((x) => x.classList.toggle("on", x.dataset.m === MODE));
  $("#single-fields").classList.toggle("hidden", MODE === "batch");
  $("#batch-fields").classList.toggle("hidden", MODE === "single");
  if (cfg.entity) {
    ENTITY = cfg.entity;
    $$(".etab").forEach((x) => x.classList.toggle("on", x.dataset.e === ENTITY));
    if ($("#role-label")) $("#role-label").childNodes[0].nodeValue = ROLE_LABEL[ENTITY] + " ";
  }
  renderAssetPicker();
  const setV = (sel, v) => { const el = $(sel); if (el != null && v != null) el.value = v; };
  setV('input[name="name"]', cfg.name); setV('select[name="genre"]', cfg.genre);
  setV('input[name="role"]', cfg.role); setV('input[name="art_style"]', cfg.art_style);
  setV('input[name="keywords"]', cfg.keywords); setV('select[name="image_scale"]', cfg.image_scale);
  setV('select[name="variant_count"]', cfg.variant_count); setV('select[name="image_model"]', cfg.image_model);
  setV('input[name="count"]', cfg.count);
  const ta = $('textarea[name="roles"]'); if (ta && cfg.roles != null) ta.value = cfg.roles;
  const setC = (n, v) => { const el = document.querySelector(`input[name="${n}"]`); if (el) el.checked = !!v; };
  setC("consistency", cfg.consistency); setC("style_lock", cfg.style_lock);
  setC("transparent", cfg.transparent); setC("sprite_sheet", cfg.sprite_sheet);
  setC("make_codex", cfg.make_codex !== false);
  if (Array.isArray(cfg.assets)) {
    const set = new Set(cfg.assets);
    $$('#asset-picker input[name="asset"]').forEach((c) => (c.checked = set.has(c.value)));
  }
}
function wirePresets() {
  $("#preset-select").addEventListener("change", (e) => {
    if (e.target.value) applyConfig(PRESETS[e.target.value]);
  });
  $("#preset-save").addEventListener("click", async () => {
    const name = prompt("프리셋 이름을 입력하세요:");
    if (!name) return;
    await fetch("/api/presets", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim(), config: gatherConfig() }),
    });
    loadPresets(name.trim());
  });
  $("#preset-del").addEventListener("click", async () => {
    const name = $("#preset-select").value;
    if (!name) { alert("삭제할 프리셋을 먼저 선택하세요."); return; }
    if (!confirm(`프리셋 "${name}" 삭제?`)) return;
    await fetch("/api/presets/" + encodeURIComponent(name), { method: "DELETE" });
    loadPresets();
  });
}

// ── 저장 경로 설정 ───────────────────────────────────────
const DEFAULT_PATH = "D:\\.CODE\\.Claude\\아트팩\\art_create_all";
async function loadSettings() {
  try {
    const s = await (await fetch("/api/settings")).json();
    if ($("#hist-path")) $("#hist-path").textContent = s.output_dir || "outputs";
    if ($("#path-input")) $("#path-input").value = s.output_dir || "";
  } catch (e) {}
}
function wirePathSettings() {
  $("#path-edit").addEventListener("click", () => {
    $("#path-editor").classList.toggle("hidden");
  });
  $("#path-cancel").addEventListener("click", () => $("#path-editor").classList.add("hidden"));
  $("#path-default").addEventListener("click", (e) => {
    e.preventDefault(); $("#path-input").value = DEFAULT_PATH;
  });
  $("#path-save").addEventListener("click", async () => {
    const v = $("#path-input").value.trim();
    if (!v) { alert("경로를 입력하세요."); return; }
    try {
      const r = await fetch("/api/settings", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ output_dir: v }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "실패");
      $("#hist-path").textContent = d.output_dir;
      $("#path-editor").classList.add("hidden");
      renderHistoryList();
      alert("저장 경로가 변경되었습니다:\n" + d.output_abs);
    } catch (err) { alert("경로 저장 실패: " + err.message); }
  });
}

function entityLabel(e) {
  return (CATALOG.entity_types && CATALOG.entity_types[e]) || e || "";
}

// ── 직업 드롭다운 (optgroup) ─────────────────────────────
function renderRoles() {
  const sel = $("#role-preset");
  const input = $('input[name="role"]');
  if (!sel || !CATALOG.role_groups) return;
  let html = '<option value="">— 직업 선택 —</option>';
  for (const [group, roles] of Object.entries(CATALOG.role_groups)) {
    html += `<optgroup label="${group}">` +
      roles.map((r) => `<option value="${r}">${r}</option>`).join("") + "</optgroup>";
  }
  sel.innerHTML = html;
  sel.addEventListener("change", () => { if (sel.value && input) input.value = sel.value; });
}

// ── 생성 히스토리 (우측 상시) ────────────────────────────
async function renderHistoryList() {
  const el = $("#history-list");
  el.innerHTML = '<p class="hint">불러오는 중…</p>';
  let items = [];
  try { items = await (await fetch("/api/history")).json(); } catch (e) {}
  if (!items.length) { el.innerHTML = '<p class="hint">아직 생성 기록이 없습니다.</p>'; return; }
  el.innerHTML = items.map((it) => `
    <div class="hist-card" data-url="${it.result_url}" data-kind="${it.kind}" data-id="${it.id}"
         title="클릭: 폴더 열기">
      <div class="hist-thumb">${it.thumb ? `<img src="/files/${it.thumb}" loading="lazy"/>` : "<span>◈</span>"}</div>
      <div class="hist-meta">
        <span class="hist-name">${it.name}</span>
        <span class="hist-sub">${entityLabel(it.entity)} · ${it.kind === "batch" ? "도감" : "단일"}</span>
      </div>
      <div class="hist-actions">
        <a href="#" class="hist-view" title="결과 다시보기">👁</a>
        <a href="/api/zip/${it.id}" download title="ZIP 다운로드">📦</a>
        <a href="#" class="hist-del" title="삭제">🗑</a>
      </div>
    </div>`).join("");
  el.querySelectorAll(".hist-card").forEach((card) => {
    card.addEventListener("click", (e) => {
      if (e.target.closest(".hist-actions")) return;
      openFolder(card.dataset.id);  // 클릭 → 폴더 열기
    });
  });
  el.querySelectorAll(".hist-view").forEach((a) => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      const c = a.closest(".hist-card");
      viewHistory(c.dataset.url, c.dataset.kind);
    });
  });
  el.querySelectorAll(".hist-del").forEach((a) => {
    a.addEventListener("click", async (e) => {
      e.preventDefault();
      const id = a.closest(".hist-card").dataset.id;
      if (!confirm("이 생성 기록을 삭제할까요? (폴더 삭제)")) return;
      await fetch("/api/history/" + encodeURIComponent(id), { method: "DELETE" });
      renderHistoryList();
    });
  });
}
async function openFolder(id) {
  try {
    const r = await fetch("/api/open/" + encodeURIComponent(id), { method: "POST" });
    if (!r.ok) throw new Error();
  } catch (e) { alert("폴더 열기는 로컬 실행 시에만 동작합니다."); }
}
async function viewHistory(url, kind) {
  try {
    const data = await (await fetch(url)).json();
    $("#empty").classList.add("hidden");
    if (kind === "batch") renderBatch(data); else renderResult(data);
  } catch (e) { alert("불러오기 실패"); }
}

function renderGenres() {
  const sel = $("#genre-select");
  if (!sel || !CATALOG.genres) return;
  sel.innerHTML = Object.entries(CATALOG.genres)
    .map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
}

function renderArtStyles() {
  const sel = $("#style-preset");
  const input = $('input[name="art_style"]');
  if (!sel || !CATALOG.art_styles) return;
  sel.innerHTML = '<option value="">— 프리셋 선택 —</option>' +
    CATALOG.art_styles.map((s) => `<option value="${s}">${s}</option>`).join("");
  // 현재 입력값이 프리셋에 있으면 선택 표시
  if (input && CATALOG.art_styles.includes(input.value)) sel.value = input.value;
  sel.addEventListener("change", () => {
    if (sel.value && input) input.value = sel.value;
  });
}

function renderModels() {
  const sel = $("#model-select");
  if (!sel || !CATALOG.image_models) return;
  sel.innerHTML = CATALOG.image_models
    .map((m) => `<option value="${m.value}">${m.label}</option>`).join("");
}

// ── 사용량·예상 비용 ─────────────────────────────────────
async function loadUsage() {
  try { renderUsage(await (await fetch("/api/usage")).json()); } catch (e) {}
}
function fmtNum(n) { return n >= 1000 ? (n / 1000).toFixed(1) + "K" : String(n); }
function renderUsage(u) {
  const el = $("#usage");
  if (!el) return;
  const krw = "~₩" + (u.total_krw || 0).toLocaleString();
  el.innerHTML = `
    <span class="u-item" title="GPT 토큰 사용량">📝 ${fmtNum(u.openai.tokens)}</span>
    <span class="u-item" title="생성한 이미지 수">🖼️ ${u.gemini.images}</span>
    <span class="u-total">~$${u.total_usd.toFixed(2)} <em>${krw}</em></span>
    <a href="#" id="usage-reset" title="집계 초기화">↺</a>`;
  const r = $("#usage-reset");
  if (r) r.addEventListener("click", async (e) => {
    e.preventDefault();
    await fetch("/api/usage/reset", { method: "POST" });
    loadUsage();
  });
}

function wireModeToggle() {
  $$(".mtab").forEach((b) => b.addEventListener("click", () => {
    MODE = b.dataset.m;
    $$(".mtab").forEach((x) => x.classList.toggle("on", x.dataset.m === MODE));
    $("#single-fields").classList.toggle("hidden", MODE === "batch");
    $("#batch-fields").classList.toggle("hidden", MODE === "single");
    // 일괄 모드에서는 개체당 영상(N×)이 느리므로 기본 해제
    if (MODE === "batch") {
      const v = document.querySelector('#asset-picker input[value="video"]');
      if (v) v.checked = false;
    }
  }));
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
    if (s.output_dir && $("#hist-path")) $("#hist-path").textContent = s.output_dir + "/";
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
          ${grouped[c].map((a) => {
            const badge = a.variable ? "가변" : (a.variants.length ? "×" + a.variants.length : "");
            return `
            <label class="asset-chip" title="${a.desc}">
              <input type="checkbox" name="asset" value="${a.key}" ${a.default ? "checked" : ""}/>
              <span>${a.label}${badge ? `<i>${badge}</i>` : ""}</span>
            </label>`; }).join("")}
        </div>
      </div>`).join("");

  // 일괄 모드에서는 개체당 영상(N×)이 느리므로 기본 해제
  if (MODE === "batch") {
    const v = document.querySelector('#asset-picker input[value="video"]');
    if (v) v.checked = false;
  }
}

function setAll(state) {
  $$('#asset-picker input[name="asset"]').forEach((c) => (c.checked = state));
}
function setDefaults() {
  const defs = new Set(CATALOG.assets.filter((a) => a.default).map((a) => a.key));
  $$('#asset-picker input[name="asset"]').forEach((c) => (c.checked = defs.has(c.value)));
}

// ── 실시간 진행률 (서버 폴링) ────────────────────────────
let progressTimer = null;
let CURRENT_PID = null;

function setProgress(pct, label) {
  const bar = $("#progress-bar").firstElementChild;
  if (bar) bar.style.width = Math.max(0, Math.min(100, pct)) + "%";
  $("#progress-pct").textContent = pct + "%";
  if (label) $("#loading-text").textContent = label;
}

function pollProgress(pid) {
  CURRENT_PID = pid;
  setProgress(0, "생성 준비 중…");
  progressTimer = setInterval(async () => {
    try {
      const p = await (await fetch("/api/progress/" + encodeURIComponent(pid))).json();
      if (!p.found) return;
      setProgress(p.percent || 0, p.label || "");
      if (p.done) stopProgress();
    } catch (e) { /* 폴링 실패 무시 */ }
  }, 700);
}

function stopProgress() {
  if (progressTimer) { clearInterval(progressTimer); progressTimer = null; }
}

$("#cancel-btn").addEventListener("click", async () => {
  if (!CURRENT_PID) return;
  $("#cancel-btn").disabled = true;
  $("#loading-text").textContent = "취소 요청 중…";
  try { await fetch("/api/cancel/" + encodeURIComponent(CURRENT_PID), { method: "POST" }); }
  catch (e) {}
});

// ── 제출 ─────────────────────────────────────────────────
$("#gen-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const assets = $$('#asset-picker input[name="asset"]:checked').map((c) => c.value);
  if (!assets.length) { alert("아트 요소를 하나 이상 선택하세요."); return; }

  const batch = MODE === "batch";
  const imageScale = parseFloat(fd.get("image_scale") || "1.0");
  const variantCount = parseInt(fd.get("variant_count") || "5", 10);
  const consistency = fd.get("consistency") !== null;
  const transparent = fd.get("transparent") !== null;
  const spriteSheet = fd.get("sprite_sheet") !== null;
  const styleLock = fd.get("style_lock") !== null;
  const imageModel = fd.get("image_model") || "";
  const progressId = "pg_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
  const adv = { consistency, transparent, sprite_sheet: spriteSheet,
                style_lock: styleLock, image_model: imageModel,
                progress_id: progressId };
  let url, payload;
  if (batch) {
    const roles = (fd.get("roles") || "").split("\n").map((s) => s.trim()).filter(Boolean);
    url = "/api/generate_batch";
    payload = {
      entity_type: ENTITY, genre: fd.get("genre"),
      art_style: fd.get("art_style") || "semi-realistic digital painting",
      keywords: fd.get("keywords") || "",
      count: Math.max(1, Math.min(8, parseInt(fd.get("count") || "4", 10))),
      roles, names: [], assets,
      make_codex: fd.get("make_codex") !== null,
      image_scale: imageScale, variant_count: variantCount,
      ...adv,
    };
  } else {
    url = "/api/generate";
    payload = {
      entity_type: ENTITY, name: fd.get("name") || "", genre: fd.get("genre"),
      role: fd.get("role") || "",
      art_style: fd.get("art_style") || "semi-realistic digital painting",
      keywords: fd.get("keywords") || "", assets,
      image_scale: imageScale, variant_count: variantCount,
      ...adv,
    };
  }

  $("#empty").classList.add("hidden");
  $("#result").classList.add("hidden");
  $("#loading").classList.remove("hidden");
  $("#submit-btn").disabled = true;
  $("#cancel-btn").disabled = false;
  pollProgress(progressId);

  try {
    const res = await fetch(url, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.status === 409) { // 사용자 취소
      $("#result").innerHTML = `<div class="warn">✕ 생성이 취소되었습니다.</div>`;
      $("#result").classList.remove("hidden");
      return;
    }
    if (!res.ok) throw new Error((await res.json()).detail || "생성 실패");
    const data = await res.json();
    if (batch) renderBatch(data); else renderResult(data);
    loadUsage();
    renderHistoryList();
  } catch (err) {
    $("#result").innerHTML = `<div class="warn">⚠ ${err.message}</div>`;
    $("#result").classList.remove("hidden");
  } finally {
    stopProgress();
    CURRENT_PID = null;
    $("#loading").classList.add("hidden");
    $("#submit-btn").disabled = false;
  }
});

$("#sel-all").addEventListener("click", (e) => { e.preventDefault(); setAll(true); });
$("#sel-none").addEventListener("click", (e) => { e.preventDefault(); setAll(false); });
$("#sel-default").addEventListener("click", (e) => { e.preventDefault(); setDefaults(); });

// ── 개별 에셋 재생성 ─────────────────────────────────────
let CURRENT_JOB_ID = null;

$("#result").addEventListener("click", async (e) => {
  const btn = e.target.closest(".regen-btn");
  if (!btn || !CURRENT_JOB_ID) return;
  const kind = btn.dataset.regen;
  const card = btn.closest(".asset-card");
  const fd = new FormData($("#gen-form"));
  const payload = {
    asset_key: kind,
    image_scale: parseFloat(fd.get("image_scale") || "1.0"),
    variant_count: parseInt(fd.get("variant_count") || "5", 10),
    transparent: fd.get("transparent") !== null,
    style_lock: fd.get("style_lock") !== null,
    image_model: fd.get("image_model") || "",
  };
  btn.disabled = true;
  btn.textContent = "…";
  try {
    const res = await fetch("/api/regenerate/" + encodeURIComponent(CURRENT_JOB_ID), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "재생성 실패");
    const out = await res.json();
    // 대표(첫) 산출물 이미지를 카드에서 즉시 갱신 (캐시 회피용 타임스탬프)
    const first = (out.assets || []).find((a) => a.kind === kind) || (out.assets || [])[0];
    if (first && card) {
      const img = card.querySelector("img");
      if (img) img.src = FILES + first.path + "?t=" + Date.now();
      const demo = card.querySelector(".badge-demo");
      if (first.demo && !demo) card.querySelector(".lbl").insertAdjacentHTML("beforeend", '<span class="badge-demo">DEMO</span>');
      if (!first.demo && demo) demo.remove();
    }
    loadUsage();
  } catch (err) {
    alert("재생성 실패: " + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "↻";
  }
});

// ── 결과 렌더링 ──────────────────────────────────────────
function renderResult(data) {
  CURRENT_JOB_ID = data.job_id || null;
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

  const regenKeys = new Set(CATALOG.assets.map((a) => a.key));
  const assetGroups = Object.keys(cats).filter((cat) => groups[cat]).map((cat) => `
    <div><p class="section-title">${cats[cat]}</p>
      <div class="assets-grid">${groups[cat].map((x) => `
        <div class="asset-card" data-kind="${x.kind}">
          <div class="media"><img src="${FILES}${x.path}?t=${Date.now()}" alt="${x.label}" loading="lazy"/></div>
          <div class="asset-meta"><span class="lbl">${x.label}${x.demo ? '<span class="badge-demo">DEMO</span>' : ""}</span>
            <span class="asset-actions">
              ${regenKeys.has(x.kind) ? `<button type="button" class="regen-btn" data-regen="${x.kind}" title="이 에셋만 다시 생성">↻</button>` : ""}
              <a href="${FILES}${x.path}" download>⬇</a></span>
          </div>
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
    <div class="dl-row"><a class="zip-btn" href="/api/zip/${data.job_id}" download>📦 전체 ZIP 다운로드</a></div>
    <div class="char-head">
      ${portrait ? `<img src="${FILES}${portrait.path}" alt="${c.name}"/>` : ""}
      <div>
        <div class="entity-badge">${entityLabel}</div>
        <h3>${c.name}</h3>
        ${c.name_en ? `<div class="name-en">${c.name_en}</div>` : ""}
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

// 이미지 에셋을 카테고리별 그룹 HTML로 (시트/영상 제외)
function assetGroupsHTML(assets, compact = false) {
  const cats = CATALOG.categories;
  const imgs = assets.filter((x) => x.is_image && x.kind !== "sheet_png" && x.kind !== "video" && x.kind !== "codex");
  const groups = {};
  imgs.forEach((x) => { (groups[x.category] ||= []).push(x); });
  return Object.keys(cats).filter((c) => groups[c]).map((c) => `
    <div><p class="section-title">${cats[c]}</p>
      <div class="assets-grid ${compact ? "compact" : ""}">${groups[c].map((x) => `
        <div class="asset-card">
          <div class="media"><img src="${FILES}${x.path}" alt="${x.label}" loading="lazy"/></div>
          <div class="asset-meta"><span class="lbl">${x.label}${x.demo ? '<span class="badge-demo">DEMO</span>' : ""}</span>
            <a href="${FILES}${x.path}" download>⬇</a></div>
        </div>`).join("")}
      </div></div>`).join("");
}

// ── 일괄 생성(도감) 결과 ─────────────────────────────────
function renderBatch(data) {
  CURRENT_JOB_ID = null;  // 개별 재생성은 단일 잡에만 적용
  const cats = CATALOG.categories;
  const entityLabel = CATALOG.entity_types[data.entity_type] || "";

  const warnHtml = data.warnings.length
    ? `<div class="warn"><b>안내</b><ul>${data.warnings.map((w) => `<li>${w}</li>`).join("")}</ul></div>` : "";

  const codexBlock = data.codex ? `
    <div><p class="section-title">${entityLabel} 도감</p>
      <div class="codex-wrap">
        <img src="${FILES}${data.codex.path}" alt="도감"/>
        <div class="dl-row"><a href="${FILES}${data.codex.path}" download>도감 이미지 ⬇</a></div>
      </div></div>` : "";

  const entries = data.entries.map((e, i) => {
    const c = e.concept;
    const portrait = e.assets.find((x) => x.is_image && x.category === "character") || e.assets.find((x) => x.kind === "sheet_png");
    const sheetPng = e.assets.find((x) => x.kind === "sheet_png");
    const sheetPdf = e.assets.find((x) => x.kind === "sheet_pdf");
    const videos = e.assets.filter((x) => x.kind === "video");
    return `
      <details class="entry" ${i === 0 ? "open" : ""}>
        <summary>
          ${portrait ? `<img src="${FILES}${portrait.path}" alt="${c.name}"/>` : '<span class="ph"></span>'}
          <span class="entry-name">${c.name}</span>
          <span class="entry-role">${[c.role, c.genre].filter(Boolean).join(" · ")}</span>
        </summary>
        <div class="entry-body">
          <p class="tag">“${c.tagline || ""}”</p>
          ${assetGroupsHTML(e.assets, true)}
          <div class="dl-row">
            ${sheetPng ? `<a href="${FILES}${sheetPng.path}" download>시트 PNG ⬇</a>` : ""}
            ${sheetPdf ? `<a href="${FILES}${sheetPdf.path}" download>PDF ⬇</a>` : ""}
            ${videos.map((v) => `<a href="${FILES}${v.path}" download>${v.label} ⬇</a>`).join("")}
          </div>
        </div>
      </details>`;
  }).join("");

  $("#result").innerHTML = `
    ${warnHtml}
    <div class="dl-row"><a class="zip-btn" href="/api/zip/${data.batch_id}" download>📦 도감 전체 ZIP 다운로드</a></div>
    ${codexBlock}
    <div><p class="section-title">개체 ${data.entries.length}종</p>
      <div class="entries">${entries}</div>
    </div>`;
  $("#result").classList.remove("hidden");
}

init();
