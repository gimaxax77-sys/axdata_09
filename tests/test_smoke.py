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
from app.models import GenerationRequest, BatchRequest, RegenerateRequest, GenBase
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
    # result.json 저장 확인
    assert (settings.output_path / "job_test" / "result.json").exists()


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
    pipeline.run_pipeline(req, settings, "job_regen")
    rr = RegenerateRequest(asset_key="emblem", variant_count=2)
    new = pipeline.regenerate_asset(rr, settings, "job_regen")
    assert new and all(a.kind == "emblem" for a in new)


def test_regenerate_rejects_non_image(settings):
    req = GenerationRequest(entity_type="character", name="x", role="전사",
                            assets=["portrait"], variant_count=1)
    pipeline.run_pipeline(req, settings, "job_x")
    with pytest.raises(ValueError):
        pipeline.regenerate_asset(RegenerateRequest(asset_key="sheet"), settings, "job_x")


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
