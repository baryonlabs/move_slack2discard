-- agents/utils/schema.sql
PRAGMA journal_mode=WAL;    -- 동시 읽기/쓰기 허용
PRAGMA foreign_keys=ON;

-- 채널 테이블
CREATE TABLE IF NOT EXISTS channels (
    id          TEXT PRIMARY KEY,   -- Slack 채널 ID (e.g., C01234ABCD)
    name        TEXT NOT NULL,
    purpose     TEXT DEFAULT '',
    topic       TEXT DEFAULT '',
    is_private  INTEGER DEFAULT 0,  -- 0: public, 1: private
    created_at  INTEGER,            -- Unix timestamp
    member_count INTEGER DEFAULT 0
);

-- 사용자 테이블
CREATE TABLE IF NOT EXISTS users (
    id           TEXT PRIMARY KEY,  -- Slack 사용자 ID (e.g., U01234ABCD)
    name         TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    real_name    TEXT DEFAULT '',
    avatar_url   TEXT DEFAULT '',
    is_bot       INTEGER DEFAULT 0
);

-- 메시지 테이블
CREATE TABLE IF NOT EXISTS messages (
    id           TEXT PRIMARY KEY,  -- ts를 ID로 사용 (channel_id + ts)
    channel_id   TEXT NOT NULL,
    user_id      TEXT,
    text         TEXT DEFAULT '',
    ts           REAL NOT NULL,     -- Unix timestamp (소수점 포함)
    thread_ts    REAL,              -- 스레드 부모 ts (null이면 독립 메시지)
    reply_count  INTEGER DEFAULT 0,
    reactions    TEXT DEFAULT '[]', -- JSON string
    FOREIGN KEY (channel_id) REFERENCES channels(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 파일 테이블
CREATE TABLE IF NOT EXISTS files (
    id          TEXT PRIMARY KEY,   -- Slack 파일 ID
    message_id  TEXT,
    name        TEXT NOT NULL,
    mimetype    TEXT DEFAULT '',
    size        INTEGER DEFAULT 0,  -- bytes
    local_path  TEXT,               -- 로컬 저장 경로 (null이면 미다운로드)
    FOREIGN KEY (message_id) REFERENCES messages(id)
);

-- FTS5 전문 검색 인덱스 (한국어 포함)
-- content 테이블 연동 없이 독립적 운영 (트리거로 수동 삽입)
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    text,
    channel_name,
    user_name,
    tokenize='unicode61'
);

-- FTS 트리거: 메시지 삽입 시 자동 인덱싱
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, text, channel_name, user_name)
    VALUES (
        new.rowid,
        new.text,
        COALESCE((SELECT name FROM channels WHERE id = new.channel_id), ''),
        COALESCE((SELECT display_name FROM users WHERE id = new.user_id), '')
    );
END;

-- 마이그레이션 진행 상태
CREATE TABLE IF NOT EXISTS migration_progress (
    key     TEXT PRIMARY KEY,
    value   TEXT
);
