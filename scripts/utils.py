from datetime import datetime
from time import perf_counter
from contextlib import contextmanager
from typing import List, Dict, Optional
import json

from project_config import PROGRESS_FILE

def log(message: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] --- {message}")


@contextmanager
def timer(name: str):
    """Context manager for timing code blocks."""
    start = perf_counter()
    try:
        yield
    finally:
        duration = perf_counter() - start
        log(f"{name} completed in {duration:.2f}s")


def write_progress(progress: List[int], n_steps: int, updates: Optional[Dict[int, str]] = None) -> None:
    """Update ``progress.json`` with progress fraction and optional text lines.

    ``progress`` should contain integers between ``0`` and ``n_steps`` for each
    running instance. ``n_steps`` specifies the total number of steps for an
    instance. ``updates`` maps zero-indexed line numbers to text that should be
    written to the JSON file.
    """
    try:
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}

        if updates is None:
            updates = {}

        total = len(progress) * n_steps
        fraction = sum(progress) / total if total else 0.0
        updates.setdefault(3, f"{fraction:.2f}")

        for idx, text in updates.items():
            data[str(idx + 1)] = text

        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[ERROR] Could not update progress file: {e}")

