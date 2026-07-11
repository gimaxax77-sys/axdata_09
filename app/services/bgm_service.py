"""배경음악(BGM) 생성 — 절차적 칩튠 루프 WAV + CapCut용 BGM 기획서.

CapCut 은 공개 오디오 생성 API 가 없으므로, 여기서는 (1) 실제 재생 가능한
짧은 루프 음원을 순수 파이썬(stdlib wave)으로 만들고, (2) CapCut 음악
라이브러리에서 어울리는 곡을 고르도록 분위기·BPM·검색 키워드를 담은
기획서를 함께 생성한다.
"""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from ..logging_config import get_logger
from ..models import EntityConcept

log = get_logger(__name__)

_SR = 22050  # 샘플레이트

# 장르 → 음악 성격 (스케일 반음 간격, BPM, 분위기, 악기, CapCut 검색어)
_GENRE_MUSIC = {
    "fantasy": {"scale": [0, 2, 3, 5, 7, 8, 10], "root": 220.0, "bpm": 100,
                "mood": "웅장하고 서정적인 판타지", "inst": "오케스트라 현악·하프·혼",
                "keywords": ["epic fantasy", "orchestral adventure", "cinematic"]},
    "sci-fi": {"scale": [0, 2, 4, 6, 7, 9, 11], "root": 262.0, "bpm": 118,
               "mood": "미래적이고 광활한 SF", "inst": "신스 패드·아르페지에이터",
               "keywords": ["sci-fi ambient", "space synth", "futuristic"]},
    "cyberpunk": {"scale": [0, 2, 3, 5, 7, 8, 10], "root": 196.0, "bpm": 128,
                  "mood": "어둡고 도시적인 사이버펑크", "inst": "다크 신스·베이스",
                  "keywords": ["synthwave", "cyberpunk", "dark electronic"]},
    "wuxia": {"scale": [0, 2, 4, 7, 9], "root": 294.0, "bpm": 88,
              "mood": "동양적이고 유려한 무협", "inst": "이호·고쟁·대나무 피리",
              "keywords": ["chinese traditional", "wuxia", "guzheng"]},
    "steampunk": {"scale": [0, 2, 3, 5, 7, 8, 10], "root": 233.0, "bpm": 108,
                  "mood": "복고 기계적인 스팀펑크", "inst": "아코디언·태엽 벨·현악",
                  "keywords": ["steampunk", "victorian waltz", "mechanical"]},
    "fairytale": {"scale": [0, 2, 4, 5, 7, 9, 11], "root": 330.0, "bpm": 96,
                  "mood": "따뜻하고 몽환적인 동화", "inst": "글로켄슈필·하프·목관",
                  "keywords": ["fairytale", "whimsical", "music box"]},
    "horror": {"scale": [0, 1, 3, 5, 6, 8, 10], "root": 174.0, "bpm": 72,
               "mood": "불안하고 긴장된 호러", "inst": "저음 드론·불협 현악",
               "keywords": ["horror ambient", "tension", "dark drone"]},
    "post-apoc": {"scale": [0, 2, 3, 5, 7, 8, 10], "root": 185.0, "bpm": 84,
                  "mood": "황폐하고 비장한 포스트아포칼립스", "inst": "앰비언트 기타·타악",
                  "keywords": ["post-apocalyptic", "desolate", "cinematic ambient"]},
}
_DEFAULT_MUSIC = _GENRE_MUSIC["fantasy"]


class _LCG:
    def __init__(self, seed: int):
        self.s = seed & 0xFFFFFFFF

    def _n(self) -> int:
        self.s = (1103515245 * self.s + 12345) & 0x7FFFFFFF
        return self.s

    def pick(self, seq):
        return seq[self._n() % len(seq)]


def _tone(freq: float, dur: float, vol: float, square: bool = True) -> list[float]:
    """단순 어택/디케이 엔벨로프를 가진 톤 샘플."""
    n = max(1, int(_SR * dur))
    atk = max(1, int(_SR * 0.008))
    out = []
    for i in range(n):
        t = i / _SR
        s = math.sin(2 * math.pi * freq * t)
        v = (1.0 if s >= 0 else -1.0) if square else s
        env = min(1.0, i / atk) * max(0.0, 1.0 - i / n)
        out.append(v * vol * env)
    return out


