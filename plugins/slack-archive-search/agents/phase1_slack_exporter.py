"""
Phase 1: Slack Export ZIP 다운로드 및 파일 수집
에이전트 규칙: 실패해도 계속 진행, 모든 실패는 progress/failed_files.json에 기록
"""
import os, json, zipfile, time, requests
from pathlib import Path
from dotenv import load_dotenv
from utils.progress_tracker import ProgressTracker
from utils.rate_limiter import RateLimiter

# 스크립트 위치 기준으로 기본 경로 설정
SCRIPT_DIR = Path(__file__).parent.parent  # plugins/slack-archive-search/
load_dotenv(SCRIPT_DIR / ".env")

SLACK_USER_TOKEN = os.getenv("SLACK_USER_TOKEN")
FILES_DIR = Path(os.getenv("FILES_DIR", SCRIPT_DIR / "data" / "files"))
EXPORT_DIR = Path(os.getenv("DATA_DIR", SCRIPT_DIR / "data")) / "slack_export"
PROGRESS_DIR = Path(os.getenv("DATA_DIR", SCRIPT_DIR / "data")) / "progress"

# Rate Limiter 설정: Slack API는 Tier별로 다름
# Tier 1: 1 req/min, Tier 2: 20 req/min, Tier 3: 50 req/min, Tier 4: 100 req/min
FILE_DOWNLOAD_RATE = 20  # 파일 다운로드는 보수적으로 분당 20개


def step1_extract_zip(zip_path: str) -> bool:
    """
    STEP 1: ZIP 압축 해제
    - 성공 시 True 반환
    - 실패 시 False 반환 (프로세스 종료하지 않음)
    """
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(EXPORT_DIR)
        print(f"[OK] ZIP 압축 해제 완료: {EXPORT_DIR}")
        return True
    except Exception as e:
        print(f"[ERROR] ZIP 압축 해제 실패: {e}")
        return False


def step2_collect_file_urls() -> list[dict]:
    """
    STEP 2: 모든 메시지 JSON에서 파일 URL 수집
    반환 형식: [{"file_id": str, "name": str, "url": str, "channel": str, "ts": str}]
    """
    files_to_download = []
    if not EXPORT_DIR.exists():
        print("[ERROR] slack_export 디렉토리 없음. Step 1을 먼저 실행하세요.")
        return []

    for channel_dir in EXPORT_DIR.iterdir():
        if not channel_dir.is_dir():
            continue
        channel_name = channel_dir.name

        for json_file in channel_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    messages = json.load(f)

                for msg in messages:
                    if not isinstance(msg, dict):
                        continue
                    for file_info in msg.get("files", []):
                        if "url_private_download" in file_info:
                            files_to_download.append({
                                "file_id": file_info.get("id", "unknown"),
                                "name": file_info.get("name", "file"),
                                "url": file_info["url_private_download"],
                                "channel": channel_name,
                                "ts": msg.get("ts", "0"),
                                "size": file_info.get("size", 0),
                                "mimetype": file_info.get("mimetype", "")
                            })
            except Exception as e:
                print(f"[WARN] JSON 파싱 실패 {json_file}: {e}")
                continue

    print(f"[OK] 다운로드 대상 파일 {len(files_to_download)}개 수집")
    return files_to_download


def step3_download_files(files_to_download: list[dict]) -> dict:
    """
    STEP 3: 파일 다운로드
    - 파일당 최대 3회 재시도
    - Rate Limit: 분당 20개
    - 이미 다운로드된 파일은 스킵
    결과: {"success": int, "failed": int, "skipped": int}
    """
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)

    failed_log = []
    result = {"success": 0, "failed": 0, "skipped": 0}
    headers = {"Authorization": f"Bearer {SLACK_USER_TOKEN}"}

    # 이미 다운로드된 파일 ID 로드
    done_file = PROGRESS_DIR / "downloaded_files.json"
    done_ids = set()
    if done_file.exists():
        with open(done_file) as f:
            done_ids = set(json.load(f))

    for i, file_info in enumerate(files_to_download):
        file_id = file_info["file_id"]

        # 이미 처리된 파일 스킵
        if file_id in done_ids:
            result["skipped"] += 1
            continue

        # 저장 경로 설정
        save_dir = FILES_DIR / file_id
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / file_info["name"]

        # 파일이 이미 존재하면 스킵
        if save_path.exists():
            done_ids.add(file_id)
            result["skipped"] += 1
            continue

        # 다운로드 시도 (최대 3회)
        downloaded = False
        for attempt in range(3):
            try:
                response = requests.get(
                    file_info["url"],
                    headers=headers,
                    stream=True,
                    timeout=60
                )

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    print(f"[RATE LIMIT] {retry_after}초 대기...")
                    time.sleep(retry_after)
                    continue

                if response.status_code == 200:
                    with open(save_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    downloaded = True
                    break
                else:
                    print(f"[WARN] HTTP {response.status_code}: {file_info['name']}")
                    time.sleep(2 ** attempt)  # 지수 백오프

            except Exception as e:
                print(f"[WARN] 다운로드 실패 (시도 {attempt+1}/3): {e}")
                time.sleep(2 ** attempt)

        if downloaded:
            done_ids.add(file_id)
            result["success"] += 1
        else:
            result["failed"] += 1
            failed_log.append(file_info)

        # Rate Limiting: 분당 20개 = 3초 간격
        if (i + 1) % 20 == 0:
            time.sleep(60)
        else:
            time.sleep(3)

        # 진행 상태 저장 (100개마다)
        if (i + 1) % 100 == 0:
            with open(done_file, 'w') as f:
                json.dump(list(done_ids), f)
            print(f"[진행] {i+1}/{len(files_to_download)} 처리 완료")

    # 최종 저장
    with open(done_file, 'w') as f:
        json.dump(list(done_ids), f)

    if failed_log:
        with open(PROGRESS_DIR / "failed_files.json", 'w') as f:
            json.dump(failed_log, f, ensure_ascii=False, indent=2)

    print(f"[DONE] 성공: {result['success']}, 실패: {result['failed']}, 스킵: {result['skipped']}")
    return result


def run_phase1(zip_path: str):
    """Phase 1 실행 진입점"""
    print("=" * 50)
    print("Phase 1: Slack 데이터 다운로드 시작")
    print("=" * 50)

    if not step1_extract_zip(zip_path):
        print("[FATAL] ZIP 압축 해제 실패. Phase 1 중단.")
        return False

    files = step2_collect_file_urls()
    result = step3_download_files(files)

    # DONE 체크리스트
    checks = {
        "ZIP 압축 해제": EXPORT_DIR.exists(),
        "channels.json 존재": (EXPORT_DIR / "channels.json").exists(),
        "users.json 존재": (EXPORT_DIR / "users.json").exists(),
        "파일 다운로드 시작": result["success"] > 0 or result["skipped"] > 0,
    }

    print("\n[Phase 1 DONE 체크리스트]")
    all_ok = True
    for check, status in checks.items():
        icon = "✅" if status else "❌"
        print(f"  {icon} {check}")
        if not status:
            all_ok = False

    return all_ok


if __name__ == "__main__":
    import sys
    zip_path = sys.argv[1] if len(sys.argv) > 1 else "./slack_export.zip"
    run_phase1(zip_path)
