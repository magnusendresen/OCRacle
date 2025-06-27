from datetime import datetime
from time import perf_counter
from contextlib import contextmanager
from typing import List, Dict, Optional
import json

from project_config import PROGRESS_FILE


def read_progress() -> Dict[str, str]:
    """Return the current ``progress.json`` data or an empty dict."""
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def update_progress_lines(lines: Dict[int, str]) -> None:
    """Update ``progress.json`` with 1-indexed line numbers."""
    try:
        data = read_progress()
        for line, text in lines.items():
            data[str(line)] = text
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[ERROR] Could not update progress file: {e}")

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
        if updates is None:
            updates = {}

        total = len(progress) * n_steps
        fraction = sum(progress) / total if total else 0.0
        updates.setdefault(4, f"{fraction:.2f}")

        update_progress_lines({idx + 1: text for idx, text in updates.items()})
    except Exception as e:
        print(f"[ERROR] Could not update progress file: {e}")


def update_progress_fraction(line: int, current: int, total: int) -> None:
    """Update ``progress.json`` with ``current/total`` written to ``line``."""
    try:
        fraction = current / total if total else 0.0
        update_progress_lines({line: f"{fraction:.2f}"})
    except Exception as e:
        print(f"[ERROR] Could not update progress file: {e}")

