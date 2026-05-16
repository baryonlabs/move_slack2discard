# Slack → Local 아카이브 시스템

Slack 워크스페이스의 모든 데이터를 로컬에 다운로드하고, LLM Wiki(Karpathy 스타일)로 검색 가능한 시스템입니다.

## 빠른 시작 (Mock 데이터로 테스트)

### 1. 환경 설정
```bash
# 의존성 설치
pip install -r requirements.txt

# .env 생성 (Slack 토큰은 나중에 추가)
cp .env.example .env
```

### 2. Mock 데이터로 테스트 (지금 바로 가능)
```bash
# Mock 데이터는 이미 생성됨: data/slack_export/
# Phase 2 실행 (파싱 & SQLite 저장)
python agents/phase2_data_parser.py

# 검증
sqlite3 data/archive.db "SELECT COUNT(*) FROM messages;"
sqlite3 data/archive.db "SELECT COUNT(*) FROM messages_fts;"
```

### 3. LLM Wiki 검색 테스트
```bash
# 기본 검색
python agents/llm_wiki_search.py "안녕하세요"

# 대화형 모드 (추천)
python agents/llm_wiki_search.py --interactive

# LLM 요약과 함께 (ANTHROPIC_API_KEY 또는 OPENAI_API_KEY 필요)
python agents/llm_wiki_search.py "Slack" --llm
```

## 실제 Slack 데이터 사용법

### 1. Slack Export ZIP 다운로드
```
Slack Admin → Settings & Administration → Workspace settings
→ Import/Export Data → Export → Start Export
→ 범위: 최근 3개월 (Free 플랜: Public channels만)
```

### 2. Phase 1 & 2 실행
```bash
# Phase 1: ZIP 압축 해제 & 파일 다운로드
python agents/phase1_slack_exporter.py ./slack_export.zip

# Phase 2: SQLite DB 저장
python agents/phase2_data_parser.py

# 검증
sqlite3 data/archive.db "SELECT COUNT(*) FROM messages;"
```

### 3. 지속적 업데이트 (3개월마다)
```bash
# 새 ZIP 다운로드 후 동일하게 실행
python agents/phase1_slack_exporter.py ./slack_new.zip
python agents/phase2_data_parser.py
# → 자동으로 기존 DB에 병합 (INSERT OR IGNORE)
```

## LLM Wiki 검색 사용법

### 대화형 모드 (Karpathy 스타일)
```bash
python agents/llm_wiki_search.py --interactive
```

```
======================================================
Slack 아카이브 LLM Wiki 검색 (대화형 모드)
======================================================
명령어: /search <쿼리>, /stats, /quit

🔍 Slack 아카이브 테스트
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
# 정확한 문구 검색
python agents/llm_wiki_search.py "Python SQLite"

# prefix 검색 (한국어 지원)
python agents/llm_wiki_search.py "안녕"

# 채널 필터
python agents/llm_wiki_search.py "테스트" --channel general

# LLM 요약과 함께
python agents/llm_wiki_search.py "검색" --llm
```

## 한국어 검색 팁
- SQLite FTS5 unicode61 토크나이저 사용
- `"안녕"*` 형태로 prefix 검색 가능
- 정확한 문구는 따옴표로 검색: `"안녕하세요"`

## 파일 구조
```
project/
├── .env                    # 환경 변수 (git 제외)
├── requirements.txt
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
│       └── ...
└── tests/
    └── test_each_phase.py
```

## Discord 봇 (나중에)
```bash
# .env에 DISCORD_BOT_TOKEN 추가 후
python agents/phase3_discord_bot.py
```

## 문제 해결
- **FTS 검색 결과 없음**: `"` 따옴표 없이 검색하거나 `*` prefix 사용
- **DB 잠금**: `rm data/archive.db-wal data/archive.db-shm`
- **파일 다운로드 실패**: `data/progress/failed_files.json` 확인

## 보안
- ✅ .env는 .gitignore에 포함됨
- ✅ data/ 디렉토리는 .gitignore에 포함됨
- ✅ 토큰 하드코딩 금지
