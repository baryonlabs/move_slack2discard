"""
Phase 2: Slack Export JSON → SQLite 파싱
에이전트 규칙:
- INSERT OR IGNORE로 중복 방지
- 모든 DB 작업은 트랜잭션 처리
- 실패 채널은 스킵하고 계속 진행
"""
import os, json, sqlite3
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_PATH = Path(os.getenv("DB_PATH", "./data/archive.db"))
EXPORT_DIR = Path(os.getenv("DATA_DIR", "./data")) / "slack_export"
FILES_DIR = Path(os.getenv("FILES_DIR", "./data/files"))


def get_db() -> sqlite3.Connection:
    """DB 연결 (WAL 모드, Row Factory 설정)"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection):
    """스키마 초기화"""
    schema_path = Path(__file__).parent / "utils" / "schema.sql"
    if schema_path.exists():
        with open(schema_path) as f:
            conn.executescript(f.read())
    else:
        # 인라인 스키마 (schema.sql 없을 때 폴백)
        conn.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS channels (
            id TEXT PRIMARY KEY, name TEXT NOT NULL,
            purpose TEXT DEFAULT '', topic TEXT DEFAULT '',
            is_private INTEGER DEFAULT 0, created_at INTEGER, member_count INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, name TEXT NOT NULL,
            display_name TEXT DEFAULT '', real_name TEXT DEFAULT '',
            avatar_url TEXT DEFAULT '', is_bot INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, channel_id TEXT NOT NULL,
            user_id TEXT, text TEXT DEFAULT '', ts REAL NOT NULL,
            thread_ts REAL, reply_count INTEGER DEFAULT 0, reactions TEXT DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY, message_id TEXT, name TEXT NOT NULL,
            mimetype TEXT DEFAULT '', size INTEGER DEFAULT 0, local_path TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
            text, channel_name, user_name, tokenize='unicode61'
        );
        """)
    conn.commit()
    print("[OK] DB 스키마 초기화 완료")


def parse_users(conn: sqlite3.Connection):
    """users.json 파싱 및 저장"""
    users_file = EXPORT_DIR / "users.json"
    if not users_file.exists():
        print("[WARN] users.json 없음. 스킵.")
        return

    with open(users_file, encoding='utf-8') as f:
        users = json.load(f)

    with conn:
        for user in users:
            if not isinstance(user, dict):
                continue
            profile = user.get("profile", {})
            conn.execute("""
                INSERT OR IGNORE INTO users (id, name, display_name, real_name, avatar_url, is_bot)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user.get("id", ""),
                user.get("name", "unknown"),
                profile.get("display_name", ""),
                profile.get("real_name", ""),
                profile.get("image_72", ""),
                1 if user.get("is_bot") else 0
            ))

    print(f"[OK] 사용자 {len(users)}명 저장 완료")


def parse_channels(conn: sqlite3.Connection):
    """channels.json 파싱 및 저장"""
    channels_file = EXPORT_DIR / "channels.json"
    if not channels_file.exists():
        print("[WARN] channels.json 없음. 스킵.")
        return []

    with open(channels_file, encoding='utf-8') as f:
        channels = json.load(f)

    with conn:
        for ch in channels:
            if not isinstance(ch, dict):
                continue
            conn.execute("""
                INSERT OR IGNORE INTO channels (id, name, purpose, topic, is_private, created_at, member_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                ch.get("id", ""),
                ch.get("name", "unknown"),
                ch.get("purpose", {}).get("value", ""),
                ch.get("topic", {}).get("value", ""),
                1 if ch.get("is_private") else 0,
                ch.get("created", 0),
                len(ch.get("members", []))
            ))

    print(f"[OK] 채널 {len(channels)}개 저장 완료")
    return channels


