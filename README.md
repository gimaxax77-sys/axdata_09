# AXData Studio — 캐릭터 & 게임 아트 자동 제작 툴

**GPT(기획) + Gemini(아트) + CapCut(영상)** 을 조합해 **캐릭터 · 몬스터 · NPC**
를 입력하면 **26종 아트 요소 · 캐릭터 시트 · 쇼케이스 영상**을 한 번에
자동 생성하는 웹 도구입니다. 만들 요소는 체크박스로 골라서 진행하며,
여러 개체를 한 번에 만드는 **일괄 생성(도감)** 모드도 지원합니다.

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
- **26종 아트 요소 선택 생성** — 필요한 것만 체크해서 생성 (아래 카탈로그 참고)
- **일괄 생성(도감)** — 개수·역할 목록을 주면 여러 개체를 병렬 생성하고,
  전체를 한 장에 모은 **도감 오버뷰 이미지**까지 만들어 줌
- **웹 UI** — 브라우저에서 설정하고 결과를 카테고리별로 미리보기·다운로드
- **캐릭터 일관성(레퍼런스)** — 초상화를 앵커로 삼아 전신·표정·포즈 등을
  image-to-image 로 파생, 동일 인물 유지 (실 API 에서 효과, 기본 ON)
- **투명 배경(PNG 알파)** — 스프라이트·아이콘 등 컷아웃 에셋 배경 제거
  (rembg 설치 시 정밀, 미설치 시 Pillow 플러드필 폴백)
- **스프라이트 시트 export** — 다변형 에셋을 아틀라스 PNG + 프레임/피벗 메타
  JSON 으로 패킹 (게임 엔진 임포트용)
- **스타일 락** — 앵커를 전체 에셋에 스타일·팔레트 기준으로 주입해 룩 통일
- **이미지 모델 선택** — Gemini(Nano Banana) / OpenAI gpt-image-1(네이티브 투명)
- **ZIP 내보내기** — 결과/도감 전체를 한 번에 다운로드
- **정밀 사용량 집계** — GPT·Gemini 토큰까지 반영한 예상 비용
- **생성 히스토리** — 과거 생성 기록을 썸네일로 조회·다시보기·ZIP·삭제
  (모든 결과는 `OUTPUT_DIR` 아래 폴더로 자동 저장)
- **데모 모드** — API 키가 없어도 전체 파이프라인이 끝까지 동작
  (GPT → 로컬 기획 생성기, Gemini → 카테고리별 Pillow 플레이스홀더 아트)
- **CapCut 연동** — 편집용 draft 프로젝트(스토리보드 + 에셋)를 생성.
  `pyJianYingDraft` 설치 시 CapCut 에서 바로 여는 네이티브 draft 도 생성
- **의존성 없는 미리보기 영상** — Pillow 만으로 Ken Burns 슬라이드쇼 GIF 생성
  (ffmpeg/imageio 있으면 MP4 도 추가)

## 🎨 아트 요소 카탈로그 (21종)

| 카테고리 | 요소 |
|----------|------|
| **캐릭터 아트** | 초상화, 전신, 표정 세트, 액션 포즈, 도트 스프라이트, 턴어라운드(×3), 엠블럼, 이모트, 탈것/펫 |
| **아이템 / 장비** | 무기·방어구 아이콘(×3), 인벤토리 아이템, 스킬 아이콘, 등급 프레임(×5) |
| **환경 / 배경** | 배경 일러스트, 타일셋, 스카이박스 |
| **UI / 브랜딩** | 타이틀 로고, TCG 카드, 배너·썸네일, 스플래시 아트, 프로필 카드 |
| **인게임 UI / HUD** | 버튼 세트, 기능 아이콘, 재화 아이콘, 창/패널 프레임, HUD 바 세트 |
| **통합 산출물** | 캐릭터 시트(PNG/PDF), 쇼케이스 영상 + CapCut draft |

> **변형 개수 선택**: 표정·포즈·스킬·이모트·버튼·아이콘 등 "가변" 에셋은
> 3/5/7/10개 중 원하는 장수만큼 생성할 수 있습니다.

