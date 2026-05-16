# Slack Archive Search Plugin for Claude Code

> **Claude Code 플러그인으로 설치하고 쉽게 Slack 아카이브를 검색하세요!**

## 🚀 빠른 설치 (Claude Code 내에서)

### 1. 플러그인 마켓플레이스 추가
```
/plugin marketplace add baryonlabs/move_slack2discard
```

### 2. 플러그인 설치
```
/plugin install slack-archive-search
```

### 3. 환경 설정
```bash
cd ~/.claude/plugins/slack-archive-search
pip install -r requirements.txt
cp .env.example .env
# .env 편집하여 SLACK_USER_TOKEN 입력
```

### 4. 사용 시작
```
/search-slack "안녕하세요"
/search-slack --interactive
```

---

## ✨ 기능

- ✅ **Slack Export ZIP → 로컬 다운로드** (Free 플랜 Public 채널 지원)
- ✅ **이미지/첨부파일 모두 다운로드** (자동 중단점 복구)
- ✅ **SQLite + FTS5 전문 검색** (한국어 음절 단위 검색)
- ✅ **LLM Wiki 검색** (Karpathy 스타일, 대화형 모드)
- ✅ **Claude Code 스킬** (`/search-slack` 명령어)
- ✅ **3개월마다 지속적 업데이트** (DB 자동 병합)

## 📦 플러그인 구조

```
move_slack2discard/
├── .claude-plugin/           # 플러그인 메타데이터
│   ├── plugin.json
│   └── marketplace.json
├── plugins/
│   └── slack-archive-search/   # 메인 플러그인
│       ├── SKILL.md            # Claude Code 스킬 정의
│       ├── README.md           # 플러그인 내 사용법
│       ├── requirements.txt
│       └── agents/
│           ├── phase1_slack_exporter.py
│           ├── phase2_data_parser.py
│           └── llm_wiki_search.py
└── data/                      # (git 제외) 로컬 데이터
```

## 📥 실제 Slack 데이터 사용법

### 1. Slack Export ZIP 다운로드
```
Slack Admin → Settings & Administration → Workspace settings
→ Import/Export Data → Export → Public channels ZIP 다운로드
```

### 2. 데이터 처리
```bash
# 플러그인 설치 후 디렉토리에서
python agents/phase2_data_parser.py

# 또는 Slack Export ZIP이 있다면
python agents/phase1_slack_exporter.py ./slack_export.zip
python agents/phase2_data_parser.py
```

### 3. 검색
```bash
# 기본 검색
python agents/llm_wiki_search.py "안녕하세요"

# Claude Code 스킬 사용
/search-slack "안녕하세요"
```

## 🖼️ 이미지/첨부파일 조회

검색 결과에 자동으로 첨부파일(이미지, 문서 등) 정보가 표시됩니다:
```
**첨부 파일:**
  - test_document.pdf (102400 bytes)
  - image.png (51200 bytes) → 로컬: /path/to/data/files/F001/image.png
```

## 🔄 지속적 업데이트 (3개월마다)

```bash
# 새 ZIP 다운로드 후
python agents/phase1_slack_exporter.py ./slack_new.zip
python agents/phase2_data_parser.py
# → 자동으로 기존 DB에 병합 (INSERT OR IGNORE)
```

## 🚨 문제 해결

| 문제 | 해결 방법 |
|---|---|
| DB 없음 | Slack Export ZIP 다운로드 후 `/search-slack --init {ZIP_PATH}` |
| 이미지 안 보임 | `data/files/` 폴더 확인, Phase 1 재실행 |
| 검색 결과 없음 | `"안녕"*` prefix 검색 시도 |

## 🔒 보안

- ✅ `.env`는 `.gitignore`에 포함됨
- ✅ `data/` 디렉토리는 `.gitignore`에 포함됨 (개인정보 포함)
- ✅ 토큰 하드코딩 금지

## 📜 라이선스

MIT License

---

*Slack Archive Search Plugin | Baryon Labs*
