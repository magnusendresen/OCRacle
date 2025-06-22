import prompt_to_text
import extract_images
import task_boundaries
import ocr_pdf
from project_config import *

import asyncio
import json
import sys
import re
import difflib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from copy import deepcopy
from collections import defaultdict

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

def load_prompt(name: str) -> str:
    with open(PROMPT_DIR / f"{name}.txt", "r", encoding="utf-8") as f:
        return f.read()

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

# Paths and global state
JSON_PATH = EXAM_CODES_JSON
task_status = defaultdict(lambda: 0)
total_task_count = 0

def load_emnekart_from_json(json_path: Path):
    """
    Leser hele JSON-listen og returnerer:
      - data: rå liste av oppføringer
      - emnekart: dict fra Emnekode (uppercase) -> Emnenavn
    """
    if not json_path.is_file():
        print(f"❌ Feil: JSON-filen '{json_path}' finnes ikke.", file=sys.stderr)
        sys.exit(1)
    try:
        with json_path.open(encoding="utf-8") as jf:
            data = json.load(jf)
    except Exception as e:
        print(f"❌ Kunne ikke lese JSON: {e}", file=sys.stderr)
        sys.exit(1)

    emnekart = {}
    for entry in data:
        kode = entry.get("Emnekode")
        navn = entry.get("Emnenavn")
        if kode and navn:
            emnekart[kode.upper()] = navn
    return data, emnekart

@dataclass
class Exam:
    subject: Optional[str] = None
    matching_codes: List[str] = field(default_factory=list)
    topic: Optional[str] = None
    exam_version: Optional[str] = None
    task_number: Optional[str] = None
    points: Optional[int] = None
    task_text: Optional[str] = None
    images: List[str] = field(default_factory=list)
    code: Optional[str] = None
    total_tasks: int = 0
    exam_topics: List[str] = field(default_factory=list)
    task_numbers: List[str] = field(default_factory=list)
    ocr_tasks: Dict[str, str] = field(default_factory=dict)


def write_progress(updates: Optional[Dict[int, str]] = None):
    """
    Write updates to ``progress.json``.
    ``updates`` should map zero-indexed line numbers to text. If ``updates`` is
    ``None`` the function will write the current task_status to key ``4``
    (1-indexed in the JSON file).
    """
    try:
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}

        if updates is None:
            status_str = ''.join(str(task_status[t]) for t in range(1, total_task_count + 1))
            updates = {3: status_str}

        for idx, text in updates.items():
            data[str(idx + 1)] = text

        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)

        for idx, text in updates.items():
            print(f"[STATUS] | Wrote '{text}' to key {idx + 1} in {PROGRESS_FILE}")
    except Exception as e:
        print(f"[ERROR] Could not update progress file: {e}")

def get_topics(emnekode: str) -> str:
    """
    Return comma-separated unique 'Temaer' for matching emnekoder,
    or default list if fewer than 6 topics are found.
    """
    json_path = EXAM_CODES_JSON

    with json_path.open('r', encoding='utf-8') as f:
        data = json.load(f)

    all_codes = [entry.get("Emnekode", "").upper() for entry in data]
    matches = difflib.get_close_matches(emnekode.upper(), all_codes, n=len(all_codes), cutoff=0.6)

    unike_temaer = set()

    for entry in data:
        if entry.get("Emnekode", "").upper() in matches:
            temaer = entry.get("Temaer", [])
            unike_temaer.update(map(str.strip, temaer))

    if len(unike_temaer) < 3:
        print("\n Fewer than 3 topics found in subject, returning empty string.\n")
        return ""

    print("\n Topics found in subject, using results as reference.\n")
    return ", ".join(sorted(unike_temaer))

def add_topics(topic: str, exam: Exam):
    """
    Adds a topic to the JSON file for matching subject codes if it doesn't already exist.
    """
    try:
        with JSON_PATH.open('r', encoding='utf-8') as jf:
            json_data = json.load(jf)
        for entry in json_data:
            if entry.get("Emnekode", "").upper() in exam.matching_codes:
                temas = entry.get("Temaer", [])
                exists = any(
                    difflib.SequenceMatcher(None, t.lower(), topic.lower()).ratio() >= 0.9
                    for t in temas
                )
                if not exists:
                    temas.append(topic)
                    entry["Temaer"] = temas
        with JSON_PATH.open('w', encoding='utf-8') as jf:
            json.dump(json_data, jf, ensure_ascii=False, indent=4)
        print(f"[DEEPSEEK] | Lagt til tema '{topic}' for emnekoder {exam.matching_codes}")
    except Exception as e:
        print(f"[ERROR] Kunne ikke oppdatere temaer i JSON: {e}", file=sys.stderr)

SUBJECT_REGEX = re.compile(r"[A-Z]{2,}[A-Z0-9]*\d{2,}")

def clean_subject_code(raw: str) -> str:
    """Return a sanitized subject code or 'UNKNOWN' if none found."""
    cand = re.sub(r"[^A-Z0-9]", "", raw.upper())
    match = SUBJECT_REGEX.search(cand)
    return match.group(0) if match else "UNKNOWN"

