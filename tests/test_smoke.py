"""스모크 테스트 — 핵심 경로(파이프라인/배경제거/타일러블/슬러그/경로안전/
카탈로그/진행률·취소/재생성)를 데모 모드로 빠르게 검증.

실 API 없이도 전 구간이 동작해야 한다(데모 폴백). 회귀 방지용.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from PIL import Image

from app.config import get_settings
from app.models import (
    GenerationRequest, BatchRequest, RegenerateRequest, RepackRequest, GenBase,
)
from app.services import asset_catalog as cat
from app.services import imageops, pipeline, progress


@pytest.fixture()
def settings(tmp_path):
    s = get_settings()
    s.output_dir = str(tmp_path)
    return s


# ── 카탈로그 ──────────────────────────────────────────────
def test_catalog_payload_shape():
    payload = cat.catalog_payload()
    assert "assets" in payload and payload["assets"]
    assert "entity_types" in payload
    assert "categories" in payload
    # 각 에셋은 key/label/category/entities 를 갖는다
    a = payload["assets"][0]
    for f in ("key", "label", "category", "entities"):
        assert f in a


def test_supergroups_cover_every_category():
    # 6개 상위 메뉴가 모든 중분류를 한 번씩만 담아야 함(선택·산출물 그룹 기준)
    payload = cat.catalog_payload()
    supers = payload["supergroups"]
    assert [sg["key"] for sg in supers] == \
        ["character", "item", "environment", "vfx", "ui", "set"]
    covered = [c for sg in supers for c in sg["cats"]]
    assert sorted(covered) == sorted(payload["categories"])   # 빠짐·중복 없음
    assert len(covered) == len(set(covered))


def test_subjects_scope_categories_and_defaults():
    payload = cat.catalog_payload()
    subs = {s["key"]: s for s in payload["subjects"]}
    assert set(subs) == {"character", "item", "environment", "vfx", "ui"}
    # 캐릭터만 기획 생성 대상
    assert subs["character"]["concept"] is True
    assert subs["item"]["concept"] is False
    # 아이템 대상은 아이템 카테고리만, 기본 선택 1개 이상
    assert subs["item"]["cats"] == ["item"]
    assert subs["item"]["default_keys"]


def test_object_subject_has_no_bio_and_right_assets(settings):
    # 사물/디자인 대상은 스탯·성격 없이 해당 산출물만
    req = GenerationRequest(subject="item", genre="fantasy", role="화염 대검")
    res = pipeline.run_pipeline(req, settings, "job_item")
    assert res.concept.stats == []
    assert res.concept.personality == ""
    assert res.concept.entity_type == "item"
    cats = {cat.CATALOG[a.kind].category for a in res.assets if a.kind in cat.CATALOG}
    assert "character" not in cats  # 캐릭터 아트는 생성되지 않음


def test_item_art_generates_per_selected_rarity(settings):
    # 아이템 일러스트는 선택한 등급 수만큼 생성(등급이 변형 축)
    req = GenerationRequest(subject="item", genre="fantasy", role="장검",
                            assets=["item_art"], rarities=["일반", "전설", "극"])
    res = pipeline.run_pipeline(req, settings, "job_item_rar")
    arts = [a for a in res.assets if a.kind == "item_art"]
    assert len(arts) == 3
    assert {a.label.split("·")[-1].strip() for a in arts} == {"일반", "전설", "극"}


def test_item_art_defaults_to_one_when_no_rarity(settings):
    req = GenerationRequest(subject="item", genre="fantasy", role="방패", assets=["item_art"])
    res = pipeline.run_pipeline(req, settings, "job_item_norar")
    assert len([a for a in res.assets if a.kind == "item_art"]) == 1


def test_type_lists_and_rarities_in_payload():
    p = cat.catalog_payload()
    assert p["type_lists"]["item_types"] == ["무기", "방어구", "악세사리", "소비", "재료"]
    for k in ("env_types", "vfx_types", "ui_types"):
        assert p["type_lists"][k]  # 대상별 종류 목록 존재
    assert "일반" in p["rarities"] and "무아" in p["rarities"]
    subs = {s["key"]: s for s in p["subjects"]}
    assert subs["item"]["role_preset"] == "item_types" and subs["item"]["rarities"] is True
    assert subs["vfx"]["role_preset"] == "vfx_types" and subs["vfx"]["rarities"] is True
    assert subs["environment"]["rarities"] is False and subs["ui"]["rarities"] is False


def test_vfx_art_generates_per_rarity(settings):
    # 특수효과도 등급 축: 선택한 등급마다 차등 이펙트 1장씩
    req = GenerationRequest(subject="vfx", genre="fantasy", role="화염",
                            assets=["vfx_art"], rarities=["일반", "무아"])
    res = pipeline.run_pipeline(req, settings, "job_vfx_rar")
    arts = [a for a in res.assets if a.kind == "vfx_art"]
    assert len(arts) == 2


@pytest.mark.parametrize("subject", ["environment", "vfx", "ui"])
def test_object_subjects_no_bio(settings, subject):
    # 나머지 사물/디자인 대상도 캐릭터 기획 없이 해당 산출물만
    req = GenerationRequest(subject=subject, genre="fantasy", role="테스트")
    res = pipeline.run_pipeline(req, settings, f"job_{subject}")
    assert res.concept.stats == [] and res.concept.personality == ""
    assert res.concept.entity_type == subject
    assert res.assets  # 산출물이 생성됨


def test_pipeline_animation_makes_sheet_and_gif(settings):
    # 대기 애니메이션은 프레임 + 스트립 시트 + GIF 를 자동 생성
    req = GenerationRequest(entity_type="character", name="애니테스트",
                            assets=["anim_idle"], variant_count=3)
    res = pipeline.run_pipeline(req, settings, "job_anim")
    kinds = {a.kind for a in res.assets}
    assert "anim_idle_sheet" in kinds and "anim_idle_gif" in kinds
    gif = next(a for a in res.assets if a.kind == "anim_idle_gif")
    assert (settings.output_path / gif.path).exists()


def test_invalid_subject_rejected():
    # subject 는 허용값 5종만 (잘못된 값은 조용히 캐릭터로 처리되지 않음)
    with pytest.raises(Exception):
        GenerationRequest(subject="bogus", genre="fantasy")


def test_require_local_blocks_non_loopback():
    # 로컬 전용 제어 엔드포인트는 루프백이 아니면 403
    from fastapi.testclient import TestClient
    from app.main import app
    r = TestClient(app).post("/api/open/anything")
    assert r.status_code == 403


def test_index_injects_cache_busting_version():
    # 정적 파일에 ?v= 버전이 붙어 업데이트 후 브라우저가 최신을 받도록 함
    from fastapi.testclient import TestClient
    from app.main import app
    html = TestClient(app).get("/").text
    assert 'src="/app.js?v=' in html
    assert 'href="/style.css?v=' in html


def test_download_missing_returns_404():
    # 없는 잡/파일 다운로드는 404 (경로 방어 _safe_path 경유)
    from fastapi.testclient import TestClient
    from app.main import app
    r = TestClient(app).get("/api/download/does-not-exist/none.png")
    assert r.status_code == 404


def test_vfx_in_catalog_and_no_video_bgm():
    payload = cat.catalog_payload()
    keys = {a["key"] for a in payload["assets"]}
    assert {"vfx_element", "vfx_skill", "vfx_hit"} <= keys
    assert "vfx" in payload["categories"]
    # 영상·BGM 은 세트 제작에서 제외(카탈로그에 없어 선택 불가) — 시트만 유지
    assert "video" not in keys and "bgm" not in keys
    assert "sheet" in keys
    # VFX 는 컷아웃(투명) 대상 + 가변
    assert cat.CATALOG["vfx_element"].cutout is True
    assert cat.CATALOG["vfx_element"].variable is True


def test_bgm_generation_makes_valid_wav(tmp_path):
    import wave
    from app.models import EntityConcept
    from app.services import bgm_service
    concept = EntityConcept(name="아리아", title="현자", genre="fantasy",
                            role="마법사", tagline="", appearance="", personality="",
                            backstory="")
    wav = tmp_path / "bgm.wav"
    brief = tmp_path / "bgm.txt"
    ok = bgm_service.generate_bgm(concept, wav, brief, "fantasy")
    assert ok and wav.exists() and brief.exists()
    with wave.open(str(wav)) as w:
        assert w.getframerate() == 22050
        assert w.getnframes() > 22050  # 1초 이상
    assert "BPM" in brief.read_text(encoding="utf-8")


def test_pipeline_vfx_assets(settings):
    req = GenerationRequest(entity_type="character", name="이펙트", role="마법사",
                            genre="fantasy", assets=["vfx_element"], variant_count=3)
    res = pipeline.run_pipeline(req, settings, "seed_20260711-150000")
    kinds = {a.kind for a in res.assets}
    assert "vfx_element" in kinds  # 이미지 변형
    assert len([a for a in res.assets if a.kind == "vfx_element"]) == 3


def test_video_bgm_blocked_from_selection(settings):
    # 영상·BGM 은 선택해도 카탈로그에 없어 산출물이 생성되지 않음(코드선 차단)
    req = GenerationRequest(entity_type="character", name="차단테스트",
                            assets=["video", "bgm"])
    res = pipeline.run_pipeline(req, settings, "seed_block")
    kinds = {a.kind for a in res.assets}
    assert "video" not in kinds
    assert "bgm" not in kinds and "bgm_guide" not in kinds


def test_default_keys_present_for_each_entity():
    for entity in cat.ENTITY_TYPES:
        keys = cat.default_keys(entity)
        assert keys, f"{entity} 기본 에셋 없음"
        valid = {s.key for s in cat.specs_for_entity(entity)}
        assert set(keys) <= valid


# ── 모델 상속 ─────────────────────────────────────────────
def test_model_inheritance_shares_fields():
    # GenBase 공통 필드가 두 요청 모델에 모두 존재
    for field in ("genre", "art_style", "assets", "variant_count", "progress_id"):
        assert field in GenerationRequest.model_fields
        assert field in BatchRequest.model_fields
    # 오버라이드: BatchRequest 의 entity_type 기본값은 monster
    assert BatchRequest().entity_type == "monster"
    assert GenerationRequest().entity_type == "character"
    assert issubclass(GenerationRequest, GenBase)
    assert issubclass(BatchRequest, GenBase)


# ── 슬러그 / 경로 안전 ────────────────────────────────────
def test_slug_keeps_korean_strips_specials():
    from app.main import _slug
    assert _slug("권사 #1!") == "권사-1"
    assert _slug("") == "untitled"
    assert _slug("../../etc") != "../../etc"  # 특수문자 제거됨


def test_safe_path_blocks_traversal(tmp_path):
    from app.main import _safe_path
    root = tmp_path
    (root / "ok.txt").write_text("x")
    # 정상
    assert _safe_path(root, "ok.txt").name == "ok.txt"
    # 탈출 시도 → 404
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        _safe_path(root, "../secret")


# ── 이미지 후처리 ─────────────────────────────────────────
def test_flood_alpha_makes_corners_transparent():
    img = Image.new("RGB", (120, 120), (255, 255, 255))
    from PIL import ImageDraw
    ImageDraw.Draw(img).ellipse([40, 40, 80, 80], fill=(200, 30, 30))
    out = imageops.flood_alpha(img)
    assert out.mode == "RGBA"
    assert out.getpixel((0, 0))[3] == 0        # 모서리 투명
    assert out.getpixel((60, 60))[3] == 255    # 중앙 불투명


def test_make_tileable_preserves_size():
    img = Image.new("RGB", (64, 64), (100, 120, 140))
    out = imageops.make_tileable(img)
    assert out.size == (64, 64)


def test_rarity_frame_draws_border_high_tier(tmp_path):
    # 고등급은 가장자리에 등급색 테두리가 그려지고 크기는 그대로
    src = tmp_path / "art.png"
    Image.new("RGB", (200, 200), (20, 20, 20)).save(src)
    imageops.apply_rarity_frame(src, "전설")  # 금색 프레임
    out = Image.open(src)
    assert out.size == (200, 200)
    r, g, bl = out.getpixel((0, 0))[:3]
    assert r > 120 and g > 90 and bl < 120  # 금빛 테두리(원본 어두운색 아님)


def test_rarity_frame_common_no_change(tmp_path):
    # '일반'은 프레임 없음(원본 유지)
    src = tmp_path / "art2.png"
    Image.new("RGB", (100, 100), (30, 30, 30)).save(src)
    imageops.apply_rarity_frame(src, "일반")
    assert Image.open(src).getpixel((0, 0))[:3] == (30, 30, 30)


def test_subtypes_cover_item_env_ui_vfx():
    p = cat.catalog_payload()
    st = p["subtypes"]
    assert st["무기"][0] == "장검"          # 아이템
    assert "보스방" in st["던전"]           # 환경
    assert "버튼" in st["다크 판타지"]       # UI
    assert "화염구" in st["화염"]           # 특수효과
    assert p["rarity_colors"]["전설"] == "#f0be3c"  # 등급 배지색


def test_item_art_asset_carries_rarity_variant(settings):
    # 결과 카드 배지용: 등급 축 에셋은 variant(등급)를 담는다
    req = GenerationRequest(subject="item", genre="fantasy", role="장검",
                            assets=["item_art"], rarities=["전설", "극"])
    res = pipeline.run_pipeline(req, settings, "job_badge")
    variants = {a.variant for a in res.assets if a.kind == "item_art"}
    assert variants == {"전설", "극"}


def test_breathe_keeps_size_and_bottom(tmp_path):
    # 호흡 프레임은 크기가 그대로여야 하고(흔들림 방지), 발(하단)은 고정
    src = tmp_path / "base.png"
    img = Image.new("RGB", (80, 100), (20, 20, 20))
    from PIL import ImageDraw
    ImageDraw.Draw(img).rectangle([0, 90, 79, 99], fill=(200, 50, 50))  # 하단 띠
    img.save(src)
    dst = tmp_path / "f.png"
    imageops.breathe(src, dst, phase=0.5)  # 최대 확장 지점
    out = Image.open(dst)
    assert out.size == (80, 100)                    # 크기 동일
    assert out.getpixel((40, 99))[0] > 150          # 하단 띠 유지(발 고정)


def test_idle_animation_frames_uniform_size(settings, tmp_path):
    # 대기 애니메이션 5프레임은 모두 동일 크기여야 함(1장만 작던 문제 회귀 방지)
    from app.services import gemini_service
    from app.models import EntityConcept
    concept = EntityConcept(name="파수병", title="", genre="fantasy", role="기사",
                            tagline="", appearance="", personality="", backstory="")
    res = gemini_service.generate_asset(
        cat.CATALOG["anim_idle"], concept, tmp_path, settings, variant_count=5)
    assert len(res) == 5
    sizes = {Image.open(r.path).size for r in res}
    assert len(sizes) == 1  # 모든 프레임 크기 동일


def test_tile_preview_file(tmp_path):
    src = tmp_path / "tile.png"
    Image.new("RGB", (48, 48), (30, 60, 90)).save(src)
    out = tmp_path / "prev.png"
    res = imageops.tile_preview_file(src, out, 3)
    assert res and out.exists()
    prev = Image.open(out)
    assert prev.size[0] >= 48 and prev.size[1] >= 48


# ── 파이프라인 (데모 모드) ────────────────────────────────
def test_pipeline_demo_generates_assets(settings):
    req = GenerationRequest(
        entity_type="character", name="테스트영웅", role="기사",
        assets=["portrait", "fullbody", "emblem", "sheet"], variant_count=3,
    )
    res = pipeline.run_pipeline(req, settings, "job_test")
    kinds = {a.kind for a in res.assets}
    assert "portrait" in kinds
    assert "sheet_png" in kinds
    assert res.concept.name  # 기획서 생성됨
    # 저장 경로는 대분류(캐릭터)/중분류(직업)/장르_이름_날짜 로 재구성됨
    assert res.job_id.startswith("캐릭터/기사/")
    assert "판타지_테스트영웅_" in res.job_id
    assert (settings.output_path / res.job_id / "result.json").exists()


def test_object_folder_nested_by_subject_and_type(settings):
    # 사물 대상: 대분류(아이템)/중분류(종류)/… 로 저장
    req = GenerationRequest(subject="item", genre="fantasy", role="장검",
                            type_group="무기", assets=["item_art"], rarities=["일반"])
    res = pipeline.run_pipeline(req, settings, "seed_20260711-160000")
    assert res.job_id.startswith("아이템/무기/")
    assert (settings.output_path / res.job_id / "result.json").exists()


def test_proportion_keyword_normalized():
    from app.services.gpt_service import _normalize_proportion
    # 'N등신'(몸 비율)이 '머리 N개'로 오해되지 않도록 영어 비율로 변환
    out = _normalize_proportion("붉은 갑옷, 5등신")
    assert "등신" not in out
    assert "one head" in out and "5" in out
    # 소수 등신도 처리
    assert "7.5" in _normalize_proportion("7.5등신")
    # 등신이 없으면 원문 유지
    assert _normalize_proportion("푸른 머리") == "푸른 머리"


def test_art_style_injected_and_saved(settings):
    import json
    req = GenerationRequest(entity_type="character", name="스타일", role="저격수",
                            genre="sci-fi", art_style="pixel art", assets=["portrait"])
    res = pipeline.run_pipeline(req, settings, "seed_20260711-170000")
    # 선택한 아트 스타일이 concept 에 반영되고 concept.json 에 저장됨(재생성에서 재사용)
    assert res.concept.art_style == "pixel art"
    cj = json.loads((settings.output_path / res.job_id / "concept.json").read_text(encoding="utf-8"))
    assert cj.get("art_style") == "pixel art"


def test_pipeline_transparent_cutout(settings):
    req = GenerationRequest(
        entity_type="character", name="컷아웃", role="도적",
        assets=["portrait", "emblem"], variant_count=1, transparent=True,
    )
    res = pipeline.run_pipeline(req, settings, "job_cut")
    assert res.assets


def test_batch_pipeline_demo(settings):
    req = BatchRequest(entity_type="monster", genre="fantasy", count=2,
                       assets=["portrait"], variant_count=1, make_codex=True)
    res = pipeline.run_batch(req, settings, "batch_test")
    assert len(res.entries) == 2
    assert res.codex is not None


# ── 재생성 ────────────────────────────────────────────────
def test_regenerate_asset(settings):
    req = GenerationRequest(entity_type="character", name="재생성", role="궁수",
                            assets=["portrait", "emblem"], variant_count=2)
    res = pipeline.run_pipeline(req, settings, "job_regen")
    rr = RegenerateRequest(asset_key="emblem", variant_count=2)
    new = pipeline.regenerate_asset(rr, settings, res.job_id)
    assert new and all(a.kind == "emblem" for a in new)


def test_repack_variants_keeps_selected(settings):
    import json
    req = GenerationRequest(entity_type="character", name="재패킹", role="전사",
                            assets=["expressions"], variant_count=5, sprite_sheet=True)
    res = pipeline.run_pipeline(req, settings, "job_repack")
    job_dir = settings.output_path / res.job_id
    import re
    numbered = re.compile(r"expressions_\d+\.png$")
    before = sorted(f.name for f in job_dir.glob("expressions_*.png") if numbered.match(f.name))
    assert len(before) == 5
    keep = ["expressions_1.png", "expressions_3.png", "expressions_5.png"]
    out = pipeline.repack_variants(
        RepackRequest(asset_key="expressions", keep=keep), settings, res.job_id)
    assert len(out["kept"]) == 3
    assert set(out["dropped"]) == {"expressions_2.png", "expressions_4.png"}
    after = sorted(f.name for f in job_dir.glob("expressions_*.png") if numbered.match(f.name))
    assert after == keep
    data = json.loads((job_dir / "result.json").read_text(encoding="utf-8"))
    expr = sorted(a["path"].split("/")[-1] for a in data["assets"]
                  if a["kind"] == "expressions")
    assert expr == keep


def test_repack_requires_one_kept(settings):
    req = GenerationRequest(entity_type="character", name="x", role="전사",
                            assets=["expressions"], variant_count=3)
    res = pipeline.run_pipeline(req, settings, "job_rp2")
    with pytest.raises(ValueError):
        pipeline.repack_variants(
            RepackRequest(asset_key="expressions", keep=[]), settings, res.job_id)


def test_regenerate_rejects_non_image(settings):
    req = GenerationRequest(entity_type="character", name="x", role="전사",
                            assets=["portrait"], variant_count=1)
    res = pipeline.run_pipeline(req, settings, "job_x")
    with pytest.raises(ValueError):
        pipeline.regenerate_asset(RegenerateRequest(asset_key="sheet"), settings, res.job_id)


# ── 진행률 / 취소 ─────────────────────────────────────────
def test_progress_lifecycle():
    progress.start("t1", 3, "시작")
    progress.advance("t1")
    snap = progress.snapshot("t1")
    assert snap["current"] == 1 and snap["total"] == 3
    progress.finish("t1")
    assert progress.snapshot("t1")["done"] is True


def test_cancel_raises_check():
    progress.start("t2", 5)
    assert progress.cancel("t2") is True
    with pytest.raises(progress.Cancelled):
        progress.check("t2")


def test_progress_empty_id_is_noop():
    # 빈 progress_id 는 조용히 무시 (배치 하위 파이프라인)
    progress.start("", 3)
    progress.advance("")
    assert progress.snapshot("") is None
    assert progress.is_cancelled("") is False


# ── 예산 / 비용 상한 ──────────────────────────────────────
def test_budget_defaults_and_set(tmp_path, monkeypatch):
    from app import runtime
    monkeypatch.setattr(runtime, "_FILE", tmp_path / "rc.json")
    d = runtime.get_budget()
    assert set(d) == {"confirm_threshold", "per_run_limit", "monthly_limit"}
    saved = runtime.set_budget({"confirm_threshold": 1.5, "per_run_limit": 3, "monthly_limit": 40})
    assert saved["confirm_threshold"] == 1.5
    assert runtime.get_budget()["monthly_limit"] == 40.0


def test_budget_set_ignores_bad_values(tmp_path, monkeypatch):
    from app import runtime
    monkeypatch.setattr(runtime, "_FILE", tmp_path / "rc.json")
    runtime.set_budget({"per_run_limit": 5})
    # 잘못된 값/음수는 무시 또는 0 하한
    saved = runtime.set_budget({"per_run_limit": "abc", "monthly_limit": -10})
    assert saved["per_run_limit"] == 5.0        # 기존값 유지
    assert saved["monthly_limit"] == 0.0        # 음수는 0 하한


# ── CSV 가져오기 ──────────────────────────────────────────
def test_importer_parses_and_analyzes_template():
    from app.services import importer
    rows = importer.parse_upload("t.csv", importer.TEMPLATE_CSV.encode("utf-8"))
    assert len(rows) == 4
    res = importer.analyze(rows)
    plans = res["plans"]
    # 1행: 캐릭터 rpg → rpg 번들
    assert plans[0]["entity_type"] == "character"
    assert "portrait" in plans[0]["assets"] and "sheet" in plans[0]["assets"]
    # 2행: 몬스터 도감 번들
    assert plans[1]["entity_type"] == "monster"
    assert plans[1]["assets"] == ["portrait", "fullbody", "emblem", "sheet"]
    # 3행: 직접 지정 에셋 우선
    assert set(plans[2]["assets"]) == {"portrait", "namecard", "emote"}
    # 4행: 2d → 애니 번들
    assert "pixel_sprite" in plans[3]["assets"]
    assert plans[3]["transparent"] is True


def test_importer_purpose_bundles_and_unknown():
    from app.services import importer
    rows = [{"entity_type": "캐릭터", "role": "전사", "purpose": "카드"},
            {"entity_type": "monster", "purpose": "존재하지않음"}]
    plans = importer.analyze(rows)["plans"]
    assert "card_frame" in plans[0]["assets"]
    # 알 수 없는 용도 → 기본 세트 + 경고
    assert plans[1]["assets"] == ["portrait", "fullbody", "sheet"]
    assert any("알 수 없는 용도" in w for w in plans[1]["warnings"])


def test_importer_korean_labels_and_entity_alias():
    from app.services import importer
    rows = [{"entity_type": "몬스터", "genre": "판타지", "assets": "초상화;전신"}]
    plans = importer.analyze(rows)["plans"]
    assert plans[0]["entity_type"] == "monster"
    assert plans[0]["genre"] == "fantasy"
    assert plans[0]["assets"] == ["portrait", "fullbody"]


def test_import_run_generates_independent_jobs(settings):
    from app.services import importer
    rows_raw = importer.parse_upload("t.csv", importer.TEMPLATE_CSV.encode("utf-8"))
    plans = importer.analyze(rows_raw)["plans"][:2]
    reqs = [GenerationRequest(
        entity_type=p["entity_type"], name=p["name"], role=p["role"],
        genre=p["genre"], art_style=p["art_style"], keywords=p["keywords"],
        assets=p["assets"], variant_count=p["variant_count"],
        image_scale=p["image_scale"], transparent=p["transparent"]) for p in plans]
    job_ids = [f"imp_{i}_20260711-130000" for i in range(len(reqs))]
    results = pipeline.run_import(reqs, settings, job_ids)
    assert len(results) == 2
    # 각 행은 장르_직업_캐릭명_날짜 로 재구성된 독립 잡 폴더로 생성됨
    for res in results:
        assert (settings.output_path / res.job_id / "result.json").exists()
        assert res.job_id.count("/") == 2  # 대분류/중분류/폴더


# ── 이미지 편집 ───────────────────────────────────────────
def test_editor_crop_bg_adjust(tmp_path):
    from app.services import editor
    p = tmp_path / "e.png"
    Image.new("RGB", (400, 300), (120, 60, 200)).save(p)
    # 크롭: 중앙 절반
    size = editor.apply_edit(p, crop={"l": 0.25, "t": 0.25, "r": 0.75, "b": 0.75})
    assert size == (200, 150)
    # 밝기 1.5배
    Image.new("RGB", (40, 40), (100, 100, 100)).save(p)
    editor.apply_edit(p, brightness=1.5)
    assert Image.open(p).getpixel((0, 0))[0] == 150


def test_editor_bg_flatten_transparent(tmp_path):
    from app.services import editor
    p = tmp_path / "t.png"
    Image.new("RGBA", (60, 60), (0, 0, 0, 0)).save(p)
    editor.apply_edit(p, bg="#ffffff")
    out = Image.open(p)
    assert out.mode == "RGB"
    assert out.getpixel((5, 5)) == (255, 255, 255)


def test_editor_tiny_crop_ignored(tmp_path):
    from app.services import editor
    p = tmp_path / "s.png"
    Image.new("RGB", (100, 100), (10, 20, 30)).save(p)
    # 4px 미만 크롭은 무시 → 원본 크기 유지
    size = editor.apply_edit(p, crop={"l": 0.5, "t": 0.5, "r": 0.51, "b": 0.51})
    assert size == (100, 100)


def test_spend_ledger_accumulates(tmp_path, monkeypatch):
    from app import runtime
    monkeypatch.setattr(runtime, "_FILE", tmp_path / "rc.json")
    assert runtime.get_month_spend("2026-07") == 0.0
    runtime.add_spend("2026-07", 0.5)
    runtime.add_spend("2026-07", 0.25)
    runtime.add_spend("2026-07", 0.0)   # 데모(0)는 무시
    assert runtime.get_month_spend("2026-07") == 0.75
    assert runtime.get_month_spend("2026-08") == 0.0  # 월 분리
