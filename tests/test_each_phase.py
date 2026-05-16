"""
tests/test_each_phase.py
Basic validation tests for all phases
"""
import os
import pytest
from pathlib import Path

@pytest.fixture
def env_setup():
    os.environ["DATA_DIR"] = "./data"
    os.environ["DB_PATH"] = "./data/archive.db"
    os.environ["FILES_DIR"] = "./data/files"
    yield
    # Cleanup if needed

def test_phase1_zip_extract(env_setup, tmp_path):
    """Test ZIP extraction logic (mock)"""
    from agents.phase1_slack_exporter import step1_extract_zip
    zip_path = tmp_path / "test.zip"
    zip_path.write_bytes(b"PK\x03\x04")  # Minimal invalid ZIP
    result = step1_extract_zip(str(zip_path))
    assert isinstance(result, bool)

def test_phase2_db_init(env_setup):
    """Test DB schema initialization"""
    from agents.phase2_data_parser import get_db, init_db
    conn = get_db()
    init_db(conn)
    # Check tables exist
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = [t[0] for t in tables]
    assert "channels" in table_names
    assert "users" in table_names
    assert "messages" in table_names
    assert "files" in table_names
    assert "messages_fts" in table_names
    conn.close()

def test_phase3_discord_bot_import():
    """Test Phase 3 bot imports correctly"""
    try:
        import agents.phase3_discord_bot as bot
        assert hasattr(bot, "run_phase3")
    except ImportError as e:
        pytest.fail(f"Failed to import Phase 3 bot: {e}")
