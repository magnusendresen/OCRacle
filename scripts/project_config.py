from pathlib import Path

"""Centralized configuration constants used throughout the project."""

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ICP_DATA_DIR = PROJECT_ROOT / "icp_data"
PROGRESS_FILE = ICP_DATA_DIR / "progress.txt"
DIR_FILE = ICP_DATA_DIR / "dir.txt"
SUBJECT_FILE = ICP_DATA_DIR / "subject.txt"
IGNORED_FILE = ICP_DATA_DIR / "ignored.txt"

TASKS_JSON = PROJECT_ROOT / "tasks.json"
EXAM_CODES_JSON = PROJECT_ROOT / "ntnu_emner.json"
EXAM_CODES_MERGED_JSON = PROJECT_ROOT / "ntnu_emner_sammenslaatt.json"

IMG_DIR = PROJECT_ROOT / "img"
PDF_DIR = PROJECT_ROOT / "pdf"

PROMPT_CONFIG = (
    "DO AS YOU ARE TOLD AND RESPOND ONLY WITH WHAT IS ASKED FROM YOU. "
    "DO NOT EXPLAIN OR SAY WHAT YOU ARE DOING (e.g. here is the..., below is..., sure here is..., etc.). "
    "DO NOT WRITE ANY SYMBOLS LIKE - OR \\n OR CHANGE LETTER FORMATTING WITH ** AND SIMILAR. "
    "YOU ARE USED IN A TEXT PROCESSING PYTHON PROGRAM SO THE TEXT SHOULD BE PLAIN. "
)

__all__ = [
    "PROJECT_ROOT",
    "ICP_DATA_DIR",
    "PROGRESS_FILE",
    "DIR_FILE",
    "SUBJECT_FILE",
    "IGNORED_FILE",
    "TASKS_JSON",
    "EXAM_CODES_JSON",
    "EXAM_CODES_MERGED_JSON",
    "IMG_DIR",
    "PDF_DIR",
    "PROMPT_CONFIG",
]

def print_config():
    for name in __all__:
        value = globals()[name]
        print(f"{name}: {value}")

print_config()
