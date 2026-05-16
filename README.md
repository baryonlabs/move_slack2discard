# Slack → Local 아카이브 + LLM Wiki 검색

Slack 워크스페이스의 **모든 데이터(메시지, 파일, 이미지)**를 로컬에 다운로드하고, LLM Wiki(Karpathy 스타일)로 검색하는 시스템입니다.

## ✨ 주요 기능

- ✅ **Slack Export ZIP → 로컬 다운로드** (Public 채널, Free 플랜 지원)
- ✅ **이미지/첨부파일 모두 다운로드** (자동 중단점 복구)
- ✅ **SQLite + FTS5 전문 검색** (한국어 음절 단위 검색)
- ✅ **LLM Wiki 검색** (Karpathy 스타일, 대화형 모드)
- ✅ **3개월마다 지속적 업데이트** (DB 자동 병합)
- ✅ **Claude Code 스킬 지원** (`/search-slack` 명령어)

---

## 📦 스킬로 설치하기 (추천)

### 1. 리포지토리 클론
```bash
git clone https://github.com/baryonlabs/move_slack2discard.git
cd move_slack2discard
```

### 2. 의존성 설치
```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정
```bash
cp .env.example .env
# .env 파일 열어서 SLACK_USER_TOKEN 입력
```

### 4. 스킬 인식 확인
Claude Code에서 다음 명령어로 스킬이 인식되는지 확인:
```
/search-slack --help
```

---

## 🚀 빠른 시작 (Mock 데이터로 테스트)

Slack 데이터 없이도 **지금 바로 테스트** 가능합니다:

```bash
# Mock 데이터로 Phase 2 실행 (자동으로 테스트 데이터 생성됨)
python agents/phase2_data_parser.py

# LLM Wiki 검색 테스트 (대화형 모드)
python agents/llm_wiki_search.py --interactive
```

---

## 📥 실제 Slack 데이터 사용법

### 1. Slack Export ZIP 다운로드
```
Slack Admin → Settings & Administration → Workspace settings
→ Import/Export Data → Export → Start Export
→ 범위: Public channels (Free 플랜)
→ 날짜: 최근 3개월 단위 권장
```

### 2. Phase 1 & 2 실행
```bash
# ZIP 파일을 프로젝트 루트에 복사 후
python agents/phase1_slack_exporter.py ./slack_export.zip

# SQLite DB 저장 (자동으로 파일 경로도 저장됨)
python agents/phase2_data_parser.py

# 검증
sqlite3 data/archive.db "SELECT COUNT(*) FROM messages;"
sqlite3 data/archive.db "SELECT local_path FROM files LIMIT 5;"
```

### 3. 검색 실행

**기본 검색:**
```bash
python agents/llm_wiki_search.py "안녕하세요"
```

**대화형 모드 (추천):**
```bash
python agents/llm_wiki_search.py --interactive
```

```
======================================================
Slack 아카이브 LLM Wiki 검색 (대화형 모드)
======================================================
명령어: /search <쿼리>, /stats, /quit

🔍 안녕하세요
# Slack 아카이브 검색 결과
> **검색어:** `안녕하세요`
> **결과 수:** 1개
---
## 1. general | Martin Kim | 2024-02-01 09:00
```
안녕하세요! Slack 아카이브 시스템 테스트 중입니다.
```

**첨부파일 정보 표시:**
검색 결과에 자동으로 첨부파일(이미지, 문서 등) 정보가 표시됩니다:
```
**첨부 파일:**
  - test_document.pdf (102400 bytes)
  - image.png (51200 bytes)
```

**LLM 요약과 함께:**
```bash
python agents/llm_wiki_search.py "Slack" --llm
# ANTHROPIC_API_KEY 또는 OPENAI_API_KEY 필요
```

---

## 🔄 지속적 업데이트 (3개월마다)

Slack 데이터는 3개월마다 새로 Export 받고, 기존 DB에 병합합니다:

```bash
# 새 ZIP 다운로드 후
python agents/phase1_slack_exporter.py ./slack_new.zip
python agents/phase2_data_parser.py
# → 자동으로 기존 DB에 병합 (INSERT OR IGNORE)
```

**이미 다운로드된 파일은 스킵**, 새 파일만 다운로드됩니다.

---

## 🖼️ 이미지/첨부파일 조회

### 로컬 경로로 조회
```bash
# DB에서 파일 경로 확인
sqlite3 data/archive.db "SELECT name, local_path FROM files WHERE local_path IS NOT NULL LIMIT 5;"
```

출력 예시:
```
test_document.pdf|data/files/F001/test_document.pdf
image.png|data/files/F002/image.png
```

### 검색 시 자동 표시
LLM Wiki 검색 시 첨부파일 정보가 자동으로 포함됩니다.

---

## 🛠️ Claude Code 스킬로 사용하기

### 스킬 명령어: `/search-slack`

**기본 검색:**
```
/search-slack "안녕하세요"
```

**대화형 모드:**
```
/search-slack --interactive
```

**LLM 요약:**
```
/search-slack "테스트" --llm
```

**업데이트:**
```
/search-slack --update ./new_slack_export.zip
```

---

## 📂 파일 구조

```
project/
├── .env                    # 환경 변수 (git 제외)
├── requirements.txt
├── README.md
├── SKILL.md               # Claude Code 스킬 정의
├── data/
│   ├── archive.db          # SQLite DB (FTS5 인덱스 포함)
│   ├── files/              # 다운로드된 Slack 파일 (이미지/문서 등)
│   │   └── {file_id}/
│   │       └── {filename}
│   ├── slack_export/       # Slack ZIP 압축 해제 경로
│   └── progress/           # 진행 상태 JSON 파일들
├── agents/
│   ├── phase1_slack_exporter.py   # Slack 파일 다운로드
│   ├── phase2_data_parser.py     # SQLite 파싱 & 저장
│   ├── llm_wiki_search.py        # LLM Wiki 검색 (Karpathy 스타일)
│   └── utils/
│       ├── db.py
│       ├── schema.sql
│       ├── rate_limiter.py
│       └── progress_tracker.py
└── tests/
    └── test_each_phase.py
```

---

## 🇰🇷 한국어 검색 팁

- SQLite FTS5 `unicode61` 토크나이저 사용
- `"안녕"*` 형태로 prefix 검색 가능
- 정확한 문구는 따옴표로 검색: `"안녕하세요"`

---

## ⚠️ 문제 해결

| 문제 | 해결 방법 |
|---|---|
| FTS 검색 결과 없음 | `"` 따옴표 없이 검색하거나 `*` prefix 사용 |
| DB 잠금 | `rm data/archive.db-wal data/archive.db-shm` |
| 파일 다운로드 실패 | `data/progress/failed_files.json` 확인 |
| 이미지가 안 보임 | `data/files/` 폴더 확인, Phase 1 재실행 |

---

## 🔒 보안

- ✅ `.env`는 `.gitignore`에 포함됨
- ✅ `data/` 디렉토리는 `.gitignore`에 포함됨 (개인정보 포함)
- ✅ 토큰 하드코딩 금지

---

## 📜 라이선스

MIT License

---

*Slack → Local 아카이브 시스템 | Baryon Labs*