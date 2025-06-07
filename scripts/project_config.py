from pathlib import Path

"""Centralized configuration constants used throughout the project."""

# Base directory containing all Python scripts and related assets
PROJECT_ROOT = Path(__file__).resolve().parent

# File locations
PROGRESS_FILE = PROJECT_ROOT / "progress.txt"
DIR_FILE = PROJECT_ROOT / "dir.txt"
SUBJECT_FILE = PROJECT_ROOT / "subject.txt"
TASKS_JSON = PROJECT_ROOT / "tasks.json"

# JSON databases for subject information
EXAM_CODES_JSON = PROJECT_ROOT / "ntnu_emner.json"
EXAM_CODES_MERGED_JSON = PROJECT_ROOT / "ntnu_emner_sammenslaatt.json"

# Directory locations
IMG_DIR = PROJECT_ROOT / "img"

# Optional directory for stored PDF files (one level above scripts)
PDF_DIR = PROJECT_ROOT.parent / "pdf"

# Prefix for all language model prompts to keep responses short and direct
PROMPT_CONFIG = (
    "DO AS YOU ARE TOLD AND RESPOND ONLY WITH WHAT IS ASKED FROM YOU. "
    "DO NOT EXPLAIN OR SAY WHAT YOU ARE DOING (e.g. here is the..., below is..., sure here is..., etc.). "
    "DO NOT WRITE ANY SYMBOLS LIKE - OR \n OR CHANGE LETTER FORMATTING WITH ** AND SIMILAR. "
    "YOU ARE USED IN A TEXT PROCESSING PYTHON PROGRAM SO THE TEXT SHOULD BE PLAIN. "
)

# Define what gets imported when using 'from project_config import *'
__all__ = [
    "PROJECT_ROOT",
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
