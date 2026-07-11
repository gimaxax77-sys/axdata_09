const $ = (sel) => document.querySelector(sel);
const FILES = "/files/";

// ── 상태 표시 (live / demo) ──────────────────────────────
async function loadStatus() {
  try {
    const s = await (await fetch("/api/status")).json();
    const pills = [
      ["GPT", s.gpt, s.openai_model],
      ["Gemini", s.gemini, s.gemini_model],
    ];
    $("#status").innerHTML = pills.map(([name, mode, model]) =>
      `<span class="pill ${mode}" title="${model}">
         <span class="dot"></span>${name}: ${mode === "live" ? "연결됨" : "데모"}
       </span>`
    ).join("");
  } catch (e) { /* noop */ }
}

// ── 진행 단계 애니메이션 ─────────────────────────────────
const STEP_TEXT = {
  gpt: "GPT가 캐릭터를 기획하는 중…",
  gemini: "Gemini가 아트를 생성하는 중…",
  sheet: "캐릭터 시트를 조합하는 중…",
  video: "CapCut 쇼케이스를 구성하는 중…",
};
let stepTimer = null;
function runStepAnimation() {
  const order = ["gpt", "gemini", "sheet", "video"];
  let i = 0;
  const advance = () => {
    document.querySelectorAll(".steps li").forEach((li) => {
      const s = li.dataset.step;
      const idx = order.indexOf(s);
      li.classList.toggle("done", idx < i);
      li.classList.toggle("active", idx === i);
    });
    if (order[i]) $("#loading-text").textContent = STEP_TEXT[order[i]];
    i = Math.min(i + 1, order.length - 1);
  };
  advance();
  stepTimer = setInterval(advance, 1400);
}

// ── 폼 제출 ──────────────────────────────────────────────
$("#gen-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const payload = {
    name: fd.get("name") || "",
    genre: fd.get("genre"),
    role: fd.get("role") || "",
    art_style: fd.get("art_style") || "semi-realistic digital painting",
    keywords: fd.get("keywords") || "",
    make_sheet: fd.get("make_sheet") !== null,
    make_assets: fd.get("make_assets") !== null,
    make_video: fd.get("make_video") !== null,
  };

  $("#empty").classList.add("hidden");
  $("#result").classList.add("hidden");
  $("#loading").classList.remove("hidden");
  $("#submit-btn").disabled = true;
  runStepAnimation();

  try {
    const res = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "생성 실패");
    const data = await res.json();
    renderResult(data);
  } catch (err) {
    $("#result").innerHTML = `<div class="warn">⚠ ${err.message}</div>`;
    $("#result").classList.remove("hidden");
  } finally {
    clearInterval(stepTimer);
    $("#loading").classList.add("hidden");
    $("#submit-btn").disabled = false;
  }
});

// ── 결과 렌더링 ──────────────────────────────────────────
function assetByKind(assets, kind) {
  return assets.find((a) => a.kind === kind);
}

function renderResult(data) {
  const c = data.concept;
  const a = data.assets;
  const portrait = assetByKind(a, "portrait");
  const jobBase = FILES; // 경로는 job_id 포함 상대경로

  const warnHtml = data.warnings.length
    ? `<div class="warn"><b>안내</b><ul>${data.warnings.map((w) => `<li>${w}</li>`).join("")}</ul></div>`
    : "";

  const palette = (c.color_palette || [])
    .map((h) => `<span style="background:${h}" title="${h}"></span>`).join("");

  const stats = (c.stats || []).map((s) => `
    <div class="stat-row">
      <span>${s.name}</span>
      <div class="stat-bar"><div class="stat-fill" style="width:${s.value}%"></div></div>
      <span class="stat-val">${s.value}</span>
    </div>`).join("");

  const abilities = (c.abilities || [])
    .map((ab) => `<span>${ab}</span>`).join("");

  // 아트 에셋 카드
  const artKinds = ["portrait", "fullbody", "icon"];
  const artCards = artKinds.map((k) => {
    const asset = assetByKind(a, k);
    if (!asset) return "";
    return `<div class="asset-card">
      <div class="media"><img src="${jobBase}${asset.path}" alt="${asset.label}"/></div>
      <div class="asset-meta"><span class="lbl">${asset.label}${asset.demo ? '<span class="badge-demo">DEMO</span>' : ""}</span>
        <a href="${jobBase}${asset.path}" download>다운로드</a></div>
    </div>`;
  }).join("");

  // 문서(시트) 카드
  const sheetPng = assetByKind(a, "sheet_png");
  const sheetPdf = assetByKind(a, "sheet_pdf");
  const draft = assetByKind(a, "capcut_draft");
  const videos = a.filter((x) => x.kind === "video");

  const sheetBlock = sheetPng ? `
    <div>
      <p class="section-title">캐릭터 시트</p>
      <div class="asset-card" style="max-width:340px;margin-top:10px">
        <div class="media" style="aspect-ratio:1240/1754"><img src="${jobBase}${sheetPng.path}" alt="캐릭터 시트"/></div>
        <div class="asset-meta"><span class="lbl">캐릭터 시트${sheetPng.demo ? '<span class="badge-demo">DEMO</span>' : ""}</span>
          <span>
            <a href="${jobBase}${sheetPng.path}" download>PNG</a>
            ${sheetPdf ? `&nbsp;·&nbsp;<a href="${jobBase}${sheetPdf.path}" download>PDF</a>` : ""}
          </span>
        </div>
      </div>
    </div>` : "";

  const videoBlock = videos.length ? `
    <div class="showcase">
      <p class="section-title">쇼케이스 영상</p>
      <img src="${jobBase}${videos[0].path}" alt="쇼케이스"/>
      <div class="dl-row">
        ${videos.map((v) => `<a href="${jobBase}${v.path}" download>${v.label} ⬇</a>`).join("")}
        ${draft ? `<a href="${jobBase}${draft.path}/capcut_storyboard.json" download>CapCut 스토리보드 ⬇</a>` : ""}
      </div>
    </div>` : "";

  $("#result").innerHTML = `
    ${warnHtml}
    <div class="char-head">
      ${portrait ? `<img src="${jobBase}${portrait.path}" alt="${c.name}"/>` : ""}
      <div>
        <h3>${c.name}</h3>
        <p class="title">${[c.title, c.role, c.genre].filter(Boolean).join(" · ")}</p>
        <p class="tag">“${c.tagline || ""}”</p>
        <div class="palette">${palette}</div>
      </div>
    </div>

    ${artCards ? `<div><p class="section-title">게임 아트 에셋</p><div class="assets-grid" style="margin-top:10px">${artCards}</div></div>` : ""}

    <div>
      <p class="section-title">스탯</p>
      <div class="stats" style="margin-top:10px">${stats}</div>
    </div>

    <div class="lore">
      <h4>외형</h4>${c.appearance || ""}
      <h4>성격</h4>${c.personality || ""}
      <h4>배경 이야기</h4>${c.backstory || ""}
      <h4>시그니처 능력</h4>
      <div class="abilities">${abilities}</div>
    </div>

    ${sheetBlock}
    ${videoBlock}
  `;
  $("#result").classList.remove("hidden");
}

loadStatus();
