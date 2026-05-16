"""
LLM Wiki Search (Karpathy 스타일)
로컬 SQLite FTS5 + LLM을 활용한 지능형 검색

사용법:
  python agents/llm_wiki_search.py "검색어"
  python agents/llm_wiki_search.py --query "안녕하세요" --limit 5
  python agents/llm_wiki_search.py --interactive  # 대화형 모드
"""
import os, sqlite3, argparse, json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_PATH = Path(os.getenv("DB_PATH", "./data/archive.db"))
LLM_API_KEY = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
LLM_PROVIDER = "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "openai" if os.getenv("OPENAI_API_KEY") else None

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def format_timestamp(ts: float) -> str:
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except:
        return "날짜 불명"

def search_messages(query: str, limit: int = 10, channel: str = None):
    """
    FTS5 전문 검색 수행 (Karpathy 스타일: 빠르고 정확한 1차 검색)
    한국어 검색을 위해 음절 단위 prefix 검색 지원 (예: "안녕*" → "안녕하세요" 매칭)
    """
    # 한국어 검색 개선: 따옴표 없으면 prefix 검색 적용
    if not query.startswith('"') and not query.endswith('"'):
        # 각 단어에 prefix 매칭 적용
        words = query.split()
        fts_query = " OR ".join([f'"{w}"*' if len(w) >= 2 else f'"{w}"' for w in words])
    else:
        fts_query = query

    db = get_db()

    if channel:
        rows = db.execute("""
            SELECT m.id, m.text, m.ts, m.channel_id,
                   c.name as channel_name,
                   u.display_name as user_name,
                   u.name as user_handle
            FROM messages_fts fts
            JOIN messages m ON fts.rowid = m.rowid
            LEFT JOIN channels c ON m.channel_id = c.id
            LEFT JOIN users u ON m.user_id = u.id
            WHERE messages_fts MATCH ?
              AND c.name = ?
            ORDER BY m.ts DESC
            LIMIT ?
        """, (fts_query, channel, limit)).fetchall()
    else:
        rows = db.execute("""
            SELECT m.id, m.text, m.ts, m.channel_id,
                   c.name as channel_name,
                   u.display_name as user_name,
                   u.name as user_handle
            FROM messages_fts fts
            JOIN messages m ON fts.rowid = m.rowid
            LEFT JOIN channels c ON m.channel_id = c.id
            LEFT JOIN users u ON m.user_id = u.id
            WHERE messages_fts MATCH ?
            ORDER BY m.ts DESC
            LIMIT ?
        """, (fts_query, limit)).fetchall()

    db.close()
    return rows

def format_wiki_style(results: list, query: str) -> str:
    """
    Karpathy 스타일 Wiki 포맷팅:
    - 깔끔한 마크다운
    - 컨텍스트 보존
    - 메타데이터 최소화
    """
    if not results:
        return f"## 검색 결과 없음\n**쿼리:** `{query}`"

    output = [f"# Slack 아카이브 검색 결과\n"]
    output.append(f"> **검색어:** `{query}`")
    output.append(f"> **결과 수:** {len(results)}개\n")
    output.append("---\n")

    for i, row in enumerate(results, 1):
        channel = row["channel_name"] or "unknown"
        user = row["user_name"] or row["user_handle"] or "unknown"
        ts = format_timestamp(row["ts"])
        text = row["text"] or "(내용 없음)"

        output.append(f"## {i}. {channel} | {user} | {ts}\n")
        output.append(f"```\n{text}\n```\n")

        # 파일 첨부 확인
        db = get_db()
        files = db.execute("""
            SELECT name, size FROM files WHERE message_id = ?
        """, (row["id"],)).fetchall()
        db.close()

        if files:
            output.append("**첨부 파일:**")
            for f in files:
                output.append(f"  - {f['name']} ({f['size']:,} bytes)")
        output.append("\n---\n")

    return "\n".join(output)