def guess_code_from_filename(pdf_path: str) -> str:
    match = SUBJECT_REGEX.search(Path(pdf_path).stem.upper())
    return match.group(0) if match else ""

def get_subject_code_variations(subject: str):
    data, emnekart = load_emnekart_from_json(JSON_PATH)
    pattern_parts = []

    for ch in subject:
        if ch == 'Y':
            pattern_parts.append(r'\d')  # ett valgfritt siffer
        else:
            pattern_parts.append(re.escape(ch))  # bokstavelig match

    regex = re.compile('^' + ''.join(pattern_parts) + '$')

    matching_codes = [kode for kode in emnekart if regex.match(kode)]
    if matching_codes:
        print(f"[INFO] | Fant matchende emnekoder i JSON: {matching_codes}")
        return matching_codes
    else:
        print(f"[INFO] | Ingen matchende emnekoder i JSON.")
        return []

async def get_exam_info() -> Exam:
    print("[INFO] | get_exam_info")
    exam = Exam()

    try:
        with DIR_FILE.open("r", encoding="utf-8") as dir_file:
            pdf_dir = json.load(dir_file).get("exam", "").strip()
    except Exception as e:
        print(f"[ERROR] Could not read dir.json: {e}")
        pdf_dir = ""

    pdf_path = Path(pdf_dir)
    if not pdf_path.is_absolute():
        candidate = PDF_DIR / pdf_path
        if candidate.exists():
            pdf_path = candidate
    if not pdf_path.exists():
        print(f"[WARNING] PDF file not found: {pdf_path}")
    pdf_dir = str(pdf_path)

    print("[INFO] | Processing PDF contents")

    containers, task_map, ranges, assigned_tasks = await task_boundaries.detect_task_boundaries(str(pdf_path))
    cropped = task_boundaries.crop_tasks(
        str(pdf_path), containers, ranges, assigned_tasks, temp_dir=Path(__file__).parent / "temp"
    )
    print("[INFO] | Processing cropped task images with Google Vision")
    ocr_results = await ocr_pdf.ocr_images([img for _, img in cropped])
    ocr_text = " ".join(ocr_results)
    exam.ocr_tasks = {}
    for (task_num, _), text in zip(cropped, ocr_results):
        exam.ocr_tasks[task_num] = exam.ocr_tasks.get(task_num, "") + text
    exam.task_numbers = assigned_tasks
    exam.total_tasks = len(assigned_tasks)
    write_progress({6: str(exam.total_tasks)})

    with SUBJECT_FILE.open("r", encoding="utf-8") as f:
        first_line = f.readline().strip()
        if len(first_line) > 4:
            exam.subject = clean_subject_code(first_line)
        else:
            print("[PROMPT] | get_subject_code")
            raw_subject = (
                await prompt_to_text.async_prompt_to_text(
                    PROMPT_CONFIG + load_prompt("get_subject_code") + ocr_text,
                    max_tokens=1000,
                    is_num=False,
                    max_len=50,
                )
            )
            exam.subject = clean_subject_code(raw_subject)
    if exam.subject == "UNKNOWN":
        guess = guess_code_from_filename(pdf_path)
        if guess:
            print(f"[INFO] | Guessed subject code from filename: {guess}")
            exam.subject = guess
    print(f"[INFO] | Subject code detected: {exam.subject}")
    exam.matching_codes = get_subject_code_variations(exam.subject)
    write_progress({4: exam.subject or ""})

    print("[PROMPT] | get_exam_version")
    exam_raw_version = await prompt_to_text.async_prompt_to_text(
        PROMPT_CONFIG + load_prompt("get_exam_version") + ocr_text,
        max_tokens=1000,
        is_num=False,
        max_len=12,
    )
    exam_raw_version = str(exam_raw_version).strip()
    if len(exam_raw_version) >= 3:
        version_abbr = exam_raw_version[0].upper() + exam_raw_version[-2:]
    else:
        version_abbr = exam_raw_version.upper()
    exam.exam_version = version_abbr
    write_progress({5: exam.exam_version or ""})

    await extract_images.extract_figures(
        str(pdf_path), containers, task_map, exam.subject, exam.exam_version
    )

    print("[PROMPT] | exam_topics")
    exam.exam_topics = await prompt_to_text.async_prompt_to_text(
        PROMPT_CONFIG + load_prompt("exam_topics") + ocr_text,
        max_tokens=1000,
        is_num=False,
        max_len=300,
    )
    if exam.exam_topics:
        exam.exam_topics = [t.strip() for t in str(exam.exam_topics).split(',')]
    else:
        exam.exam_topics = []

    global total_task_count
    total_task_count = exam.total_tasks
    print(f"[DEEPSEEK] | Total tasks for processing: {exam.total_tasks}")

    return exam