def _note_freq(root: float, scale: list[int], degree: int) -> float:
    octave, idx = divmod(degree, len(scale))
    semis = scale[idx] + 12 * octave
    return root * (2 ** (semis / 12.0))


def generate_bgm(concept: EntityConcept, out_wav: Path, out_brief: Path,
                 genre: str) -> bool:
    """짧은 루프 WAV + BGM 기획서(txt) 생성. 성공 시 True."""
    m = _GENRE_MUSIC.get(genre, _DEFAULT_MUSIC)
    scale, root, bpm = m["scale"], m["root"], m["bpm"]
    beat = 60.0 / bpm  # 1박 길이(초)

    seed = abs(hash((concept.name or "") + genre)) & 0x7FFFFFFF
    rnd = _LCG(seed)

    # 8마디 멜로디(마디당 4박) + 베이스, 2회 반복 → 루프
    bars, beats_per_bar = 8, 4
    mix: list[float] = []
    prev = rnd.pick(range(len(scale)))
    for _ in range(bars * beats_per_bar):
        # 멜로디: 스케일 위를 완만히 이동
        step = rnd.pick([-2, -1, 0, 1, 1, 2])
        deg = max(0, min(len(scale) * 2 - 1, prev + step))
        prev = deg
        mel = _tone(_note_freq(root, scale, deg + len(scale)), beat * 0.9, 0.22, True)
        bass = _tone(_note_freq(root, scale, deg % len(scale)) / 2, beat, 0.16, False)
        seg = [(mel[i] if i < len(mel) else 0.0) + bass[i] for i in range(len(bass))]
        mix.extend(seg)
    mix = mix + mix  # 2회 반복

    # 정규화 → 16bit PCM
    peak = max((abs(v) for v in mix), default=1.0) or 1.0
    scale_f = 0.9 / peak
    try:
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(out_wav), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(_SR)
            frames = b"".join(struct.pack("<h", int(max(-1, min(1, v * scale_f)) * 32767))
                              for v in mix)
            wf.writeframes(frames)
    except Exception as exc:  # pragma: no cover
        log.warning("BGM WAV 생성 실패: %s", exc)
        return False

    _write_brief(concept, out_brief, genre, m, bpm)
    return True


def _write_brief(concept: EntityConcept, out_brief: Path, genre: str,
                 m: dict, bpm: int) -> None:
    kw = ", ".join(m["keywords"])
    dur = f"{len(concept.name or '')}"  # 사용 안 함(자리표시 방지)
    text = f"""# BGM 기획서 — {concept.name}

[대상] {concept.title or ''} · {concept.role or ''} ({genre})
[분위기] {m['mood']}
[템포] 약 {bpm} BPM
[추천 악기] {m['inst']}
[구성 제안] 인트로(4마디) → 메인 테마(8마디) → 브릿지 → 반복 루프

[CapCut 음악 찾기]
- CapCut > 오디오 > 음악 에서 아래 키워드로 검색해 어울리는 곡을 고르세요.
  검색어(영문): {kw}
- 상업적 사용 시 각 곡의 라이선스(저작권/크레딧 표기)를 반드시 확인하세요.
- 무료 곡이 부족하면 CapCut Pro 음원 또는 외부 로열티프리(Epidemic/Artlist 등) 활용.

[동봉 파일] bgm_loop.wav — 분위기 확인용 데모 루프(칩튠). 실제 영상에는
CapCut 음악 라이브러리의 정식 음원 사용을 권장합니다.
"""
    try:
        out_brief.parent.mkdir(parents=True, exist_ok=True)
        out_brief.write_text(text, encoding="utf-8")
    except Exception as exc:  # pragma: no cover
        log.debug("BGM 기획서 저장 실패(무시): %s", exc)
