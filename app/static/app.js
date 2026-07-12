const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const FILES = "/files/";

let CATALOG = null;
let STATUS = null; // /api/status (모드 + 가격)
let SUBJECT = "character"; // 제작 대상: character | item | environment | vfx | ui
let ENTITY = "character";  // 캐릭터 대상 하위: character | monster | npc
let MODE = "single"; // single | batch

// 엔티티별 role 라벨 힌트 (캐릭터 대상)
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
// 사물/디자인 대상의 역할 라벨·힌트 (캐릭터 기획 없음)
const SUBJECT_ROLE = {
  item: ["유형 / 설명", "예: 화염 대검, 판금 갑옷, 마력 반지…"],
  environment: ["유형 / 설명", "예: 폐허 도시, 고대 숲, 수정 동굴…"],
  vfx: ["유형 / 설명", "예: 화염 폭발, 회복 오라, 참격 이펙트…"],
  ui: ["유형 / 설명", "예: 다크 판타지 UI, 네온 HUD…"],
};

// ── 초기 로드 ────────────────────────────────────────────
async function init() {
  await loadStatus();
  CATALOG = await (await fetch("/api/catalog")).json();
  renderSubjectTabs();
  renderEntityTabs();
  applySubjectUI();
  renderAssetPicker();
  renderGenres();
  renderRoles();
  renderRarities();
  renderArtStyles();
  renderModels();
  wireModeToggle();
  $("#hist-refresh").addEventListener("click", renderHistoryList);
  wirePathSettings();
  wirePresets();
  wireBudget();
  wireEditor();
  wireCompare();
  wireImport();
  loadSettings();
  loadPresets();
  loadUsage();
  loadBudget();
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
    mode: MODE, subject: SUBJECT, entity: ENTITY,
    name: fd.get("name") || "", genre: fd.get("genre"), role: fd.get("role") || "",
    art_style: fd.get("art_style") || "", keywords: fd.get("keywords") || "",
    image_scale: fd.get("image_scale"), variant_count: fd.get("variant_count"),
    image_model: fd.get("image_model") || "",
    consistency: fd.get("consistency") !== null, style_lock: fd.get("style_lock") !== null,
    transparent: fd.get("transparent") !== null, sprite_sheet: fd.get("sprite_sheet") !== null,
    count: fd.get("count"), make_codex: fd.get("make_codex") !== null, roles: fd.get("roles") || "",
    rarities: $$('#rarity-picker input[name="rarity"]:checked').map((c) => c.value),
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
  }
  if (cfg.subject) {
    SUBJECT = cfg.subject;
    $$(".stab").forEach((x) => x.classList.toggle("on", x.dataset.s === SUBJECT));
  }
  applySubjectUI();
  renderRoles();
  renderRarities();
  renderAssetPicker();
  if (Array.isArray(cfg.rarities) && cfg.rarities.length) {
    const rs = new Set(cfg.rarities);
    $$('#rarity-picker input[name="rarity"]').forEach((c) => (c.checked = rs.has(c.value)));
  }
  const setV = (sel, v) => { const el = $(sel); if (el != null && v != null) el.value = v; };
  setV('input[name="name"]', cfg.name); setV('select[name="genre"]', cfg.genre);
  setV('input[name="role"]', cfg.role); setV('input[name="art_style"]', cfg.art_style);
  setV('input[name="keywords"]', cfg.keywords); setV('select[name="image_scale"]', cfg.image_scale);
  setV('select[name="variant_count"]', cfg.variant_count); setV('select[name="image_model"]', cfg.image_model);
  setV('input[name="count"]', cfg.count);
  const ta = $('textarea[name="roles"]'); if (ta && cfg.roles != null) ta.value = cfg.roles;
  const setC = (n, v) => { if (v === undefined) return; const el = document.querySelector(`input[name="${n}"]`); if (el) el.checked = !!v; };
  setC("consistency", cfg.consistency); setC("style_lock", cfg.style_lock);
  setC("transparent", cfg.transparent); setC("sprite_sheet", cfg.sprite_sheet);
  if (cfg.make_codex !== undefined) setC("make_codex", cfg.make_codex !== false);
  if (Array.isArray(cfg.assets)) {
    const set = new Set(cfg.assets);
    $$('#asset-picker input[name="asset"]').forEach((c) => (c.checked = set.has(c.value)));
  }
  computeEstimate();
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
  if (CATALOG.entity_types && CATALOG.entity_types[e]) return CATALOG.entity_types[e];
  // 사물/디자인 대상은 entity_type 에 subject 키가 저장됨 → 한글 라벨로
  const sub = (CATALOG.subjects || []).find((s) => s.key === e);
  return (sub && sub.label) || e || "";
}

// ── 역할/종류 드롭다운 (제작 대상별) ─────────────────────
function renderRoles() {
  const sel = $("#role-preset");
  const input = $('input[name="role"]');
  if (!sel) return;
  const subj = subjectDef(SUBJECT);
  const preset = subj ? subj.role_preset : "job";
  let html = "";
  if (preset === "job" && CATALOG.role_groups) {
    html = '<option value="">— 직업 선택 —</option>';
    for (const [group, roles] of Object.entries(CATALOG.role_groups)) {
      html += `<optgroup label="${group}">` +
        roles.map((r) => `<option value="${r}">${r}</option>`).join("") + "</optgroup>";
    }
  } else if (preset === "item_types" && CATALOG.item_types) {
    html = '<option value="">— 종류 선택 —</option>' +
      CATALOG.item_types.map((r) => `<option value="${r}">${r}</option>`).join("");
  }
  sel.innerHTML = html;
  sel.classList.toggle("hidden", !html);  // 프리셋 없는 대상은 드롭다운 숨김
  // 선택 시 역할 입력칸을 채움(idempotent onchange)
  sel.onchange = () => { if (sel.value && input) input.value = sel.value; };
}