async def process_task(task_number: str, exam: Exam) -> Exam:
    print(f"[INFO] | process_task {task_number}")
    task_exam = deepcopy(exam)
    task_exam.task_number = task_number
    task_exam.exam_version = exam.exam_version

    task_output = str(exam.ocr_tasks.get(task_number, ""))
    valid = 0
    images = 0

    print(f"[PROMPT] | extract_task_text for task {task_number}")
    task_output = str(
        await prompt_to_text.async_prompt_to_text(
            PROMPT_CONFIG + load_prompt("extract_task_text").format(task_number=task_number) + task_output,
            max_tokens=1000,
            is_num=False,
            max_len=2000,
        )
    )
    task_status[task_number] = 1
    write_progress()

    print(f"[PROMPT] | detect_images for task {task_number}")
    images = int(
        await prompt_to_text.async_prompt_to_text(
            PROMPT_CONFIG + load_prompt("detect_images") + task_output,
            max_tokens=1000,
            is_num=True,
            max_len=2,
        )
    )
    if images > 0:
        print(f"[DEEPSEEK] | Images were found in task {task_number}.")
        task_dir = IMG_DIR / task_exam.subject / task_exam.exam_version / task_number
        if task_dir.exists():
            found_images = sorted(task_dir.glob("*.png"))
            task_exam.images = [str(img.relative_to(PROJECT_ROOT)) for img in found_images]
        else:
            task_exam.images = []
        print(f"[DEEPSEEK] | Found {len(task_exam.images)} images for task {task_number}.")
    else:
        print(f"[DEEPSEEK] | No images were found in task {task_number}.")
        task_exam.images = []
    task_status[task_number] = 2
    write_progress()

    print(f"[PROMPT] | extract_points for task {task_number}")
    points_str = await prompt_to_text.async_prompt_to_text(
        PROMPT_CONFIG + load_prompt("extract_points") + task_output,
        max_tokens=1000,
        is_num=True,
        max_len=2,
    )
    try:
        task_exam.points = int(points_str) if points_str is not None else None
    except (TypeError, ValueError):
        task_exam.points = None
    task_status[task_number] = 3
    write_progress()

    reference = get_topics(exam.subject)
    if exam.exam_topics:
        topics_str = ", ".join(exam.exam_topics)
        reference = f"{reference}, {topics_str}" if reference else topics_str
    print(f"[PROMPT] | extract_topic for task {task_number}")
    task_exam.topic = str(
        await prompt_to_text.async_prompt_to_text(
            PROMPT_CONFIG + load_prompt("extract_topic") + reference + task_output,
            max_tokens=1000,
            is_num=False,
            max_len=100,
        )
    )
    print(f"[DEEPSEEK] | Topic found for task {task_number}: {task_exam.topic}")
    add_topics(task_exam.topic, exam)
    task_status[task_number] = 4
    write_progress()

    for step_idx, instruction in enumerate([
        "translate_to_bokmaal",
        "remove_exam_admin",
        "format_html_output",
    ], start=5):
        print(f"[PROMPT] | {instruction} for task {task_number}")
        task_output = str(
            await prompt_to_text.async_prompt_to_text(
                PROMPT_CONFIG + load_prompt(instruction) + task_output,
                max_tokens=1000,
                is_num=False,
                max_len=2000,
            )
        )
        print(f"\n\n\nOppgave {task_number}:\n{task_output}\n\n\n\n")
        task_status[task_number] = step_idx
        write_progress()

    print(f"[PROMPT] | validate_task for task {task_number}")
    valid = int(
        await prompt_to_text.async_prompt_to_text(
            PROMPT_CONFIG + load_prompt("validate_task") + task_output,
            max_tokens=1000,
            is_num=True,
            max_len=2,
        )
    )
    task_status[task_number] = 8
    write_progress()

    task_exam.task_text = task_output

    if valid == 0:
        print(f"[DEEPSEEK] [TASK {task_number}] | Task not approved.\n")
        return task_exam
    else:
        print(f"[DEEPSEEK] [TASK {task_number}] | Task approved.\n")
        return task_exam

async def main_async():
    print("[INFO] | task_processing.main_async")
    exam_template = await get_exam_info()
    print(f"[DEEPSEEK] | Started processing all tasks")

    tasks = [
        asyncio.create_task(process_task(str(task), exam_template))
        for task in exam_template.task_numbers
    ]
    results = await asyncio.gather(*tasks)

    failed = [res.task_number for res in results if res.task_text is None]
    points = [res.points for res in results if res.task_text is not None]

    # Bilder beholdes for fremtidig bruk og slettes ikke automatisk

    for res in results:
        if res.task_text is not None:
            print(f"Result for task {res.task_number}: {res.task_text}\n   (Points: {res.points})\n")

    print(f"[DEEPSEEK] | Failed tasks: {failed}")
    print(f"[DEEPSEEK] | Points for tasks: {points}")
    print(f"[DEEPSEEK] | Final total cost: {prompt_to_text.total_cost:.4f} USD")
    return results


def main():
    return asyncio.run(main_async())

if __name__ == "__main__":
    main()