## 📚 일괄 생성(도감)

`일괄 생성 · 도감` 모드에서 개수(1~8)와 역할/종족 목록을 입력하면:

- 각 개체를 **병렬로 생성**(스레드 풀)해 개체별 아트·시트를 만들고
- 전체를 한 장에 모은 **도감 오버뷰 이미지**(이름·역할·핵심 지표)를 생성

몬스터 도감, NPC 명부, 캐릭터 로스터 등을 한 번에 뽑을 때 유용합니다.
(개체당 영상은 N배 느려지므로 일괄 모드에서는 기본 해제됩니다.)

> 요소는 `app/services/asset_catalog.py` 한 곳에서 정의됩니다.
> 항목을 추가하면 GPT 프롬프트·Gemini 생성·UI 체크리스트에 자동 반영됩니다.

## 🪟 Windows 원클릭 (bat)

| 파일 | 기능 |
|------|------|
| **`start.bat`** | 서버 실행 + 브라우저 자동 열림 (모바일 접속용 0.0.0.0) |
| **`stop.bat`** | 서버 종료 |
| **`update.bat`** | 종료 → `git pull` → 의존성 갱신 → (선택)실행. **경로 자동 인식** |

> 업데이트는 **`update.bat` 더블클릭** 한 번이면 끝 — cd/pull/pip 수동 입력 불필요.

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

- **OpenAI 키**: <https://platform.openai.com/api-keys> (결제/크레딧 활성 필요)
- **Gemini 키**: <https://aistudio.google.com/apikey> (Google AI Studio)
- `gemini-2.5-flash-image`(Nano Banana) 사용에는 `google-genai>=1.38` 이 필요합니다
  (`requirements.txt` 에 반영됨).

## 🔌 실 API 연동 확인 (스모크 테스트)

키를 넣은 뒤, 실제 호출이 되는지 한 번에 점검할 수 있습니다.

```bash
python scripts/smoke_test.py          # 제공자별 최소 호출 점검
python scripts/smoke_test.py --full   # 실제 캐릭터 1종 전체 생성까지
```

- 키가 없으면 해당 항목은 **SKIP** (데모 모드는 그대로 동작)
- 실패 시 원인별 힌트(키/모델/한도/설치) 출력
- `--full` 은 실제 API 로 초상화·엠블럼·시트를 생성해 `outputs/smoke_full/` 에 저장하고,
  각 산출물이 **LIVE / DEMO** 중 무엇으로 만들어졌는지 표시

## 📁 구조

```
app/
├── main.py                # FastAPI 앱 (UI + API)
├── config.py              # 설정 / .env
├── models.py              # Pydantic 스키마 (엔티티/에셋)
├── services/
│   ├── asset_catalog.py   # 26종 아트 요소 레지스트리 (단일 진실 공급원)
│   ├── gpt_service.py     # 캐릭터/몬스터/NPC 기획 (OpenAI + 데모 폴백)
│   ├── gemini_service.py  # 범용 에셋 생성 (Gemini + 카테고리별 플레이스홀더)
│   ├── sheet_composer.py  # 캐릭터 시트 PNG/PDF 조합 (Pillow, 엔티티 대응)
│   ├── codex_composer.py  # 도감 오버뷰 이미지 조합 (일괄 생성)
│   ├── capcut_service.py  # CapCut draft + 쇼케이스 영상
│   ├── pipeline.py        # 오케스트레이션 (단일 + 일괄)
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
| `GET` | `/api/catalog` | 엔티티 타입 + 21종 에셋 카탈로그 |
| `POST` | `/api/generate` | 단일 생성 (entity_type + assets → 결과) |
| `POST` | `/api/generate_batch` | 일괄 생성 (count + roles → 개체들 + 도감) |
| `GET` | `/files/<job_id>/...` | 생성 산출물 서빙 |

## 📌 참고

- CapCut 은 공식 공개 API 가 없어 draft 파일 방식으로 연동합니다.
- 상용 배포 시 각 AI 제공자의 이용약관·콘텐츠 정책을 확인하세요.
