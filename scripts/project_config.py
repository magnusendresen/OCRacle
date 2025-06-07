from pathlib import Path

"""Centralized configuration constants used throughout the project."""

# Base directory of the entire project (repo root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Communication files between C++ and Python
ICP_DATA_DIR = PROJECT_ROOT / "icp_data"
ICP_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROGRESS_FILE = ICP_DATA_DIR / "progress.txt"
DIR_FILE = ICP_DATA_DIR / "dir.txt"
SUBJECT_FILE = ICP_DATA_DIR / "subject.txt"

# Main task data file (directly in root)
TASKS_JSON = PROJECT_ROOT / "tasks.json"

# JSON databases for subject information (still in scripts/)
EXAM_CODES_JSON = PROJECT_ROOT / "scripts" / "ntnu_emner.json"
EXAM_CODES_MERGED_JSON = PROJECT_ROOT / "scripts" / "ntnu_emner_sammenslaatt.json"

# Other directories
IMG_DIR = PROJECT_ROOT / "img"
PDF_DIR = PROJECT_ROOT / "pdf"

# Prompt template
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

if __name__ == "__main__":
    print_config()
