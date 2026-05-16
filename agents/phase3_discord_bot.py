"""
Phase 3: Discord 아카이브 검색 봇
슬래시 명령어:
  /search <query> [channel] [limit]  - 메시지 전문 검색
  /download <file_id>                - 파일 다운로드
  /channel <channel_name>            - 채널 최근 메시지 조회
  /stats                             - 아카이브 통계

에이전트 규칙:
  - 모든 슬래시 명령은 반드시 defer()로 시작한다 (3초 제한 회피)
  - 검색 결과는 최대 10개로 제한한다
  - 파일 크기 25MB 초과 시 파일 경로 정보만 제공한다
"""
import os, sqlite3, asyncio
from pathlib import Path
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))
DB_PATH = Path(os.getenv("DB_PATH", "./data/archive.db"))
FILES_DIR = Path(os.getenv("FILES_DIR", "./data/files"))

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25MB Discord 제한
MAX_SEARCH_RESULTS = 10
MAX_EMBED_DESCRIPTION = 3500  # 4096 미만으로 여유 있게 설정


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def format_timestamp(ts: float) -> str:
    """Unix timestamp → 읽기 쉬운 날짜 문자열"""
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "날짜 불명"


def truncate_text(text: str, max_len: int = 200) -> str:
    """긴 텍스트 자르기"""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


# --- Bot 설정 ---
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


@bot.event
async def on_ready():
    print(f"[OK] {bot.user} 봇 실행 중")
    try:
        guild = discord.Object(id=DISCORD_GUILD_ID)
        synced = await tree.sync(guild=guild)
        print(f"[OK] 슬래시 명령어 {len(synced)}개 동기화 완료")
    except Exception as e:
        print(f"[ERROR] 명령어 동기화 실패: {e}")


# --- /search 명령어 ---
@tree.command(
    name="search",
    description="Slack 아카이브에서 메시지를 검색합니다",
    guild=discord.Object(id=DISCORD_GUILD_ID)
)
@app_commands.describe(
    query="검색할 키워드",
    channel="특정 채널로 제한 (선택)",
    limit="최대 결과 수 (기본: 5, 최대: 10)"
)
async def search_command(
    interaction: discord.Interaction,
    query: str,
    channel: str = None,
    limit: int = 5
):
    # 반드시 defer()로 시작 (3초 제한 회피)
    await interaction.response.defer(thinking=True)

    # 입력 검증
    if not query or len(query.strip()) < 2:
        await interaction.followup.send("❌ 검색어는 2글자 이상이어야 합니다.", ephemeral=True)
        return

    limit = min(max(1, limit), MAX_SEARCH_RESULTS)

    try:
        db = get_db()

        if channel:
            # 채널 필터 포함 검색
            rows = db.execute("""
                SELECT m.id, m.text, m.ts, m.channel_id,
                       c.name as channel_name,
                       u.display_name as user_name
                FROM messages_fts fts
                JOIN messages m ON fts.rowid = m.rowid
                LEFT JOIN channels c ON m.channel_id = c.id
                LEFT JOIN users u ON m.user_id = u.id
                WHERE messages_fts MATCH ?
                  AND c.name = ?
                ORDER BY m.ts DESC
                LIMIT ?
            """, (query, channel, limit)).fetchall()
        else:
            rows = db.execute("""
                SELECT m.id, m.text, m.ts, m.channel_id,
                       c.name as channel_name,
                       u.display_name as user_name
                FROM messages_fts fts
                JOIN messages m ON fts.rowid = m.rowid
                LEFT JOIN channels c ON m.channel_id = c.id
                LEFT JOIN users u ON m.user_id = u.id
                WHERE messages_fts MATCH ?
                ORDER BY m.ts DESC
                LIMIT ?
            """, (query, limit)).fetchall()

        db.close()

        if not rows:
            await interaction.followup.send(f"🔍 **'{query}'** 검색 결과가 없습니다.")
            return

        # Embed 생성
        embed = discord.Embed(
            title=f"🔍 검색 결과: '{query}'",
            description=f"총 {len(rows)}개 결과",
            color=0x4A90D9
        )

        for row in rows:
            channel_name = row["channel_name"] or "unknown"
            user_name = row["user_name"] or "unknown"
            text = truncate_text(row["text"] or "(내용 없음)", 200)
            date_str = format_timestamp(row["ts"])

            # Field 값 4096자 제한 준수
            field_value = f"**채널:** #{channel_name}\n**작성자:** {user_name}\n**날짜:** {date_str}\n```{text}```"
            if len(field_value) > 1024:
                field_value = field_value[:1021] + "..."

            embed.add_field(
                name=f"📌 {date_str}",
                value=field_value,
                inline=False
            )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"[ERROR] /search 오류: {e}")
        await interaction.followup.send(f"❌ 검색 중 오류가 발생했습니다: {str(e)[:100]}")


