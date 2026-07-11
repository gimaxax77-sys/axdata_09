"""CapCut 영상 서비스.

두 가지 산출물을 만든다:

1. CapCut draft 프로젝트 — pyJianYingDraft 가 설치되어 있으면 CapCut 앱에서
   바로 열 수 있는 네이티브 draft 를 생성한다. 없으면 동일한 타임라인 정보를
   담은 스토리보드 JSON + 에셋 + 안내 README 를 draft 폴더에 만든다.
2. 미리보기 영상 — 외부 도구 없이 Pillow 만으로 Ken Burns(줌/팬) 슬라이드쇼
   애니메이션 GIF 를 생성한다. ffmpeg/moviepy 가 있으면 MP4 로도 내보낸다.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw

from ..models import CharacterConcept
from .fonts import load_font


# ─────────────────────────────────────────────────────────────────────
# 스토리보드 (씬 구성) — CapCut draft 와 미리보기 영상이 공유
# ─────────────────────────────────────────────────────────────────────
def build_storyboard(concept: CharacterConcept, images: dict[str, Path]) -> list[dict]:
    scenes = []
    if images.get("portrait"):
        scenes.append({
            "image": "portrait.png",
            "duration": 3.0,
            "transition": "fade",
            "effect": "zoom_in",
            "title": concept.name,
            "subtitle": concept.title or concept.role,
        })
    if images.get("fullbody"):
        scenes.append({
            "image": "fullbody.png",
            "duration": 3.0,
            "transition": "slide_left",
            "effect": "pan_up",
            "title": "외형",
            "subtitle": (concept.tagline or concept.appearance)[:40],
        })
    if images.get("icon"):
        scenes.append({
            "image": "icon.png",
            "duration": 2.5,
            "transition": "fade",
            "effect": "zoom_out",
            "title": "능력",
            "subtitle": " · ".join(concept.abilities[:3]),
        })
    if images.get("portrait"):
        scenes.append({
            "image": "portrait.png",
            "duration": 3.0,
            "transition": "fade",
            "effect": "zoom_in",
            "title": concept.name,
            "subtitle": f"{concept.genre} · {concept.role}",
        })
    return scenes


# ─────────────────────────────────────────────────────────────────────
# CapCut draft 생성
# ─────────────────────────────────────────────────────────────────────
def build_capcut_draft(
    concept: CharacterConcept,
    images: dict[str, Path],
    draft_dir: Path,
    storyboard: list[dict],
) -> tuple[Path, bool]:
    """CapCut draft 폴더를 만든다. 네이티브 draft 면 True, 스토리보드면 False."""
    draft_dir.mkdir(parents=True, exist_ok=True)

    # 에셋 복사
    assets_dir = draft_dir / "assets"
    assets_dir.mkdir(exist_ok=True)
    for kind, path in images.items():
        if path and path.exists():
            shutil.copy(path, assets_dir / path.name)

    try:
        import pyJianYingDraft  # noqa: F401

        native = _build_native_draft(concept, assets_dir, draft_dir, storyboard)
        if native:
            return draft_dir, True
    except Exception as exc:  # pragma: no cover - optional dependency
        print(f"[capcut_service] 네이티브 draft 생략({exc}); 스토리보드로 대체")

    # 스토리보드 JSON + README
    storyboard_doc = {
        "project": f"{concept.name} 캐릭터 쇼케이스",
        "resolution": {"width": 1080, "height": 1920},
        "fps": 30,
        "character": {
            "name": concept.name,
            "title": concept.title,
            "genre": concept.genre,
            "role": concept.role,
        },
        "scenes": storyboard,
        "bgm_suggestion": _bgm_hint(concept.genre),
    }
    (draft_dir / "capcut_storyboard.json").write_text(
        json.dumps(storyboard_doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (draft_dir / "README.txt").write_text(_draft_readme(concept), encoding="utf-8")
    return draft_dir, False


def _build_native_draft(concept, assets_dir, draft_dir, storyboard) -> bool:
    """pyJianYingDraft 로 네이티브 CapCut draft 생성.

    라이브러리 API 는 버전마다 다르므로 방어적으로 시도하고,
    실패하면 False 를 반환해 스토리보드 폴백으로 넘긴다.
    """
    import pyJianYingDraft as draft
    from pyJianYingDraft import trange

    script = draft.Script_file(1080, 1920)
    script.add_track(draft.Track_type.video)

    t = 0.0
    for scene in storyboard:
        img_path = assets_dir / scene["image"]
        if not img_path.exists():
            continue
        material = draft.Video_material(str(img_path))
        script.add_material(material)
        seg = draft.Video_segment(
            material,
            trange(f"{t}s", f"{scene['duration']}s"),
        )
        script.add_segment(seg)
        t += scene["duration"]

    script.dump(str(draft_dir / "draft_content.json"))
    return True


# ─────────────────────────────────────────────────────────────────────
# 미리보기 영상 (Pillow → GIF, 선택적 MP4)
# ─────────────────────────────────────────────────────────────────────
def build_preview_video(
    concept: CharacterConcept,
    images: dict[str, Path],
    storyboard: list[dict],
    out_gif: Path,
    out_mp4: Path | None = None,
    *,
    fps: int = 12,
    canvas: tuple[int, int] = (720, 1280),
) -> tuple[Path, Path | None]:
    """Ken Burns 슬라이드쇼 애니메이션을 만든다. (gif_path, mp4_path|None)."""
    frames: list[Image.Image] = []
    accent = _accent(concept)

    for scene in storyboard:
        img_path = _resolve_scene_image(scene, images)
        if not img_path or not img_path.exists():
            continue
        base = Image.open(img_path).convert("RGB")
        n = max(1, int(scene["duration"] * fps))
        for i in range(n):
            p = i / max(1, n - 1)
            frame = _ken_burns_frame(base, canvas, scene["effect"], p, accent)
            _overlay_text(frame, scene.get("title", ""), scene.get("subtitle", ""),
                          accent, fade=_fade_alpha(p))
            frames.append(frame)

    if not frames:  # 이미지가 하나도 없을 때 대비
        frames = [Image.new("RGB", canvas, (18, 16, 28))]

    out_gif.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        out_gif, save_all=True, append_images=frames[1:],
        duration=int(1000 / fps), loop=0, optimize=True,
    )

    mp4_path = None
    if out_mp4 is not None:
        mp4_path = _try_mp4(frames, out_mp4, fps)

    return out_gif, mp4_path


def _try_mp4(frames, out_mp4: Path, fps: int) -> Path | None:
    """imageio(+ffmpeg) 가 있으면 MP4 로 내보낸다. 없으면 None."""
    try:
        import imageio.v2 as imageio  # type: ignore

        writer = imageio.get_writer(str(out_mp4), fps=fps, codec="libx264",
                                    quality=8, macro_block_size=None)
        for f in frames:
            writer.append_data(_to_array(f))
        writer.close()
        return out_mp4
    except Exception as exc:  # pragma: no cover - optional dependency
        print(f"[capcut_service] MP4 생략(ffmpeg/imageio 없음): {exc}")
        return None


def _to_array(img: Image.Image):
    import numpy as np  # type: ignore

    return np.asarray(img)


# ── Ken Burns & 오버레이 ──────────────────────────────────────────────
def _ken_burns_frame(base, canvas, effect, p, accent) -> Image.Image:
    cw, ch = canvas
    # 캔버스를 덮도록 크게 리사이즈
    iw, ih = base.size
    cover = max(cw / iw, ch / ih) * 1.25
    bw, bh = int(iw * cover), int(ih * cover)
    big = base.resize((bw, bh), Image.LANCZOS)

    zoom = 1.0 + 0.12 * (p if "in" in effect else (1 - p) if "out" in effect else 0)
    vw, vh = int(cw / zoom), int(ch / zoom)

    if effect == "pan_up":
        oy = int((bh - vh) * (1 - p))
    elif effect == "pan_down":
        oy = int((bh - vh) * p)
    else:
        oy = (bh - vh) // 2
    ox = (bw - vw) // 2
    ox = max(0, min(ox, bw - vw))
    oy = max(0, min(oy, bh - vh))

    crop = big.crop((ox, oy, ox + vw, oy + vh)).resize((cw, ch), Image.LANCZOS)

    # 하단 그라데이션(자막 가독성)
    grad = Image.new("L", (1, ch), 0)
    for y in range(ch):
        t = max(0.0, (y / ch - 0.55) / 0.45)
        grad.putpixel((0, y), int(180 * t))
    grad = grad.resize((cw, ch))
    dark = Image.new("RGB", (cw, ch), (10, 8, 18))
    crop = Image.composite(dark, crop, grad)
    return crop


def _overlay_text(frame, title, subtitle, accent, fade=255) -> None:
    if not title and not subtitle:
        return
    draw = ImageDraw.Draw(frame, "RGBA")
    cw, ch = frame.size
    f_title = load_font(int(cw * 0.075), bold=True)
    f_sub = load_font(int(cw * 0.042))

    y = int(ch * 0.80)
    # 액센트 바
    draw.rounded_rectangle([int(cw * 0.08), y, int(cw * 0.08) + 60, y + 8],
                           radius=4, fill=(*accent, fade))
    y += 24
    if title:
        draw.text((int(cw * 0.08), y), title, font=f_title, fill=(255, 255, 255, fade))
        y += f_title.size + 10
    if subtitle:
        draw.text((int(cw * 0.08), y), subtitle, font=f_sub, fill=(220, 216, 230, fade))


def _fade_alpha(p: float) -> int:
    if p < 0.12:
        return int(255 * p / 0.12)
    if p > 0.88:
        return int(255 * (1 - p) / 0.12)
    return 255


def _resolve_scene_image(scene, images) -> Path | None:
    name = scene["image"].replace(".png", "")
    return images.get(name)


def _accent(concept: CharacterConcept) -> tuple[int, int, int]:
    palette = concept.color_palette
    hexc = palette[2] if len(palette) > 2 else (palette[0] if palette else "#C89B3C")
    h = hexc.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore
    except ValueError:
        return (200, 155, 60)


def _bgm_hint(genre: str) -> str:
    return {
        "fantasy": "웅장한 오케스트라 / 에픽 트레일러 BGM",
        "sci-fi": "신스웨이브 / 앰비언트 일렉트로닉",
        "cyberpunk": "다크 신스웨이브 / 인더스트리얼 비트",
    }.get(genre.lower(), "에픽 트레일러 BGM")


def _draft_readme(concept: CharacterConcept) -> str:
    return (
        f"{concept.name} — CapCut 쇼케이스 draft\n"
        "====================================\n\n"
        "이 폴더에는 CapCut 편집을 위한 스토리보드와 에셋이 들어 있습니다.\n\n"
        "[사용법]\n"
        "1. assets/ 폴더의 이미지를 CapCut 타임라인에 순서대로 올립니다.\n"
        "2. capcut_storyboard.json 의 scenes 순서/길이/전환/효과를 참고해\n"
        "   각 클립에 전환(transition)과 애니메이션(effect)을 적용합니다.\n"
        "3. bgm_suggestion 을 참고해 배경음악을 추가합니다.\n"
        "4. title/subtitle 을 자막으로 넣으면 미리보기 영상과 동일한 구성이 됩니다.\n\n"
        "* pyJianYingDraft 를 설치하면(requirements.txt 주석 참고) 이 폴더에\n"
        "  draft_content.json 이 함께 생성되어 CapCut 에서 바로 열 수 있습니다.\n"
    )
