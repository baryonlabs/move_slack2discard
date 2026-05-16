---
name: slack-to-local
description: Slack 워크스페이스 데이터를 로컬에 다운로드하고 LLM Wiki(Karpathy 스타일)로 검색하는 시스템. Slack Export ZIP → SQLite DB + FTS5 → 지능형 검색. Free 플랜용.
---

# Slack → Local 아카이브 + LLM Wiki 검색

Slack 워크스페이스의 모든 데이터를 로컬에 다운로드하고, LLM Wiki 방식으로 검색 가능한 시스템입니다.

## 빠른 시작

### 1. 환경 설정
```bash
# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일 편집: SLACK_USER_TOKEN 추가
```

### 2. Slack Export 다운로드
```
Slack Admin → Settings & Administration → Workspace settings
→ Import/Export Data → Export → Start Export
→ 범위: Public channels (Free 플랜)
→ 날짜: 최근 3개월 단위 권장
```

### 3. 실행
```bash
# Phase 1 & 2: 다운로드 + SQLite 저장
python agents/phase2_data_parser.py

# 테스트용 Mock 데이터로 먼저 해보기 (Slack 데이터 없어도 가능)
python agents/phase2_data_parser.py  # Mock 데이터 자동 생성됨

# LLM Wiki 검색 (Karpathy 스타일)
python agents/llm_wiki_search.py --interactive
```

## LLM Wiki 검색 사용법

### 대화형 모드 (추천)
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
---
```

### 1회 검색
```bash
# 기본 검색
python agents/llm_wiki_search.py "안녕하세요"

# prefix 검색 (한국어 지원)
python agents/llm_wiki_search.py "안녕"

# 채널 필터
python agents/llm_wiki_search.py "테스트" --channel general

# LLM 요약과 함께 (ANTHROPIC_API_KEY 필요)
python agents/llm_wiki_search.py "Slack" --llm
```

## 지속적 업데이트 (3개월마다)

```bash
# 새 ZIP 다운로드 후
python agents/phase1_slack_exporter.py ./slack_new.zip
python agents/phase2_data_parser.py
# → 자동으로 기존 DB에 병합 (INSERT OR IGNORE)
```

## 기능

- ✅ Slack Export ZIP → 로컬 다운로드
- ✅ SQLite + FTS5 전문 검색 (한국어 지원)
- ✅ LLM Wiki 검색 (Karpathy 스타일)
- ✅ 3개월마다 다운로드 → 자동 병합
- ✅ 대화형 검색 모드
- ✅ LLM 요약 (선택적)

## 파일 구조

```
project/
├── .env                    # 환경 변수
├── requirements.txt
├── README.md
├── data/
│   ├── archive.db          # SQLite DB (FTS5 인덱스 포함)
│   ├── files/              # 다운로드된 Slack 파일
│   └── slack_export/       # Slack ZIP 압축 해제 경로
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

## 한국어 검색 팁

- SQLite FTS5 unicode61 토크나이저 사용
- `"안녕"*` 형태로 prefix 검색 가능
- 정확한 문구는 따옴표로 검색: `"안녕하세요"`

## 문제 해결

- **FTS 검색 결과 없음**: `"` 따옴표 없이 검색하거나 `*` prefix 사용
- **DB 잠금**: `rm data/archive.db-wal data/archive.db-shm`
- **파일 다운로드 실패**: `data/progress/failed_files.json` 확인

## 보안

- ✅ .env는 .gitignore에 포함됨
- ✅ data/ 디렉토리는 .gitignore에 포함됨
- ✅ 토큰 하드코딩 금지