// ── 아이템 등급 체크박스 (아이템 대상 전용) ───────────────
function renderRarities() {
  const box = $("#rarity-box");
  const picker = $("#rarity-picker");
  if (!box || !picker) return;
  const subj = subjectDef(SUBJECT);
  const show = !!(subj && subj.rarities) && (CATALOG.rarities || []).length;
  box.classList.toggle("hidden", !show);
  if (!show) return;
  picker.innerHTML = CATALOG.rarities.map((r) => `
    <label class="asset-chip">
      <input type="checkbox" name="rarity" value="${r}" ${r === "일반" ? "checked" : ""} />
      <span>${r}</span>
    </label>`).join("");
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
         title="클릭: 설정 불러오기 + 결과 보기">
      <div class="hist-thumb">${it.thumb ? `<img src="/files/${it.thumb}" loading="lazy"/>` : "<span>◈</span>"}</div>
      <div class="hist-meta">
        <span class="hist-name">${it.name}</span>
        <span class="hist-sub">${entityLabel(it.entity)} · ${it.kind === "batch" ? "도감" : "단일"}</span>
      </div>
      <div class="hist-actions">
        <a href="#" class="hist-open" title="폴더 열기">📂</a>
        <a href="/api/zip/${it.id}" download title="ZIP 다운로드">📦</a>
        <a href="#" class="hist-del" title="삭제">🗑</a>
      </div>
    </div>`).join("");
  el.querySelectorAll(".hist-card").forEach((card) => {
    card.addEventListener("click", async (e) => {
      if (e.target.closest(".hist-actions")) return;
      // 클릭 → 이 항목의 설정을 폼에 불러오고 결과도 보여줌 (추가 생성 편의)
      try {
        const data = await (await fetch(card.dataset.url + "?t=" + Date.now())).json();
        loadHistoryConfig(data);
        $("#empty").classList.add("hidden");
        if (card.dataset.kind === "batch") renderBatch(data); else renderResult(data);
      } catch (err) { alert("불러오기 실패"); }
    });
  });
  el.querySelectorAll(".hist-open").forEach((a) => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      openFolder(a.closest(".hist-card").dataset.id);
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

// 히스토리 항목의 설정을 폼에 복원 — 추가 생성 편의.
// 저장된 원본 요청(request)이 있으면 키워드·변형수·크기·옵션까지 전부 복원.
function loadHistoryConfig(data) {
  const isBatch = !!(data.entries || data.batch_id);
  const entry0 = isBatch ? (data.entries && data.entries[0]) : data;
  const c = (entry0 && entry0.concept) || {};
  const req = (entry0 && entry0.request) || {};
  // 에셋: 저장된 요청 우선, 없으면 결과 kind 에서 복원(구버전 기록 대비)
  let assets = req.assets;
  if (!assets || !assets.length) {
    const kinds = new Set(((entry0 && entry0.assets) || []).map((a) => a.kind));
    assets = CATALOG.assets.filter((a) => kinds.has(a.key)).map((a) => a.key);
    if (kinds.has("sheet_png") || kinds.has("sheet_pdf")) assets.push("sheet");
  }
  // 이미지 크기 select 값 매칭(1.0 이 "1" 로 바뀌지 않게 문자열화)
  const scale = req.image_scale != null
    ? (Number(req.image_scale) === 1 ? "1.0" : String(req.image_scale)) : undefined;
  // 제작 대상 복원: 사물 대상은 entity_type 에 subject 가 저장되어 있음
  const objectKeys = new Set((CATALOG.subjects || [])
    .filter((s) => s.key !== "character").map((s) => s.key));
  const savedType = c.entity_type || data.entity_type || req.entity_type;
  const subject = req.subject || (objectKeys.has(savedType) ? savedType : "character");
  const entity = subject === "character"
    ? (req.entity_type || c.entity_type || "character") : "character";
  applyConfig({
    mode: isBatch ? "batch" : "single",
    subject: subject,
    entity: entity,
    name: isBatch ? "" : (c.name || req.name),
    genre: c.genre || req.genre,
    role: c.role || req.role,
    art_style: c.art_style || req.art_style,
    keywords: req.keywords,
    rarities: req.rarities,
    image_scale: scale,
    variant_count: req.variant_count != null ? String(req.variant_count) : undefined,
    image_model: req.image_model,
    consistency: req.consistency,
    style_lock: req.style_lock,
    transparent: req.transparent,
    sprite_sheet: req.sprite_sheet,
    assets: assets && assets.length ? assets : undefined,
  });
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
    const isImport = MODE === "import";
    $("#gen-form").classList.toggle("hidden", isImport);
    $("#import-section").classList.toggle("hidden", !isImport);
    $("#pform-foot").classList.toggle("hidden", isImport);
    // 제작 대상 탭은 단일 생성에서만. 일괄(도감)은 캐릭터/몬스터/NPC 전용.
    const subjTabs = $("#subject-tabs");
    if (subjTabs) subjTabs.classList.toggle("hidden", MODE !== "single");
    if (MODE === "batch" && SUBJECT !== "character") {
      SUBJECT = "character";
      $$(".stab").forEach((x) => x.classList.toggle("on", x.dataset.s === "character"));
      applySubjectUI();
      renderAssetPicker();
    }
    if (!isImport) {
      $("#single-fields").classList.toggle("hidden", MODE === "batch");
      $("#batch-fields").classList.toggle("hidden", MODE === "single");
      // 일괄 모드에서는 개체당 영상(N×)이 느리므로 기본 해제
      if (MODE === "batch") {
        const v = document.querySelector('#asset-picker input[value="video"]');
        if (v) v.checked = false;
      }
    }
    computeEstimate();
  }));
}

async function loadStatus() {
  try {
    const s = await (await fetch("/api/status")).json();
    STATUS = s;
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

// ── 제작 대상 탭 (최상위 대분류) ─────────────────────────
function subjectDef(key) {
  return (CATALOG.subjects || []).find((s) => s.key === key) || null;
}
function renderSubjectTabs() {
  const el = $("#subject-tabs");
  if (!el) return;
  el.innerHTML = (CATALOG.subjects || []).map((s) =>
    `<button type="button" class="stab ${s.key === SUBJECT ? "on" : ""}" data-s="${s.key}">${s.label}</button>`
  ).join("");
  $$(".stab").forEach((b) => b.addEventListener("click", () => setSubject(b.dataset.s)));
}
function setSubject(key) {
  SUBJECT = key;
  $$(".stab").forEach((x) => x.classList.toggle("on", x.dataset.s === SUBJECT));
  applySubjectUI();
  renderRoles();
  renderRarities();
  renderAssetPicker();
  computeEstimate();
}
// 대상에 따라 캐릭터 전용 필드(엔티티 하위탭·직업 프리셋) 표시/숨김 + 라벨 조정
function applySubjectUI() {
  const isChar = SUBJECT === "character";
  $("#gen-form").dataset.subject = SUBJECT;
  const roleInput = $('input[name="role"]');
  if (isChar) {
    if ($("#role-label")) $("#role-label").childNodes[0].nodeValue = ROLE_LABEL[ENTITY] + " ";
    if (roleInput) roleInput.placeholder = ROLE_PH[ENTITY];
  } else {
    const [label, ph] = SUBJECT_ROLE[SUBJECT] || ["유형 / 설명", ""];
    if ($("#role-label")) $("#role-label").childNodes[0].nodeValue = label + " ";
    if (roleInput) roleInput.placeholder = ph;
  }
}

// ── 엔티티 탭 (캐릭터 대상 하위) ─────────────────────────
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

// 에셋을 6개 상위 메뉴(대분류) → 카테고리(중분류) 순으로 묶는다.
// 선택 화면과 결과 산출물이 같은 구조를 공유하도록 한 곳에서 계산한다.
function groupBySuper(assets) {
  const cats = CATALOG.categories;
  const supers = CATALOG.supergroups || [];
  const byCat = {};
  assets.forEach((a) => { (byCat[a.category] ||= []).push(a); });
  return supers.map((sg) => {
    const subs = sg.cats
      .filter((c) => byCat[c])
      .map((c) => ({ cat: c, label: cats[c], items: byCat[c] }));
    const count = subs.reduce((n, s) => n + s.items.length, 0);
    return { key: sg.key, label: sg.label, subs, count };
  }).filter((sg) => sg.count > 0);
}

// ── 에셋 선택기 (제작 대상 → 상위 메뉴) ─────────────────────
function renderAssetPicker() {
  const subj = subjectDef(SUBJECT);
  const cats = new Set(subj ? subj.cats : Object.keys(CATALOG.categories));
  const defaults = new Set(subj ? subj.default_keys : ["fullbody"]);
  // 사물/디자인 대상은 엔티티 개념이 없으므로 캐릭터 기준으로 필터(백엔드와 동일).
  const ent = SUBJECT === "character" ? ENTITY : "character";
  const scoped = CATALOG.assets.filter(
    (a) => a.entities.includes(ent) && cats.has(a.category));
  const supers = groupBySuper(scoped);

  $("#asset-picker").innerHTML = supers.map((sg, idx) => {
    // 중분류가 2개 이상인 메뉴(캐릭터·UI)만 세부 라벨을 보여준다.
    const body = sg.subs.map((sub) => {
      const head = sg.subs.length > 1 ? `<p class="sub-cat">${sub.label}</p>` : "";
      const chips = sub.items.map((a) => {
        const badge = a.variable ? "가변" : (a.variants.length ? "×" + a.variants.length : "");
        return `
        <label class="asset-chip" title="${a.desc}">
          <input type="checkbox" name="asset" value="${a.key}" ${defaults.has(a.key) ? "checked" : ""} />
          <span>${a.label}${badge ? `<i>${badge}</i>` : ""}</span>
        </label>`;
      }).join("");
      return head + `<div class="group-items">${chips}</div>`;
    }).join("");
    return `
      <details class="asset-group" ${idx < 1 ? "open" : ""}>
        <summary>${sg.label} <span class="cnt">(${sg.count})</span>
          <span class="grp-sel"><a href="#" class="cat-all" data-sg="${sg.key}">전체</a><a href="#" class="cat-none" data-sg="${sg.key}">해제</a></span>
        </summary>
        ${body}
      </details>`;
  }).join("");

  // 일괄 모드에서는 개체당 영상(N×)이 느리므로 기본 해제
  if (MODE === "batch") {
    const v = document.querySelector('#asset-picker input[value="video"]');
    if (v) v.checked = false;
  }
  computeEstimate();
}

function setAll(state) {
  $$('#asset-picker input[name="asset"]').forEach((c) => (c.checked = state));
}
function setDefaults() {
  const subj = subjectDef(SUBJECT);
  const defs = new Set(subj ? subj.default_keys : CATALOG.assets.filter((a) => a.default).map((a) => a.key));
  $$('#asset-picker input[name="asset"]').forEach((c) => (c.checked = defs.has(c.value)));
}

// ── 예상 파일수 · 용량 · 비용 (실시간) ───────────────────
// PNG/GIF 용량은 픽셀수 기반 근사치. LIVE(실 API)는 사진/회화형이라 크고,
// DEMO(플레이스홀더)는 단순 도형이라 작다.
const BYTES_PER_PX = { live: 1.5, demo: 0.22 };  // 압축 PNG 근사(바이트/픽셀)
let LAST_ESTIMATE = null;   // 최근 computeEstimate() 결과
let BUDGET = null;          // /api/budget (limits + month_spent)

function imgBytes(size, scale, live) {
  const px = size[0] * size[1] * scale * scale;
  return px * (live ? BYTES_PER_PX.live : BYTES_PER_PX.demo);
}
function fmtBytes(b) {
  if (b >= 1024 * 1024) return (b / 1048576).toFixed(b >= 10485760 ? 0 : 1) + " MB";
  if (b >= 1024) return Math.round(b / 1024) + " KB";
  return Math.round(b) + " B";
}

// 이미지 에셋 1종의 (이미지 장수, 총 파일수, 용량) 계산
function assetFileInfo(a, variantCount, opts) {
  if (!a.is_image) { // 통합 산출물 (API 이미지 아님, 로컬 합성)
    if (a.key === "sheet") return { images: 0, files: 2, bytes: 2.2e6 };   // PNG+PDF
    if (a.key === "video") return { images: 0, files: 3, bytes: 4.5e6 };   // GIF+MP4+draft
    if (a.key === "bgm") return { images: 0, files: 2, bytes: 1.7e6 };     // WAV+가이드
    return { images: 0, files: 1, bytes: 3e5 };
  }
  const n = a.key === "item_art" ? Math.max(1, opts.rarityCount || 1)
    : a.variable ? Math.min(variantCount, a.pool_max)
    : (a.fixed_count > 0 ? a.fixed_count : 1);
  let files = n;
  let bytes = n * imgBytes(a.size, opts.scale, opts.live);
  if (a.is_anim && n > 1) {                 // 애니: 스트립 시트 + GIF
    files += 2;
    bytes += imgBytes(a.size, opts.scale, opts.live) * n * 0.9;  // 시트
    bytes += a.size[0] * a.size[1] * n * 0.4;                    // GIF(팔레트)
  } else if (opts.spriteSheet && n > 1) {   // 스프라이트 시트 패킹
    files += 1;
    bytes += imgBytes(a.size, opts.scale, opts.live) * n * 0.9;
  }
  if (a.key === "tileset") {                // 3×3 미리보기 1장
    files += 1;
    bytes += imgBytes(a.size, opts.scale, false) * 0.6;
  }
  return { images: n, files, bytes };
}

function computeEstimate() {
  if (!CATALOG || !STATUS) return;
  const byKey = Object.fromEntries(CATALOG.assets.map((a) => [a.key, a]));
  const fd = new FormData($("#gen-form"));
  const model = fd.get("image_model") || "";
  const useOpenAIImg = model === "gpt-image-1";
  const imgLive = useOpenAIImg ? STATUS.gpt === "live" : STATUS.gemini === "live";
  const gptLive = STATUS.gpt === "live";

  let images = 0, files = 0, bytes = 0, concepts = 0, hasAssets = false;

  if (MODE === "import") {
    // CSV 계획 전체 합산
    const plans = IMPORT_PLANS || [];
    plans.forEach((pl) => {
      concepts += 1;
      let f = 2, b = 20000, im = 0;
      const opts = { scale: pl.image_scale, live: imgLive, spriteSheet: false };
      (pl.assets || []).forEach((k) => {
        const a = byKey[k]; if (!a) return;
        const info = assetFileInfo(a, pl.variant_count, opts);
        im += info.images; f += info.files; b += info.bytes;
      });
      images += im; files += f; bytes += b;
      if ((pl.assets || []).length) hasAssets = true;
    });
  } else {
    const checked = $$('#asset-picker input[name="asset"]:checked').map((c) => c.value);
    const variantCount = parseInt(fd.get("variant_count") || "5", 10);
    const scale = parseFloat(fd.get("image_scale") || "1.0");
    const spriteSheet = fd.get("sprite_sheet") !== null;
    const rarityCount = $$('#rarity-picker input[name="rarity"]:checked').length;
    const opts = { scale, live: imgLive, spriteSheet, rarityCount };
    hasAssets = checked.length > 0;
    let im = 0, f = 2, b = 20000; // concept.json + result.json + 여유
    checked.forEach((k) => {
      const a = byKey[k]; if (!a) return;
      const info = assetFileInfo(a, variantCount, opts);
      im += info.images; f += info.files; b += info.bytes;
    });
    let mult = 1, extraFiles = 0, extraBytes = 0;
    if (MODE === "batch") {
      mult = Math.max(1, Math.min(8, parseInt(fd.get("count") || "4", 10)));
      if (fd.get("make_codex") !== null) { extraFiles = 1; extraBytes = 5e5; }
    }
    images = im * mult; files = f * mult + extraFiles; bytes = b * mult + extraBytes;
    concepts = mult;
  }

  // 비용: 이미지 장수 × 장당 단가 + 기획(GPT) 개체당. 데모(비-LIVE)는 무료.
  const p = STATUS.pricing || {};
  const perImg = useOpenAIImg ? (p.openai_image || 0.04) : (p.gemini_image || 0.039);
  let usd = 0;
  if (imgLive) usd += images * perImg;
  if (gptLive) usd += (p.gpt_concept || 0.002) * concepts;
  const krw = usd * (p.usd_krw || 1350);

  LAST_ESTIMATE = { files, bytes, images, usd, krw, live: imgLive, hasAssets };
  $("#est-files").textContent = files.toLocaleString();
  $("#est-size").textContent = "~" + fmtBytes(bytes);
  $("#est-images").textContent = images.toLocaleString();
  const costEl = $("#est-cost");
  const noteEl = $("#est-note");
  if (!hasAssets) {
    costEl.textContent = "–";
    noteEl.textContent = MODE === "import" ? "· CSV를 올리세요" : "· 에셋을 선택하세요";
    noteEl.className = "est-note warnish";
  } else if (usd <= 0) {
    costEl.textContent = "무료";
    noteEl.textContent = "· 데모 모드 (API 미과금)";
    noteEl.className = "est-note demoish";
  } else {
    costEl.textContent = "~$" + usd.toFixed(3) + " (₩" + Math.round(krw).toLocaleString() + ")";
    noteEl.textContent = "· 예상치";
    noteEl.className = "est-note";
  }
}

// ── 예산 · 비용 확인 ─────────────────────────────────────
async function loadBudget() {
  try { BUDGET = await (await fetch("/api/budget")).json(); }
  catch (e) { BUDGET = null; return; }
  const L = BUDGET.limits || {};
  const set = (id, v) => { const el = $(id); if (el) el.value = v; };
  set("#bg-confirm", L.confirm_threshold ?? 0.5);
  set("#bg-perrun", L.per_run_limit ?? 0);
  set("#bg-monthly", L.monthly_limit ?? 0);
  const krw = BUDGET.usd_krw || 1350;
  const spent = BUDGET.month_spent_usd || 0;
  if ($("#bg-spent")) $("#bg-spent").textContent =
    "$" + spent.toFixed(3) + " (₩" + Math.round(spent * krw).toLocaleString() + ")";
  if ($("#bg-month")) $("#bg-month").textContent = BUDGET.month ? "· " + BUDGET.month : "";
}

function wireBudget() {
  const ed = $("#budget-editor");
  $("#budget-toggle").addEventListener("click", () => {
    ed.classList.toggle("hidden");
    if (!ed.classList.contains("hidden")) loadBudget();
  });
  $("#bg-close").addEventListener("click", () => ed.classList.add("hidden"));
  $("#bg-save").addEventListener("click", async () => {
    const limits = {
      confirm_threshold: parseFloat($("#bg-confirm").value || "0") || 0,
      per_run_limit: parseFloat($("#bg-perrun").value || "0") || 0,
      monthly_limit: parseFloat($("#bg-monthly").value || "0") || 0,
    };
    try {
      const r = await fetch("/api/budget", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ limits }),
      });
      if (!r.ok) throw new Error((await r.json()).detail || "저장 실패");
      BUDGET = await r.json();
      ed.classList.add("hidden");
    } catch (err) { alert("예산 저장 실패: " + err.message); }
  });
}

// 생성 전 예산 가드. 계속 진행하면 true, 막히면 false.
function budgetGate() {
  const e = LAST_ESTIMATE;
  if (!e || !e.live || e.usd <= 0) return true;   // 데모/무료는 통과
  const L = (BUDGET && BUDGET.limits) || {};
  const krw = (BUDGET && BUDGET.usd_krw) || 1350;
  const spent = (BUDGET && BUDGET.month_spent_usd) || 0;
  const won = (u) => "₩" + Math.round(u * krw).toLocaleString();
  const money = (u) => "$" + u.toFixed(3) + " (" + won(u) + ")";

  // 1회 상한 (하드 차단)
  if (L.per_run_limit > 0 && e.usd > L.per_run_limit) {
    alert(`⛔ 1회 상한 초과\n\n예상 비용 ${money(e.usd)} 이 1회 상한 ${money(L.per_run_limit)} 을 넘습니다.\n` +
      `에셋/변형 수를 줄이거나 ⚙예산에서 상한을 올리세요.`);
    return false;
  }
  // 월 예산 (하드 차단)
  if (L.monthly_limit > 0 && (spent + e.usd) > L.monthly_limit) {
    alert(`⛔ 월 예산 초과\n\n이번 달 사용 ${money(spent)} + 이번 예상 ${money(e.usd)} = ${money(spent + e.usd)}\n` +
      `월 예산 ${money(L.monthly_limit)} 을 넘습니다.\n⚙예산에서 예산을 조정하세요.`);
    return false;
  }
  // 확인 임계값 (소프트 확인)
  const th = L.confirm_threshold ?? 0.5;
  if (th >= 0 && e.usd > th) {
    return confirm(`💳 이번 생성 예상 비용\n\n${money(e.usd)} · 이미지 ${e.images}장` +
      (spent > 0 ? `\n이번 달 누적: ${money(spent)}` : "") +
      `\n\n계속 진행할까요?`);
  }
  return true;
}

// ── 이미지 편집 모달 ─────────────────────────────────────
const EDIT = { file: null, card: null, crop: null, drag: null };

function openEditor(card) {
  const file = card.dataset.file;
  if (!file || !CURRENT_JOB_ID) { alert("편집할 파일을 찾을 수 없습니다."); return; }
  EDIT.file = file;
  EDIT.card = card;
  EDIT.crop = null;
  $("#edit-title").textContent = (card.dataset.label || "이미지") + " · 편집";
  const src = FILES + CURRENT_JOB_ID + "/" + file + "?t=" + Date.now();
  const img = $("#edit-img");
  img.src = src;
  resetEditControls();
  $("#crop-rect").classList.add("hidden");
  $("#edit-imgwrap").style.background = "";
  $("#edit-modal").classList.remove("hidden");
}

function resetEditControls() {
  $("#adj-bri").value = 1; $("#adj-con").value = 1; $("#adj-sat").value = 1;
  $("#bg-custom").value = "#3355aa";
  EDIT.bg = "";
  applyPreview();
}

function pct(v) { return Math.round(v * 100) + "%"; }

function applyPreview() {
  const b = parseFloat($("#adj-bri").value), c = parseFloat($("#adj-con").value),
    s = parseFloat($("#adj-sat").value);
  $("#v-bri").textContent = pct(b); $("#v-con").textContent = pct(c); $("#v-sat").textContent = pct(s);
  $("#edit-img").style.filter = `brightness(${b}) contrast(${c}) saturate(${s})`;
  const wrap = $("#edit-imgwrap");
  if (EDIT.bg === "transparent" || EDIT.bg === "" || EDIT.bg == null) {
    wrap.classList.toggle("checker", EDIT.bg === "transparent");
    wrap.style.background = "";
  } else {
    wrap.classList.remove("checker");
    wrap.style.background = EDIT.bg;
  }
}

function wireEditor() {
  const modal = $("#edit-modal");
  const close = () => modal.classList.add("hidden");
  $("#edit-close").addEventListener("click", close);
  $("#edit-cancel").addEventListener("click", close);
  modal.addEventListener("click", (e) => { if (e.target === modal) close(); });

  ["adj-bri", "adj-con", "adj-sat"].forEach((id) =>
    $("#" + id).addEventListener("input", applyPreview));

  $("#edit-reset").addEventListener("click", resetEditControls);
  $("#crop-clear").addEventListener("click", () => {
    EDIT.crop = null; $("#crop-rect").classList.add("hidden");
  });

  // 배경 스와치
  $("#bg-swatches").addEventListener("click", (e) => {
    const sw = e.target.closest(".sw"); if (!sw) return;
    EDIT.bg = sw.dataset.bg; applyPreview();
    $$("#bg-swatches .sw").forEach((x) => x.classList.remove("on"));
    sw.classList.add("on");
  });
  $("#bg-custom").addEventListener("input", (e) => {
    EDIT.bg = e.target.value; applyPreview();
    $$("#bg-swatches .sw").forEach((x) => x.classList.remove("on"));
  });

  // 크롭 드래그
  const wrap = $("#edit-imgwrap"), rect = $("#crop-rect");
  wrap.addEventListener("pointerdown", (e) => {
    if (e.target.closest(".sw")) return;
    const img = $("#edit-img");
    const r = img.getBoundingClientRect();
    EDIT.drag = { r, x0: e.clientX, y0: e.clientY };
    rect.classList.remove("hidden");
    wrap.setPointerCapture(e.pointerId);
    updateCropRect(e.clientX, e.clientY);
  });
  wrap.addEventListener("pointermove", (e) => {
    if (EDIT.drag) updateCropRect(e.clientX, e.clientY);
  });
  wrap.addEventListener("pointerup", (e) => {
    if (!EDIT.drag) return;
    finalizeCrop(e.clientX, e.clientY);
    EDIT.drag = null;
  });

  $("#edit-apply").addEventListener("click", applyEdit);
}

function updateCropRect(cx, cy) {
  const { r, x0, y0 } = EDIT.drag;
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const ax = clamp(x0, r.left, r.right), ay = clamp(y0, r.top, r.bottom);
  const bx = clamp(cx, r.left, r.right), by = clamp(cy, r.top, r.bottom);
  const left = Math.min(ax, bx), top = Math.min(ay, by);
  const w = Math.abs(bx - ax), h = Math.abs(by - ay);
  const rect = $("#crop-rect");
  const wrapR = $("#edit-imgwrap").getBoundingClientRect();
  rect.style.left = (left - wrapR.left) + "px";
  rect.style.top = (top - wrapR.top) + "px";
  rect.style.width = w + "px";
  rect.style.height = h + "px";
}

function finalizeCrop(cx, cy) {
  const { r, x0, y0 } = EDIT.drag;
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const ax = clamp(x0, r.left, r.right), ay = clamp(y0, r.top, r.bottom);
  const bx = clamp(cx, r.left, r.right), by = clamp(cy, r.top, r.bottom);
  const l = (Math.min(ax, bx) - r.left) / r.width;
  const t = (Math.min(ay, by) - r.top) / r.height;
  const rr = (Math.max(ax, bx) - r.left) / r.width;
  const bb = (Math.max(ay, by) - r.top) / r.height;
  // 너무 작은 선택은 크롭 취소로 간주
  if (rr - l < 0.03 || bb - t < 0.03) {
    EDIT.crop = null; $("#crop-rect").classList.add("hidden"); return;
  }
  EDIT.crop = { l, t, r: rr, b: bb };
}

async function applyEdit() {
  if (!EDIT.file || !CURRENT_JOB_ID) return;
  const payload = {
    file: EDIT.file,
    crop: EDIT.crop,
    bg: (EDIT.bg === "" ? null : EDIT.bg),
    brightness: parseFloat($("#adj-bri").value),
    contrast: parseFloat($("#adj-con").value),
    saturation: parseFloat($("#adj-sat").value),
  };
  const btn = $("#edit-apply");
  btn.disabled = true; btn.textContent = "적용 중…";
  try {
    const r = await fetch("/api/edit/" + encodeURIComponent(CURRENT_JOB_ID), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error((await r.json()).detail || "편집 실패");
    const out = await r.json();
    // 카드 이미지 갱신 (캐시 회피)
    if (EDIT.card) {
      const cimg = EDIT.card.querySelector("img");
      if (cimg) cimg.src = FILES + out.file + "?t=" + Date.now();
    }
    $("#edit-modal").classList.add("hidden");
  } catch (err) {
    alert("편집 실패: " + err.message);
  } finally {
    btn.disabled = false; btn.textContent = "✓ 적용";
  }
}

// ── 변형 비교·채택 (재패킹) ──────────────────────────────
const COMPARE = { kind: null };

function openCompare(kind) {
  if (!CURRENT_RESULT || !CURRENT_JOB_ID) return;
  const variants = (CURRENT_RESULT.assets || [])
    .filter((a) => a.kind === kind && a.is_image);
  if (variants.length <= 1) return;
  COMPARE.kind = kind;
  const spec = CATALOG.assets.find((a) => a.key === kind);
  $("#compare-title").textContent = (spec ? spec.label : kind) + " · 변형 비교";
  $("#compare-grid").innerHTML = variants.map((v) => {
    const fn = v.path.split("/").pop();
    return `<label class="cmp-card on" data-file="${fn}">
      <img src="${FILES}${v.path}?t=${Date.now()}" alt="${v.label}" loading="lazy"/>
      <span class="cmp-lbl">${v.label}${v.demo ? '<span class="badge-demo">DEMO</span>' : ""}</span>
      <input type="checkbox" checked />
    </label>`;
  }).join("");
  updateCompareCount();
  $("#compare-modal").classList.remove("hidden");
}

function updateCompareCount() {
  const total = $$("#compare-grid .cmp-card").length;
  const on = $$("#compare-grid .cmp-card input:checked").length;
  $("#compare-count").textContent = `${on} / ${total} 선택`;
  $("#compare-apply").disabled = on === 0;
}

function wireCompare() {
  const modal = $("#compare-modal");
  const close = () => modal.classList.add("hidden");
  $("#compare-close").addEventListener("click", close);
  $("#compare-cancel").addEventListener("click", close);
  modal.addEventListener("click", (e) => { if (e.target === modal) close(); });

  $("#compare-grid").addEventListener("change", (e) => {
    const card = e.target.closest(".cmp-card");
    if (card) card.classList.toggle("on", e.target.checked);
    updateCompareCount();
  });
  $("#compare-all").addEventListener("click", () => {
    $$("#compare-grid .cmp-card input").forEach((c) => { c.checked = true; });
    $$("#compare-grid .cmp-card").forEach((c) => c.classList.add("on"));
    updateCompareCount();
  });

  $("#compare-apply").addEventListener("click", async () => {
    const keep = $$("#compare-grid .cmp-card").filter((c) => c.querySelector("input").checked)
      .map((c) => c.dataset.file);
    if (!keep.length) return;
    const total = $$("#compare-grid .cmp-card").length;
    if (keep.length === total) { close2(); return; }  // 변화 없음
    const btn = $("#compare-apply");
    btn.disabled = true; btn.textContent = "재패킹 중…";
    try {
      const r = await fetch("/api/repack/" + encodeURIComponent(CURRENT_JOB_ID), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asset_key: COMPARE.kind, keep }),
      });
      if (!r.ok) throw new Error((await r.json()).detail || "재패킹 실패");
      // 갱신된 result.json 을 다시 불러 결과 재렌더
      const data = await (await fetch(`${FILES}${CURRENT_JOB_ID}/result.json?t=${Date.now()}`)).json();
      renderResult(data);
      modal.classList.add("hidden");
    } catch (err) {
      alert("재패킹 실패: " + err.message);
    } finally {
      btn.disabled = false; btn.textContent = "✓ 채택 (재패킹)";
    }
  });
  function close2() { modal.classList.add("hidden"); }
}

// ── CSV / 스프레드시트 가져오기 ──────────────────────────
let IMPORT_PLANS = null;  // 최근 미리보기 계획

function wireImport() {
  const input = $("#import-file"), dz = $("#drop-zone");
  input.addEventListener("change", () => {
    if (input.files && input.files[0]) uploadImport(input.files[0]);
  });
  ["dragover", "dragenter"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("over"); }));
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("over"); }));
  dz.addEventListener("drop", (e) => {
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) uploadImport(f);
  });
  $("#import-run").addEventListener("click", runImport);
}

async function uploadImport(file) {
  $("#import-fname").textContent = "분석 중… (" + file.name + ")";
  const fd = new FormData();
  fd.append("file", file);
  try {
    const r = await fetch("/api/import/preview", { method: "POST", body: fd });
    if (!r.ok) throw new Error((await r.json()).detail || "분석 실패");
    const data = await r.json();
    IMPORT_PLANS = data.plans;
    $("#import-fname").textContent = file.name + " · " + data.total + "행" +
      (data.truncated ? " (50행까지만 처리)" : "");
    renderImportPreview(data.plans);
  } catch (err) {
    IMPORT_PLANS = null;
    $("#import-fname").textContent = "";
    $("#import-preview").classList.remove("hidden");
    $("#import-preview").innerHTML = `<div class="warn">⚠ ${err.message}</div>`;
    $("#import-actions").classList.add("hidden");
  }
}

function renderImportPreview(plans) {
  const el = $("#import-preview");
  el.classList.remove("hidden");
  if (!plans.length) { el.innerHTML = `<div class="warn">⚠ 유효한 행이 없습니다.</div>`; return; }
  const eLabel = (e) => (CATALOG.entity_types[e] || e);
  el.innerHTML = `<table class="imp-table">
    <thead><tr><th>#</th><th>타입</th><th>이름</th><th>역할</th><th>에셋</th></tr></thead>
    <tbody>${plans.map((p, i) => `
      <tr>
        <td>${i + 1}</td>
        <td>${eLabel(p.entity_type)}</td>
        <td>${p.name || "<i>자동</i>"}</td>
        <td>${p.role || "-"}</td>
        <td class="imp-assets">${p.assets.map((k) => assetLabel(k)).join(", ")}
          ${p.warnings.length ? `<span class="imp-warn" title="${p.warnings.join("\n")}">⚠${p.warnings.length}</span>` : ""}
        </td>
      </tr>`).join("")}</tbody>
  </table>`;
  $("#import-actions").classList.remove("hidden");
  computeEstimate();
  $("#import-summary").textContent = `${plans.length}개 개체 · ` + $("#est-images").textContent + "장 이미지";
  $("#import-run").textContent = `✦ 전체 생성 (${plans.length})`;
}

function assetLabel(key) {
  const a = CATALOG.assets.find((x) => x.key === key);
  return a ? a.label : key;
}

async function runImport() {
  if (!IMPORT_PLANS || !IMPORT_PLANS.length) return;
  computeEstimate();
  if (!budgetGate()) return;

  const progressId = "imp_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
  const rows = IMPORT_PLANS.map((p) => ({
    entity_type: p.entity_type, name: p.name, role: p.role, genre: p.genre,
    art_style: p.art_style, keywords: p.keywords, assets: p.assets,
    variant_count: p.variant_count, image_scale: p.image_scale,
    transparent: p.transparent,
  }));

  $("#empty").classList.add("hidden");
  $("#result").classList.add("hidden");
  $("#loading").classList.remove("hidden");
  $("#import-run").disabled = true;
  $("#cancel-btn").disabled = false;
  pollProgress(progressId);

  try {
    const r = await fetch("/api/import/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows, progress_id: progressId }),
    });
    if (r.status === 409) {
      $("#result").innerHTML = `<div class="warn">✕ 생성이 취소되었습니다.</div>`;
      $("#result").classList.remove("hidden"); return;
    }
    if (!r.ok) throw new Error((await r.json()).detail || "생성 실패");
    const data = await r.json();
    renderImportResults(data.results);
    loadUsage(); loadBudget(); renderHistoryList();
  } catch (err) {
    $("#result").innerHTML = `<div class="warn">⚠ ${err.message}</div>`;
    $("#result").classList.remove("hidden");
  } finally {
    stopProgress(); CURRENT_PID = null;
    $("#loading").classList.add("hidden");
    $("#import-run").disabled = false;
  }
}

function renderImportResults(results) {
  const res = $("#result");
  res.classList.remove("hidden");
  const eLabel = (e) => (CATALOG.entity_types[e] || e);
  res.innerHTML = `<div class="imp-done">✓ ${results.length}개 개체 생성 완료</div>
    <div class="imp-result-grid">${results.map((d) => {
      const thumb = (d.assets.find((a) => a.is_image && a.category === "character")
        || d.assets.find((a) => a.is_image) || {}).path;
      return `<div class="imp-rcard" data-job="${d.job_id}">
        <div class="media">${thumb ? `<img src="${FILES}${thumb}?t=${Date.now()}" loading="lazy"/>` : ""}</div>
        <div class="irc-body">
          <div class="entity-badge">${eLabel(d.concept.entity_type)}</div>
          <b>${d.concept.name}</b>
          <span class="hint sm">${d.assets.filter((a) => a.is_image).length}장 · ${d.concept.role || ""}</span>
          <div class="irc-actions">
            <button type="button" class="link-btn imp-view" data-url="${FILES}${d.job_id}/result.json">열기</button>
            <a href="/api/zip/${d.job_id}" download>📦</a>
          </div>
        </div>
      </div>`;
    }).join("")}</div>`;
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

  // 예산 가드: 예상 비용이 상한/임계값을 넘으면 차단하거나 확인받는다
  computeEstimate();
  if (!budgetGate()) return;

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
      subject: SUBJECT,
      entity_type: SUBJECT === "character" ? ENTITY : SUBJECT,
      name: fd.get("name") || "", genre: fd.get("genre"),
      role: fd.get("role") || "",
      rarities: $$('#rarity-picker input[name="rarity"]:checked').map((c) => c.value),
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
    loadBudget();
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

$("#sel-all").addEventListener("click", (e) => { e.preventDefault(); setAll(true); computeEstimate(); });
$("#sel-none").addEventListener("click", (e) => { e.preventDefault(); setAll(false); computeEstimate(); });
$("#sel-default").addEventListener("click", (e) => { e.preventDefault(); setDefaults(); computeEstimate(); });

// 등급 전체/해제
function setRarities(state) { $$('#rarity-picker input[name="rarity"]').forEach((c) => (c.checked = state)); }
$("#rar-all").addEventListener("click", (e) => { e.preventDefault(); setRarities(true); computeEstimate(); });
$("#rar-none").addEventListener("click", (e) => { e.preventDefault(); setRarities(false); computeEstimate(); });

// 카테고리(중분류)별 전체/해제 — summary 안이라 토글 전파를 막는다
$("#asset-picker").addEventListener("click", (e) => {
  const link = e.target.closest(".cat-all, .cat-none");
  if (!link) return;
  e.preventDefault(); e.stopPropagation();
  const det = link.closest(".asset-group");
  const on = link.classList.contains("cat-all");
  det.querySelectorAll('input[name="asset"]').forEach((c) => { c.checked = on; });
  computeEstimate();
});

// 고급 옵션 전체/해제
$("#adv-all").addEventListener("click", (e) => {
  e.preventDefault();
  $$('.adv input[type="checkbox"]').forEach((c) => { c.checked = true; });
  computeEstimate();
});
$("#adv-none").addEventListener("click", (e) => {
  e.preventDefault();
  $$('.adv input[type="checkbox"]').forEach((c) => { c.checked = false; });
  computeEstimate();
});

// 폼의 어떤 값이 바뀌든(체크박스/셀렉트/숫자) 예상치 갱신
$("#gen-form").addEventListener("input", computeEstimate);
$("#gen-form").addEventListener("change", computeEstimate);

// ── 개별 에셋 재생성 ─────────────────────────────────────
let CURRENT_JOB_ID = null;
let CURRENT_RESULT = null;

$("#result").addEventListener("click", async (e) => {
  // 편집 / 비교 버튼 우선 처리
  const editBtn = e.target.closest(".edit-btn");
  if (editBtn) { openEditor(editBtn.closest(".asset-card")); return; }
  const cmpBtn = e.target.closest(".compare-btn");
  if (cmpBtn) { openCompare(cmpBtn.dataset.compare); return; }
  const viewBtn = e.target.closest(".imp-view");
  if (viewBtn) {
    try {
      const data = await (await fetch(viewBtn.dataset.url + "?t=" + Date.now())).json();
      renderResult(data);
      $("#result").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) { alert("불러오기 실패: " + err.message); }
    return;
  }

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
  CURRENT_RESULT = data;
  const c = data.concept;
  const a = data.assets;

  const byKind = (k) => a.find((x) => x.kind === k);
  // 대표 이미지: 캐릭터면 캐릭터 아트, 사물/디자인이면 첫 이미지 산출물
  const portrait = a.find((x) => x.is_image && x.category === "character")
    || a.find((x) => x.is_image && x.kind !== "sheet_png" && x.kind !== "video")
    || byKind("sheet_png");
  // 캐릭터 기획(스탯·성격·배경)이 있는 대상인지 — 사물/디자인은 없음
  const hasBio = (c.stats && c.stats.length) || c.personality || c.backstory;

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

  const subjLabel = (CATALOG.subjects || []).find((s) => s.key === c.entity_type);
  const entityLabel = CATALOG.entity_types[c.entity_type] || (subjLabel && subjLabel.label) || "캐릭터";

  // 이미지 에셋을 6개 상위 메뉴 → 중분류 순으로 그룹핑
  const imgAssets = a.filter((x) => x.is_image && x.kind !== "sheet_png" && x.kind !== "video");
  const regenKeys = new Set(CATALOG.assets.map((a) => a.key));
  const fnOf = (path) => path.split(/[\\/]/).pop();  // / 와 \ 모두 대응
  // 같은 kind 의 이미지가 여러 장이면(variant) 비교·채택 버튼 노출
  const kindCounts = {};
  imgAssets.forEach((x) => { kindCounts[x.kind] = (kindCounts[x.kind] || 0) + 1; });
  const card = (x) => `
        <div class="asset-card" data-kind="${x.kind}" data-file="${fnOf(x.path)}" data-label="${x.label}">
          <div class="media"><img src="${FILES}${x.path}?t=${Date.now()}" alt="${x.label}" loading="lazy"/></div>
          <div class="asset-meta"><span class="lbl">${x.label}${x.demo ? '<span class="badge-demo">DEMO</span>' : ""}</span>
            <span class="asset-actions">
              ${kindCounts[x.kind] > 1 ? `<button type="button" class="compare-btn" data-compare="${x.kind}" title="변형 비교·채택 (${kindCounts[x.kind]}장)">⊞</button>` : ""}
              <button type="button" class="edit-btn" data-edit="${fnOf(x.path)}" title="편집 (크롭·배경·보정)">✎</button>
              ${regenKeys.has(x.kind) ? `<button type="button" class="regen-btn" data-regen="${x.kind}" title="이 에셋만 다시 생성">↻</button>` : ""}
              <a href="${FILES}${x.path}" download>⬇</a></span>
          </div>
        </div>`;
  const assetGroups = groupBySuper(imgAssets).map((sg) => `
    <div class="super-block"><p class="section-title">${sg.label}</p>
      ${sg.subs.map((sub) => `
        ${sg.subs.length > 1 ? `<p class="sub-cat">${sub.label}</p>` : ""}
        <div class="assets-grid">${sub.items.map(card).join("")}</div>`).join("")}
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

  // BGM (오디오 루프 + CapCut 가이드)
  const bgm = byKind("bgm"), bgmGuide = byKind("bgm_guide");
  const bgmBlock = bgm ? `
    <div class="showcase"><p class="section-title">배경음악 (BGM)</p>
      <audio controls src="${FILES}${bgm.path}" style="width:100%;margin-top:8px"></audio>
      <div class="dl-row">
        <a href="${FILES}${bgm.path}" download>루프 WAV ⬇</a>
        ${bgmGuide ? `<a href="${FILES}${bgmGuide.path}" download>CapCut BGM 가이드 ⬇</a>` : ""}
      </div>
      <p class="hint sm">데모 루프입니다. 실제 영상엔 가이드의 키워드로 CapCut 음악을 고르세요.</p>
    </div>` : "";

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

    ${hasBio ? `
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
    </div>` : (c.appearance ? `<div class="lore"><h4>설명</h4>${c.appearance}</div>` : "")}

    ${sheetBlock}
    ${videoBlock}
    ${bgmBlock}`;
  $("#result").classList.remove("hidden");
}

// 이미지 에셋을 6개 상위 메뉴 그룹 HTML로 (시트/영상 제외)
function assetGroupsHTML(assets, compact = false) {
  const imgs = assets.filter((x) => x.is_image && x.kind !== "sheet_png" && x.kind !== "video" && x.kind !== "codex");
  const card = (x) => `
        <div class="asset-card">
          <div class="media"><img src="${FILES}${x.path}" alt="${x.label}" loading="lazy"/></div>
          <div class="asset-meta"><span class="lbl">${x.label}${x.demo ? '<span class="badge-demo">DEMO</span>' : ""}</span>
            <a href="${FILES}${x.path}" download>⬇</a></div>
        </div>`;
  return groupBySuper(imgs).map((sg) => `
    <div class="super-block"><p class="section-title">${sg.label}</p>
      ${sg.subs.map((sub) => `
        ${sg.subs.length > 1 ? `<p class="sub-cat">${sub.label}</p>` : ""}
        <div class="assets-grid ${compact ? "compact" : ""}">${sub.items.map(card).join("")}</div>`).join("")}
    </div>`).join("");
}

// ── 일괄 생성(도감) 결과 ─────────────────────────────────
function renderBatch(data) {
  CURRENT_JOB_ID = null;  // 개별 재생성은 단일 잡에만 적용
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
