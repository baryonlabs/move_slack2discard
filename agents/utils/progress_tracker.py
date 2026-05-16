"""
agents/utils/progress_tracker.py
Track and persist progress to JSON files
"""
import json
from pathlib import Path

class ProgressTracker:
    def __init__(self, progress_dir: Path):
        self.progress_dir = progress_dir
        self.progress_dir.mkdir(parents=True, exist_ok=True)

    def load(self, filename: str) -> dict:
        path = self.progress_dir / filename
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save(self, filename: str, data: dict):
        path = self.progress_dir / filename
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
