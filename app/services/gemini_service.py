"""Gemini 서비스 — 임의 아트 에셋 이미지 생성.

google-genai SDK 로 Gemini 이미지 모델(Nano Banana)을 호출한다.
GEMINI_API_KEY 가 없거나 호출이 실패하면 Pillow 로 카테고리별
플레이스홀더 이미지를 생성한다(데모 모드).

이미지 후처리(배경 제거/타일러블/리사이즈)는 `imageops`,
플레이스홀더 드로잉은 `placeholders` 모듈로 분리했다.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image

from ..config import Settings
from ..logging_config import get_logger
from ..models import EntityConcept
from . import asset_catalog as cat
from . import imageops, placeholders

# 후처리 함수는 파이프라인/스모크 테스트가 gemini_service 경유로 호출할 수 있어
# 하위 호환 별칭으로 재노출한다.
from .imageops import (  # noqa: F401
    apply_tileable,
    make_transparent as _make_transparent,
    remove_background,
    tile_preview_file,
)

log = get_logger(__name__)


@dataclass
class ImageResult:
    path: Path
    label: str
    demo: bool
    variant: str = ""


# ─────────────────────────────────────────────────────────────────────
# SDK 클라이언트 캐싱 (키별 1회 생성 — 배치/다변형 시 재생성 낭비 방지)
# ─────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=4)
def _gemini_client(api_key: str):
    # 일부 환경은 cryptography rust 바인딩 문제로 import 시 pyo3 PanicException
    # (BaseException 계열)을 던진다. 일반 예외로 변환해 데모 폴백이 되도록 한다.
    try:
        from google import genai
    except BaseException as exc:  # noqa: BLE001
        raise RuntimeError(f"google-genai import 실패: {exc}") from None
    return genai.Client(api_key=api_key)


@lru_cache(maxsize=4)
def _openai_client(api_key: str):
    from openai import OpenAI
    return OpenAI(api_key=api_key)


# ─────────────────────────────────────────────────────────────────────
# 공개 API
# ─────────────────────────────────────────────────────────────────────
def generate_asset(
    spec: cat.AssetSpec,
    concept: EntityConcept,
    job_dir: Path,
    settings: Settings,
    scale: float = 1.0,
    variant_count: int = 5,
    reference: "Image.Image | None" = None,
    style_only: bool = False,
    transparent: bool = False,
    model: str = "",
) -> list[ImageResult]:
    """스펙 하나에 대한 이미지(들)를 생성. 다변형이면 여러 장.

    reference: 앵커 이미지(image-to-image). style_only=False 면 동일 캐릭터
        유지(정체성), True 면 아트 스타일/팔레트만 참조(스타일 락).
    transparent: 컷아웃 에셋이면 배경 제거해 알파 PNG 로 저장.
    model: 이미지 모델 오버라이드(빈 값이면 서버 기본).
    """
    variants = spec.resolve_variants(variant_count)
    multi = len(variants) > 1
    w, h = spec.size
    size = (max(64, int(w * scale)), max(64, int(h * scale)))
    use_ref = reference
    do_cutout = transparent and spec.cutout
    results: list[ImageResult] = []
    for i, variant in enumerate(variants):
        prompt = cat.build_prompt(
            spec,
            visual=concept.visual_core,
            name=concept.name,
            style="",  # style 은 art_style 대신 visual_core 에 녹아 있음
            genre=concept.genre,
            variant=variant,
        )
        if use_ref is not None:
            if style_only:
                prompt = (
                    "Match the ART STYLE, rendering technique, and COLOR PALETTE of "
                    "the reference image (do NOT copy its subject). " + prompt
                )
            else:
                prompt = (
                    "Using the reference image as the EXACT SAME character — keep the "
                    "identical face, hairstyle, outfit, and colors. " + prompt
                )
        if do_cutout:
            prompt += ", isolated subject on a flat solid plain background"
        suffix = f"_{i+1}" if multi else ""
        out = job_dir / f"{spec.key}{suffix}.png"
        label = f"{spec.label} · {variant}" if variant else spec.label
        is_real = _generate_image(
            prompt, out, size, settings,
            placeholder=spec.placeholder,
            label=f"{concept.name}" + (f" · {variant}" if variant else f" · {spec.label}"),
            palette=concept.color_palette,
            reference=use_ref, model=model,
        )
        if do_cutout and out.exists():
            imageops.make_transparent(out)
        results.append(ImageResult(path=out, label=label, demo=not is_real, variant=variant))
    return results


def _generate_image(prompt, out_path, size, settings, *, placeholder, label, palette,
                    reference=None, model="") -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    model = model or settings.gemini_image_model

    # OpenAI 이미지 백엔드(gpt-image-1: 네이티브 투명 지원)
    if model.startswith("gpt-image"):
        if settings.gpt_enabled:
            try:
                if _generate_with_openai_image(prompt, out_path, size, settings, model):
                    return True
            except Exception as exc:  # pragma: no cover - network guard
                log.warning("OpenAI 이미지 호출 실패, 데모 폴백: %s", exc)
        placeholders.generate_placeholder(out_path, size, label, palette, placeholder)
        return False

    # 기본: Gemini
    if settings.gemini_enabled:
        try:
            if _generate_with_gemini(prompt, out_path, size, settings,
                                     reference=reference, model=model):
                return True
        except Exception as exc:  # pragma: no cover - network guard
            log.warning("Gemini 호출 실패: %s", exc)
        # 레퍼런스가 있었는데 실패/빈응답이면, 레퍼런스 없이 재시도
        # (일관성은 낮아지지만 실제 이미지를 얻는다 → 전신 등 누락 방지)
        if reference is not None:
            try:
                if _generate_with_gemini(prompt, out_path, size, settings,
                                         reference=None, model=model):
                    log.info("레퍼런스 없이 재시도 성공")
                    return True
            except Exception as exc:  # pragma: no cover
                log.warning("재시도도 실패, 데모 폴백: %s", exc)
    placeholders.generate_placeholder(out_path, size, label, palette, placeholder)
    return False


def _generate_with_openai_image(prompt, out_path, size, settings, model) -> bool:
    """OpenAI gpt-image-1 이미지 생성 (투명 배경 네이티브 지원)."""
    import base64

    client = _openai_client(settings.openai_api_key)
    # gpt-image-1 지원 크기로 매핑
    w, h = size
    ratio = w / h
    if ratio > 1.2:
        osize = "1536x1024"
    elif ratio < 0.83:
        osize = "1024x1536"
    else:
        osize = "1024x1024"
    resp = client.images.generate(
        model=model, prompt=prompt, size=osize,
        background="transparent", n=1,
    )
    b64 = resp.data[0].b64_json
    img = Image.open(imageops.as_bytesio(base64.b64decode(b64)))
    imageops.fit(img.convert("RGBA"), size).save(out_path)
    try:
        from . import usage
        usage.record_gemini_image(1)  # 이미지 카운트 공통 집계
    except Exception as exc:
        log.debug("사용량 집계 실패(무시): %s", exc)
    return True


def _generate_with_gemini(prompt, out_path, size, settings, reference=None, model="") -> bool:
    # 클라이언트는 키별로 캐시(_gemini_client)해 매 호출 재생성 낭비를 막는다.
    # types 는 매번 import 해도 저렴(모듈 캐시).
    try:
        from google.genai import types
    except BaseException as exc:  # noqa: BLE001
        raise RuntimeError(f"google-genai import 실패: {exc}") from None

    model = model or settings.gemini_image_model
    client = _gemini_client(settings.gemini_api_key)

    # 레퍼런스 이미지가 있으면 contents 에 함께 전달(image-to-image, 캐릭터 일관성)
    contents = [prompt]
    if reference is not None:
        contents = [prompt, reference]  # google-genai 는 PIL 이미지 허용

    # 이미지 출력 모델(gemini-2.5-flash-image)은 response_modalities 로 이미지
    # 응답을 명시하면 안정적이다. 구버전/미지원 시 config 없이 재시도한다.
    def _call(with_config: bool):
        if with_config:
            cfg = types.GenerateContentConfig(response_modalities=["IMAGE"])
            return client.models.generate_content(
                model=model, contents=contents, config=cfg)
        return client.models.generate_content(model=model, contents=contents)

    try:
        resp = _call(with_config=True)
    except Exception:
        resp = _call(with_config=False)

    for candidate in resp.candidates or []:
        content = getattr(candidate, "content", None)
        for part in (getattr(content, "parts", None) or []):
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                img = Image.open(imageops.as_bytesio(inline.data)).convert("RGB")
                imageops.fit(img, size).save(out_path)
                try:
                    from . import usage
                    # 정밀 집계: usage_metadata 의 입력/출력 토큰까지 기록
                    um = getattr(resp, "usage_metadata", None)
                    usage.record_gemini_image(
                        1,
                        input_tokens=getattr(um, "prompt_token_count", 0) or 0,
                        output_tokens=(getattr(um, "candidates_token_count", 0) or 0),
                    )
                except Exception as exc:
                    log.debug("Gemini 사용량 집계 실패(무시): %s", exc)
                return True
    return False
