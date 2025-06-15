import prompt_to_text
import extract_images
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
    total_tasks: List[str] = field(default_factory=list)
    exam_topics: List[str] = field(default_factory=list)


def write_progress(updates: Optional[Dict[int, str]] = None):
    """
    Skriver til progress.txt:
      - Hvis `updates` er None: oppdater linje 4 (0-indeks 3) med task_status
      - Ellers: bruk `updates` som {0-indeks linjenr: tekst uten newline}
    """
    try:
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
        else:
            lines = []

        if updates is None:
            status_str = ''.join(str(task_status[t]) for t in total_tasks)
            updates = {3: status_str}

        max_idx = max(updates.keys())
        while len(lines) < max_idx + 1:
            lines.append("\n")

        for idx, text in updates.items():
            lines[idx] = f"{text}\n"

        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)

        for idx, text in updates.items():
            print(f"[STATUS] | Wrote '{text}' to line {idx + 1} in {PROGRESS_FILE}")
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

import re

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

async def get_exam_info(ocr_text: str) -> Exam:
    exam = Exam()

    with SUBJECT_FILE.open("r", encoding="utf-8") as f:
                        first_line = f.readline().strip()
                        if len(first_line) > 4:
                            exam.subject = first_line.strip().upper()
                            print("\n\n\n TOPIC FOUND IN FILE:")
                        else:
                            exam.subject = (
                                await prompt_to_text.async_prompt_to_text(
                                    PROMPT_CONFIG
                                    + load_prompt("get_subject_code")
                                    + ocr_text,
                                    max_tokens=1000,
                                    is_num=False,
                                    max_len=50,
                                )
                            ).strip().upper()
                            print("\n\n\n TOPIC FOUND WITH DEEPSEEK:")

    print(exam.subject+"\n\n\n")
    exam.matching_codes = get_subject_code_variations(exam.subject)
    write_progress({4: exam.subject or ""})
    
    pdf_dir = None
    with DIR_FILE.open("r", encoding="utf-8") as dir_file:
        pdf_dir = dir_file.readline().strip()

    exam_raw_version = (
        await prompt_to_text.async_prompt_to_text(
            PROMPT_CONFIG
            + load_prompt("get_exam_version").format(pdf_dir=pdf_dir)
            + ocr_text,
            max_tokens=1000,
            is_num=False,
            max_len=12,
        )
    )
    version_abbr = exam_raw_version[0].upper() + exam_raw_version[-2:]
    exam.exam_version = version_abbr
    print(f"[DEEPSEEK] | Exam version found: {exam_raw_version}")
    print("[INFO] | Set exam version abbreviation to: " + version_abbr)
    write_progress({5: exam.exam_version or ""})

    exam.total_tasks = (
        await prompt_to_text.async_prompt_to_text(
            PROMPT_CONFIG
            + load_prompt("get_total_tasks")
            + ocr_text,
            max_tokens=1000,
            is_num=False,
            max_len=250
        )
    )
    exam.total_tasks = [task.strip() for task in exam.total_tasks.split(",")]
    print(f"[DEEPSEEK] | Tasks found for processing: {exam.total_tasks}")
    write_progress({6: str(exam.total_tasks)})

    exam.exam_topics = (
        await prompt_to_text.async_prompt_to_text(
            PROMPT_CONFIG
            + load_prompt("exam_topics")
            + ocr_text,
            max_tokens=1000,
            is_num=False,
            max_len=300,
        )
    )
    if exam.exam_topics:
        exam.exam_topics = [t.strip() for t in str(exam.exam_topics).split(',')]
    else:
        exam.exam_topics = []
    print(f"[DEEPSEEK] | Topics found in exam: {exam.exam_topics}")

    global total_tasks
    total_tasks = exam.total_tasks

    await extract_images.extract_images_with_tasks(
        pdf_path=pdf_dir,
        subject=exam.subject,
        version=exam.exam_version,
        output_folder=None,
    )


    return exam

async def process_task(task_number: str, ocr_text: str, exam: Exam) -> Exam:
    task_exam = deepcopy(exam)
    task_exam.task_number = task_number
    task_exam.exam_version = exam.exam_version

    task_output = str(ocr_text)
    valid = 0
    images = 0

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

async def main_async(ocr_text: str):
    exam_template = await get_exam_info(ocr_text)
    print(f"[DEEPSEEK] | Started processing all tasks")

    # Iterate through string identifiers
    tasks = [
        asyncio.create_task(process_task(task, ocr_text, exam_template))
        for task in exam_template.total_tasks
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


def main(ocr_text: str):
    return asyncio.run(main_async(ocr_text))

if __name__ == "__main__":
    ocr_input = sys.stdin.read()
    main(ocr_input)