def ask_llm(query: str, context: str) -> str:
    """
    LLM에게 검색 결과를 기반으로 질문 (Karpathy 스타일 RAG)
    """
    if not LLM_PROVIDER:
        return "⚠️ LLM API 키가 설정되지 않았습니다. ANTHROPIC_API_KEY 또는 OPENAI_API_KEY를 .env에 추가하세요."

    prompt = f"""You are a helpful assistant analyzing Slack archive data.

Context (Slack messages matching the search):
{context}

User question: {query}

Provide a concise, informative answer based ONLY on the provided context.
If the context doesn't contain enough information, say so clearly.
Respond in Korean."""

    try:
        if LLM_PROVIDER == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=LLM_API_KEY)
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text

        elif LLM_PROVIDER == "openai":
            import openai
            client = openai.OpenAI(api_key=LLM_API_KEY)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content

    except Exception as e:
        return f"❌ LLM 호출 실패: {str(e)}"

def interactive_mode():
    """
    대화형 검색 모드 (Karpathy 스타일 REPL)
    """
    print("=" * 60)
    print("Slack 아카이브 LLM Wiki 검색 (대화형 모드)")
    print("=" * 60)
    print("명령어: /search <쿼리>, /stats, /quit")
    print()

    while True:
        try:
            user_input = input("🔍 ").strip()

            if not user_input:
                continue

            if user_input in ["/quit", "/exit", "/q"]:
                print("종료합니다.")
                break

            if user_input == "/stats":
                db = get_db()
                msg_count = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
                ch_count = db.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
                db.close()
                print(f"📊 메시지: {msg_count:,}개 | 채널: {ch_count}개")
                continue

            if user_input.startswith("/search "):
                query = user_input[8:].strip()
            else:
                query = user_input

            if len(query) < 2:
                print("❌ 검색어는 2글자 이상이어야 합니다.")
                continue

            print(f"\n🔍 검색 중: '{query}'...")
            results = search_messages(query, limit=5)

            if not results:
                print("결과가 없습니다.\n")
                continue

            # 위키 스타일 출력
            wiki_output = format_wiki_style(results, query)
            print("\n" + wiki_output + "\n")

            # LLM 요약 (옵션)
            if LLM_PROVIDER:
                context = "\n\n".join([r["text"] or "" for r in results if r["text"]])
                if context:
                    print("🤖 LLM 요약 생성 중...")
                    summary = ask_llm(query, context)
                    print(f"\n**요약:**\n{summary}\n")

        except KeyboardInterrupt:
            print("\n종료합니다.")
            break
        except Exception as e:
            print(f"❌ 오류: {e}\n")

def main():
    parser = argparse.ArgumentParser(description="Slack 아카이브 LLM Wiki 검색")
    parser.add_argument("query", nargs="?", help="검색할 키워드")
    parser.add_argument("--limit", type=int, default=10, help="최대 결과 수")
    parser.add_argument("--channel", help="채널로 필터링")
    parser.add_argument("--interactive", "-i", action="store_true", help="대화형 모드")
    parser.add_argument("--llm", action="store_true", help="LLM으로 요약 생성")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print("❌ archive.db가 없습니다. 먼저 Phase 2를 실행하세요.")
        return

    if args.interactive:
        interactive_mode()
        return

    if not args.query:
        parser.print_help()
        return

    # 검색 실행
    results = search_messages(args.query, limit=args.limit, channel=args.channel)

    # 위키 스타일 출력
    wiki_output = format_wiki_style(results, args.query)
    print(wiki_output)

    # LLM 요약 (옵션)
    if args.llm and LLM_PROVIDER and results:
        context = "\n\n".join([r["text"] or "" for r in results if r["text"]])
        print("\n🤖 LLM 요약 생성 중...\n")
        summary = ask_llm(args.query, context)
        print(f"**요약:**\n{summary}")

if __name__ == "__main__":
    main()
