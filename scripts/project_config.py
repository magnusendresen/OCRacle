from pathlib import Path

"""Centralized configuration constants used throughout the project."""

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ICP_DATA_DIR = PROJECT_ROOT / "icp_data"
PROGRESS_FILE = ICP_DATA_DIR / "progress.json"
DIR_FILE = ICP_DATA_DIR / "dir.json"
SUBJECT_FILE = ICP_DATA_DIR / "subject.txt"
IGNORED_FILE = ICP_DATA_DIR / "ignored.txt"


EXAMS_JSON = PROJECT_ROOT / "exams.json"

IMG_DIR = PROJECT_ROOT / "img"
PDF_DIR = PROJECT_ROOT / "pdf"
PROMPT_DIR = PROJECT_ROOT / "prompts"

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
    "EXAMS_JSON",
    "IMG_DIR",
    "PDF_DIR",
    "PROMPT_CONFIG",
]

def load_prompt(name: str) -> str:
    with open(PROMPT_DIR / f"{name}.txt", "r", encoding="utf-8") as f:
        content = f.read()
        if len(content.strip()) == 0:
            print(f"Warning: Prompt '{name}' is empty.")
        return content
    
# def print_config():
#     for name in __all__:
#         value = globals()[name]
#         print(f"{name}: {value}")

# print_config()