# --- /download 명령어 ---
@tree.command(
    name="download",
    description="아카이브에서 파일을 다운로드합니다",
    guild=discord.Object(id=DISCORD_GUILD_ID)
)
@app_commands.describe(file_id="Slack 파일 ID (F로 시작)")
async def download_command(interaction: discord.Interaction, file_id: str):
    await interaction.response.defer(thinking=True)

    try:
        db = get_db()
        file_row = db.execute("""
            SELECT f.id, f.name, f.mimetype, f.size, f.local_path,
                   m.ts, c.name as channel_name
            FROM files f
            LEFT JOIN messages m ON f.message_id = m.id
            LEFT JOIN channels c ON m.channel_id = c.id
            WHERE f.id = ?
        """, (file_id,)).fetchone()
        db.close()

        if not file_row:
            await interaction.followup.send(f"❌ 파일 ID `{file_id}` 를 찾을 수 없습니다.")
            return

        local_path = file_row["local_path"]

        if not local_path or not Path(local_path).exists():
            embed = discord.Embed(
                title="⚠️ 파일 미다운로드",
                description=f"파일 `{file_row['name']}` 은 로컬에 없습니다.\n\nPhase 1을 재실행하여 파일을 다운로드하세요.",
                color=0xFF9900
            )
            embed.add_field(name="파일 ID", value=file_id, inline=True)
            embed.add_field(name="파일명", value=file_row["name"], inline=True)
            embed.add_field(name="크기", value=f"{file_row['size']:,} bytes", inline=True)
            await interaction.followup.send(embed=embed)
            return

        file_size = Path(local_path).stat().st_size

        if file_size > MAX_FILE_SIZE_BYTES:
            # 25MB 초과: 파일 정보만 제공
            embed = discord.Embed(
                title="📁 파일 정보 (크기 초과)",
                description=f"파일 크기가 25MB를 초과하여 Discord에 직접 업로드할 수 없습니다.",
                color=0xFF6B6B
            )
            embed.add_field(name="파일명", value=file_row["name"], inline=False)
            embed.add_field(name="크기", value=f"{file_size / 1024 / 1024:.1f} MB", inline=True)
            embed.add_field(name="경로", value=f"`{local_path}`", inline=False)
            await interaction.followup.send(embed=embed)
        else:
            # 25MB 이하: 직접 업로드
            discord_file = discord.File(local_path, filename=file_row["name"])
            embed = discord.Embed(
                title="📎 파일 다운로드",
                color=0x00AA44
            )
            embed.add_field(name="채널", value=f"#{file_row['channel_name']}", inline=True)
            embed.add_field(name="날짜", value=format_timestamp(file_row["ts"]), inline=True)
            await interaction.followup.send(embed=embed, file=discord_file)

    except Exception as e:
        print(f"[ERROR] /download 오류: {e}")
        await interaction.followup.send(f"❌ 다운로드 중 오류 발생: {str(e)[:100]}")


# --- /channel 명령어 ---
@tree.command(
    name="channel",
    description="특정 채널의 최근 메시지를 조회합니다",
    guild=discord.Object(id=DISCORD_GUILD_ID)
)
@app_commands.describe(
    channel_name="조회할 채널 이름 (# 제외)",
    limit="조회할 메시지 수 (기본: 5)"
)
async def channel_command(interaction: discord.Interaction, channel_name: str, limit: int = 5):
    await interaction.response.defer(thinking=True)

    limit = min(max(1, limit), MAX_SEARCH_RESULTS)

    try:
        db = get_db()
        rows = db.execute("""
            SELECT m.id, m.text, m.ts, u.display_name as user_name,
                   (SELECT COUNT(*) FROM files WHERE message_id = m.id) as file_count
            FROM messages m
            LEFT JOIN channels c ON m.channel_id = c.id
            LEFT JOIN users u ON m.user_id = u.id
            WHERE c.name = ?
            ORDER BY m.ts DESC
            LIMIT ?
        """, (channel_name, limit)).fetchall()
        db.close()

        if not rows:
            await interaction.followup.send(f"❌ 채널 `#{channel_name}` 을 찾을 수 없거나 메시지가 없습니다.")
            return

        embed = discord.Embed(
            title=f"📢 #{channel_name} 최근 메시지",
            color=0x36393F
        )

        for row in rows:
            text = truncate_text(row["text"] or "(내용 없음)", 150)
            file_badge = f" 📎{row['file_count']}개" if row["file_count"] > 0 else ""

            embed.add_field(
                name=f"{row['user_name'] or 'unknown'} | {format_timestamp(row['ts'])}{file_badge}",
                value=text if text else "(내용 없음)",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"[ERROR] /channel 오류: {e}")
        await interaction.followup.send(f"❌ 채널 조회 중 오류 발생: {str(e)[:100]}")


# --- /stats 명령어 ---
@tree.command(
    name="stats",
    description="Slack 아카이브 통계를 표시합니다",
    guild=discord.Object(id=DISCORD_GUILD_ID)
)
async def stats_command(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    try:
        db = get_db()
        msg_count = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        channel_count = db.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
        user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        file_count = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        local_file_count = db.execute("SELECT COUNT(*) FROM files WHERE local_path IS NOT NULL").fetchone()[0]
        db.close()

        embed = discord.Embed(
            title="📊 Slack 아카이브 통계",
            color=0x7289DA
        )
        embed.add_field(name="💬 총 메시지", value=f"{msg_count:,}개", inline=True)
        embed.add_field(name="📢 채널 수", value=f"{channel_count:,}개", inline=True)
        embed.add_field(name="👥 사용자 수", value=f"{user_count:,}명", inline=True)
        embed.add_field(name="📎 첨부 파일", value=f"{file_count:,}개 (로컬: {local_file_count:,}개)", inline=False)

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"[ERROR] /stats 오류: {e}")
        await interaction.followup.send(f"❌ 통계 조회 중 오류 발생: {str(e)[:100]}")


def run_phase3():
    """Phase 3 실행 진입점"""
    print("=" * 50)
    print("Phase 3: Discord Bot 시작")
    print("=" * 50)

    if not DISCORD_BOT_TOKEN:
        print("[FATAL] DISCORD_BOT_TOKEN 환경 변수가 없습니다.")
        return False

    if not DB_PATH.exists():
        print("[FATAL] archive.db 없음. Phase 2를 먼저 실행하세요.")
        return False

    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    run_phase3()