def parse_messages_for_channel(conn: sqlite3.Connection, channel_id: str, channel_name: str, channel_dir: Path):
    """특정 채널의 모든 메시지 파싱"""
    json_files = sorted(channel_dir.glob("*.json"))
    total_messages = 0
    total_files = 0

    for json_file in json_files:
        try:
            with open(json_file, encoding='utf-8') as f:
                messages = json.load(f)
        except Exception as e:
            print(f"[WARN] {json_file} 파싱 실패: {e}")
            continue

        with conn:
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                if msg.get("type") != "message":
                    continue

                ts = float(msg.get("ts", "0"))
                msg_id = f"{channel_id}_{ts}"
                user_id = msg.get("user", None)
                text = msg.get("text", "")

                # 메시지 저장
                conn.execute("""
                    INSERT OR IGNORE INTO messages
                    (id, channel_id, user_id, text, ts, thread_ts, reply_count, reactions)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    msg_id,
                    channel_id,
                    user_id,
                    text,
                    ts,
                    float(msg["thread_ts"]) if "thread_ts" in msg else None,
                    msg.get("reply_count", 0),
                    json.dumps(msg.get("reactions", []), ensure_ascii=False)
                ))

                total_messages += 1

                # FTS 인덱싱은 트리거(messages_ai)가 자동 처리

                # 첨부 파일 저장
                for file_info in msg.get("files", []):
                    file_id = file_info.get("id", "")
                    if not file_id:
                        continue

                    # 로컬 경로 확인
                    local_path = None
                    expected_path = FILES_DIR / file_id / file_info.get("name", "file")
                    if expected_path.exists():
                        local_path = str(expected_path)

                    conn.execute("""
                        INSERT OR IGNORE INTO files (id, message_id, name, mimetype, size, local_path)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        file_id,
                        msg_id,
                        file_info.get("name", "file"),
                        file_info.get("mimetype", ""),
                        file_info.get("size", 0),
                        local_path
                    ))
                    total_files += 1

    return total_messages, total_files


def run_phase2():
    """Phase 2 실행 진입점"""
    print("=" * 50)
    print("Phase 2: 데이터 파싱 & SQLite 저장 시작")
    print("=" * 50)

    conn = get_db()
    init_db(conn)
    parse_users(conn)
    channels = parse_channels(conn)

    total_msg = 0
    total_file = 0

    # 각 채널 디렉토리 순회
    for channel_dir in EXPORT_DIR.iterdir():
        if not channel_dir.is_dir():
            continue

        # 채널 ID 찾기
        channel_name = channel_dir.name
        channel_id = None
        for ch in channels:
            if ch.get("name") == channel_name:
                channel_id = ch.get("id")
                break

        if not channel_id:
            # channels.json에 없는 채널도 처리 (DM 등)
            channel_id = f"UNKNOWN_{channel_name}"
            conn.execute("""
                INSERT OR IGNORE INTO channels (id, name) VALUES (?, ?)
            """, (channel_id, channel_name))
            conn.commit()

        try:
            msg_count, file_count = parse_messages_for_channel(
                conn, channel_id, channel_name, channel_dir
            )
            total_msg += msg_count
            total_file += file_count
            print(f"  [OK] #{channel_name}: 메시지 {msg_count}개, 파일 {file_count}개")
        except Exception as e:
            print(f"  [ERROR] #{channel_name} 파싱 실패: {e}")
            continue

    conn.close()

    # DONE 체크리스트
    print(f"\n[Phase 2 완료] 총 메시지: {total_msg}개, 총 파일: {total_file}개")

    # 검증 쿼리
    verify_conn = get_db()
    msg_count = verify_conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    fts_count = verify_conn.execute("SELECT COUNT(*) FROM messages_fts").fetchone()[0]
    verify_conn.close()

    checks = {
        "messages 테이블 데이터 존재": msg_count > 0,
        "FTS 인덱스 생성": fts_count > 0,
        "DB 파일 존재": DB_PATH.exists(),
    }

    print("\n[Phase 2 DONE 체크리스트]")
    all_ok = True
    for check, status in checks.items():
        icon = "✅" if status else "❌"
        print(f"  {icon} {check}")
        if not status:
            all_ok = False

    return all_ok


if __name__ == "__main__":
    run_phase2()
