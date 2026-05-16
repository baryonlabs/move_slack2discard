---
name: slack-archive-search
description: Slack 아카이브 검색 (LLM Wiki 스타일). Slack Export ZIP을 자동 처리하고 /search-slack 명령어로 메시지/이미지/첨부파일 검색.
---

# Slack Archive Search Skill

사용자가 **"/search-slack <쿼리>"**, **"Slack 메시지 검색"**, **"과거 Slack 기록 찾아줘"** 등을 요청하면 이 스킬이 자동 실행됩니다.

## 🎯 트리거 조건

다음 중 하나라도 포함되면 스킬 실행:
- `/search-slack <쿼리>`
- `Slack 검색`, `Slack 아카이브`, `과거 Slack 메시지`
- `Slack 파일 찾아줘`, `Slack 이미지 검색`

## 📦 자동 설치 (최초 1회)

데이터가 없으면 스킬이 자동으로 설치합니다:

```bash
# 1. 리포지토리 클론
[ -d /tmp/slack-archive ] || git clone https://github.com/baryonlabs/move_slack2discard.git /tmp/slack-archive
cd /tmp/slack-archive

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 환경 변수 설정 안내
echo "다음 단계: .env 파일에 SLACK_USER_TOKEN 입력하세요."
```

## 🚀 실행 흐름

### 1. 데이터 확인
```bash
[ -f /tmp/slack-archive/data/archive.db ] && echo "DB_EXISTS" || echo "NO_DB"
```

### 2. 데이터 없을 때 (최초 실행)
```bash
# Slack Export ZIP 다운로드 안내
echo "Slack Admin → Settings → Import/Export → Export → Public channels ZIP 다운로드"
echo "ZIP 파일 경로를 알려주세요: /search-slack --init {ZIP_PATH}"

# ZIP 받으면 자동 처리
cd /tmp/slack-archive
python agents/phase1_slack_exporter.py {ZIP_PATH}
python agents/phase2_data_parser.py
```

### 3. 검색 실행
```bash
cd /tmp/slack-archive
python agents/llm_wiki_search.py --search-slack "{쿼리}" --limit 10
```

## 📂 검색 결과 구조 (JSON)

`--search-slack` 모드 출력 예시:

```json
{
  "query": "안녕하세요",
  "count": 1,
  "results": [
    {
      "channel": "general",
      "user": "Martin Kim",
      "timestamp": "2024-02-01 09:00",
      "text": "안녕하세요! Slack 아카이브 시스템 테스트 중입니다.",
      "files": [
        {
          "name": "test_document.pdf",
          "size": 102400,
          "local_path": "/tmp/slack-archive/data/files/F001/test_document.pdf"
        },
        {
          "name": "image.png",
          "size": 51200,
          "local_path": "/tmp/slack-archive/data/files/F002/image.png"
        }
      ]
    }
  ]
}
```

## 🖼️ 이미지/첨부파일 조회

### 로컬 경로로 바로 접근
검색 결과의 `files[].local_path`를 사용:
```bash
open /tmp/slack-archive/data/files/F002/image.png
```

### 이미지 미리보기 (Claude Code 내)
```bash
# 작은 이미지(<1MB)는 base64로 인코딩해서 표시 가능
python -c "import base64; print(base64.b64encode(open('/tmp/slack-archive/data/files/F002/image.png','rb').read()).decode())"
```

## 🔄 지속적 업데이트
```
/search-slack --update ./new_slack.zip
```
→ 자동으로 기존 DB에 병합 (INSERT OR IGNORE)

## 💡 사용 예시

### 예시 1: 기본 검색
```
/search-slack "안녕하세요"
```
→ 최근 10개 결과 반환 (JSON)

### 예시 2: 첨부파일 있는 메시지만
```
/search-slack "디자인 검토" --has-files
```
→ `files` 배열이 비어있지 않은 결과만 필터링

### 예시 3: 대화형 모드
```
/search-slack --interactive
```
→ REPL 형태로 계속 검색

### 예시 4: LLM 요약
```
/search-slack "프로젝트 진행상황" --llm
```
→ Claude/AI가 결과를 요약해서 설명 (ANTHROPIC_API_KEY 필요)

## ⚠️ 문제 해결

| 문제 | 해결 방법 |
|---|---|
| DB 없음 | `Slack Export ZIP 다운로드 후 /search-slack --init {ZIP_PATH}` |
| 이미지 안 보임 | `ls /tmp/slack-archive/data/files/` 확인, Phase 1 재실행 |
| 검색 결과 없음 | `"안녕"*` prefix 검색 시도 |
| 데이터 업데이트 | `/search-slack --update ./new.zip` |

## 🔒 보안
- `.env`는 절대 공유 금지
- 토큰은 하드코딩하지 않음
- 모든 데이터는 로컬 저장

---

*Slack Archive Search Skill | Baryon Labs*