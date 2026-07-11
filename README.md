# AXData Studio — 캐릭터 & 게임 아트 자동 제작 툴

**GPT(기획) + Gemini(아트) + CapCut(영상)** 을 조합해 **캐릭터 · 몬스터 · NPC**
를 입력하면 **15종 아트 요소 · 캐릭터 시트 · 쇼케이스 영상**을 한 번에
자동 생성하는 웹 도구입니다. 만들 요소는 체크박스로 골라서 진행합니다.

```
대상 브리프 ─▶ GPT ─▶ 기획서(스탯·설정·visual_core·엔티티별 정보)
 (캐릭터/            │
  몬스터/            ▼
  NPC)      Gemini ─▶ [선택한 아트 요소들]
                        │
              ┌─────────┼──────────────┐
              ▼         ▼              ▼
        캐릭터 시트   게임 아트 에셋   CapCut 영상
        (PNG/PDF)     (15종 선택)     (draft + 미리보기 GIF/MP4)
```

## ✨ 특징

- **3가지 대상** — 캐릭터(플레이어) · 몬스터(적) · NPC. 엔티티별로 기획 필드,
  스탯, 부가 정보(위협도/서식지, 직업/소속 등)와 시트 라벨이 자동으로 바뀜
- **15종 아트 요소 선택 생성** — 필요한 것만 체크해서 생성 (아래 카탈로그 참고)
- **웹 UI** — 브라우저에서 설정하고 결과를 카테고리별로 미리보기·다운로드
- **데모 모드** — API 키가 없어도 전체 파이프라인이 끝까지 동작
  (GPT → 로컬 기획 생성기, Gemini → 카테고리별 Pillow 플레이스홀더 아트)
- **CapCut 연동** — 편집용 draft 프로젝트(스토리보드 + 에셋)를 생성.
  `pyJianYingDraft` 설치 시 CapCut 에서 바로 여는 네이티브 draft 도 생성
- **의존성 없는 미리보기 영상** — Pillow 만으로 Ken Burns 슬라이드쇼 GIF 생성
  (ffmpeg/imageio 있으면 MP4 도 추가)

## 🎨 아트 요소 카탈로그 (15종)

| 카테고리 | 요소 |
|----------|------|
| **캐릭터 아트** | 초상화, 전신, 표정 세트(×4), 액션 포즈(×3), 도트 스프라이트, 턴어라운드(×3), 엠블럼 아이콘 |
| **아이템 / 장비** | 무기·방어구 아이콘(×3), 인벤토리 아이템, 스킬 아이콘(×3) |
| **환경 / 배경** | 배경 일러스트, 타일셋 |
| **UI / 브랜딩** | 타이틀 로고, TCG 카드, 배너·썸네일 |
| **통합 산출물** | 캐릭터 시트(PNG/PDF), 쇼케이스 영상 + CapCut draft |

> 요소는 `app/services/asset_catalog.py` 한 곳에서 정의됩니다.
> 항목을 추가하면 GPT 프롬프트·Gemini 생성·UI 체크리스트에 자동 반영됩니다.

## 🚀 빠른 시작

```bash
# 1) 의존성 설치
pip install -r requirements.txt

# 2) (선택) API 키 설정 — 없으면 데모 모드로 동작
cp .env.example .env
#  .env 에 OPENAI_API_KEY, GEMINI_API_KEY 입력

# 3) 서버 실행
uvicorn app.main:app --reload

# 4) 브라우저에서 http://127.0.0.1:8000 접속
```

## 🔑 API 키 설정 (`.env`)

| 변수 | 용도 | 미설정 시 |
|------|------|-----------|
| `OPENAI_API_KEY` | GPT 캐릭터 기획 | 로컬 데모 생성기 사용 |
| `OPENAI_MODEL` | 기본 `gpt-4o-mini` | — |
| `GEMINI_API_KEY` | Gemini 이미지 생성 | Pillow 플레이스홀더 |
| `GEMINI_IMAGE_MODEL` | 기본 `gemini-2.5-flash-image` | — |
| `CAPCUT_DRAFT_DIR` | CapCut 초안 폴더 경로(선택) | 앱 outputs 하위 |

## 📁 구조

```
app/
├── main.py                # FastAPI 앱 (UI + API)
├── config.py              # 설정 / .env
├── models.py              # Pydantic 스키마 (엔티티/에셋)
├── services/
│   ├── asset_catalog.py   # 15종 아트 요소 레지스트리 (단일 진실 공급원)
│   ├── gpt_service.py     # 캐릭터/몬스터/NPC 기획 (OpenAI + 데모 폴백)
│   ├── gemini_service.py  # 범용 에셋 생성 (Gemini + 카테고리별 플레이스홀더)
│   ├── sheet_composer.py  # 캐릭터 시트 PNG/PDF 조합 (Pillow, 엔티티 대응)
│   ├── capcut_service.py  # CapCut draft + 쇼케이스 영상
│   ├── pipeline.py        # 오케스트레이션
│   └── fonts.py           # 폰트 로딩 (한글 지원)
└── static/                # 웹 UI (HTML/CSS/JS)
outputs/                   # 생성 결과 (job_id 별)
```

## 🎬 CapCut 워크플로우

생성된 `outputs/<job_id>/capcut_draft/` 폴더에는:

- `assets/` — 초상화·전신·아이콘 이미지
- `capcut_storyboard.json` — 씬 순서/길이/전환/자막/BGM 제안
- `README.txt` — CapCut 편집 안내
- (`pyJianYingDraft` 설치 시) `draft_content.json` — CapCut 에서 바로 열기

미리보기 `showcase.gif` 는 실제 편집 전에 완성 이미지를 확인하는 용도입니다.

## 🛠 API

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/` | 웹 UI |
| `GET` | `/api/status` | GPT/Gemini live·demo 상태 |
| `GET` | `/api/catalog` | 엔티티 타입 + 15종 에셋 카탈로그 |
| `POST` | `/api/generate` | 생성 (entity_type + assets 선택 → 결과) |
| `GET` | `/files/<job_id>/...` | 생성 산출물 서빙 |

## 📌 참고

- CapCut 은 공식 공개 API 가 없어 draft 파일 방식으로 연동합니다.
- 상용 배포 시 각 AI 제공자의 이용약관·콘텐츠 정책을 확인하세요.
