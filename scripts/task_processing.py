import prompt_to_text
import extract_images
import task_boundaries
import ocr_pdf
from project_config import *
from project_config import load_prompt
from utils import log, write_progress, update_progress_fraction
import object_handling

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
from time import perf_counter
from enum import Enum


# Number of processing steps for each task in the LLM pipeline
LLM_STEPS = 8

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

# Paths and global state
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
    topic: Optional[str] = None
    exam_version: Optional[str] = None
    task_number: Optional[str] = None
    points: Optional[int] = None
    task_text: Optional[str] = None
    # Images are handled automatically in the HTML layer
    # Code snippets are embedded directly in the task text
    exam_topics: List[str] = field(default_factory=list)
    task_numbers: List[str] = field(default_factory=list)
    ocr_tasks: Dict[str, str] = field(default_factory=dict)


def get_topics_from_json(emnekode: str) -> Enum:
    """Return available topics for a subject code."""
    with EXAMS_JSON.open('r', encoding='utf-8') as f:
        data = json.load(f)

    entry = data.get(emnekode.upper().strip(), {})
    topics = [t for t in entry.get("topics", []) if t is not None]
    return Enum('Temaer', topics)


def enum_to_str(enum: Enum) -> str:
    return str([f"{e.value}: {e.name}" for e in enum])

def get_topic_from_enum(topic_enum: Enum, num: int) -> str:
    """Get topic name from enum based on enum and number."""
    for topic in topic_enum:
        if topic.value == num:
            return topic.name
    return "Unknown Topic"

async def get_exam_info() -> Exam:
    log("Processing PDF contents")
    exam = Exam()
    global total_task_count

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

    from utils import timer, update_progress_fraction

    def _det_cb(current: int, total: int):
        update_progress_fraction(8, current, total)

    log("Finding task boundaries")
    with timer("Detecting task boundaries"):
        containers, task_map, ranges, assigned_tasks, extra = await task_boundaries.detect_task_boundaries(
            str(pdf_path), progress_callback=_det_cb
        )
    log("Cropping detected tasks")

    with timer("Cropping tasks"):
        cropped = task_boundaries.crop_tasks(
            str(pdf_path), containers, ranges, assigned_tasks,
            temp_dir=Path(__file__).parent / "temp",
            progress_callback=None,
        )
        extra_cropped = (
            task_boundaries.crop_tasks(
                str(pdf_path), [extra], [(0, 1)], ["header"],
                temp_dir=Path(__file__).parent / "temp",
                progress_callback=lambda _: None,
            )
            if extra
            else []
        )
    log("Processing task images with Google Vision")
    ocr_inputs = [img for _, img in extra_cropped] + [img for _, img in cropped]
    with timer("OCR processing"):
        ocr_results = await ocr_pdf.ocr_images(ocr_inputs)
    
    header_text = ocr_results[0] if extra_cropped else ""
    task_results = ocr_results[1:] if extra_cropped else ocr_results
    ocr_text = " ".join([header_text] + task_results)
    exam.ocr_tasks = {}
    for (task_num, _), text in zip(cropped, task_results):
        exam.ocr_tasks[task_num] = exam.ocr_tasks.get(task_num, "") + text
    exam.task_numbers = assigned_tasks
    total_task_count = len(assigned_tasks)
    progress = [task_status[t] for t in range(1, total_task_count + 1)]
    write_progress(progress, LLM_STEPS, {6: str(total_task_count)})
    write_progress(progress, LLM_STEPS, {8: str(LLM_STEPS)})

    with SUBJECT_FILE.open("r", encoding="utf-8") as f:
        first_line = f.readline().strip()
        if len(first_line) > 4:
            exam.subject = first_line.strip().upper()
            log("Subject code read from file")
        else:
            log("Prompting subject code")
            exam.subject = (
                await prompt_to_text.async_prompt_to_text(
                    PROMPT_CONFIG + load_prompt("get_subject_code") + ocr_text,
                    max_tokens=1000,
                    is_num=False,
                    max_len=50,
                )
            ).strip().upper()
    log(f"Subject code: {exam.subject}")
    object_handling.add_subject(exam.subject)
    progress = [task_status[t] for t in range(1, total_task_count + 1)]
    write_progress(progress, LLM_STEPS, {4: exam.subject or ""})

    log("Prompting exam version")
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
    object_handling.add_exam(exam.subject, exam.exam_version)
    progress = [task_status[t] for t in range(1, total_task_count + 1)]
    write_progress(progress, LLM_STEPS, {5: exam.exam_version or ""})

    with timer("Extracting figures"):
        await extract_images.extract_figures(
            str(pdf_path), containers, task_map, exam.subject, exam.exam_version
        )

    log("Extracting exam topics")

    try:
        topics = enum_to_str(get_topics_from_json(exam.subject))
        if not topics:
            raise ValueError("No topics found for subject")
        cur_topics = "The topics found in previous exams are: " + topics 
        print(f"Current topics found: {cur_topics}")
    except ValueError:
        cur_topics = "There are no added topics for this subject yet. You must find your own from the text. "
        print("\n\n\nNo topics already in subject.\n\n\n")

    exam.exam_topics = await prompt_to_text.async_prompt_to_text(
        PROMPT_CONFIG + load_prompt("exam_topics") + cur_topics + ocr_text,
        max_tokens=1000,
        is_num=False,
        max_len=2000,
    )
    if exam.exam_topics:
        exam.exam_topics = [t.strip() for t in str(exam.exam_topics).split(',')]
    else:
        exam.exam_topics = []
    log(f"Topics extracted: {len(exam.exam_topics)}")
    object_handling.add_topics(exam.subject, exam.exam_version, exam.exam_topics)

    total_task_count = len(exam.task_numbers)
    log(f"Tasks for processing: {total_task_count}")

    return exam

async def process_task(task_number: str, exam: Exam) -> Exam:
    start_time = perf_counter()
    log(f"Task {task_number}: extracting raw text")
    task_exam = deepcopy(exam)
    task_exam.task_number = task_number
    task_exam.exam_version = exam.exam_version

    task_idx = int(task_number)

    task_output = str(exam.ocr_tasks.get(task_number, ""))

    valid = 0

    task_output = str(
        await prompt_to_text.async_prompt_to_text(
            PROMPT_CONFIG + load_prompt("extract_task_text").format(task_number=task_number) + task_output,
            max_tokens=1000,
            is_num=False,
            max_len=2000,
        )
    )
    task_status[task_idx] = 1
    progress = [task_status[t] for t in range(1, total_task_count + 1)]
    write_progress(progress, LLM_STEPS)

    task_status[task_idx] = 2
    progress = [task_status[t] for t in range(1, total_task_count + 1)]
    write_progress(progress, LLM_STEPS)

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
    task_status[task_idx] = 3
    progress = [task_status[t] for t in range(1, total_task_count + 1)]
    write_progress(progress, LLM_STEPS)
    if task_exam.points is not None:
        log(f"Task {task_number}: points extracted -> {task_exam.points}p")


    if exam.exam_topics:
        cur_topic_enum_str = enum_to_str(Enum('Temaer', exam.exam_topics))

        print(f"\n\n\n cur_topic_enum_str: {cur_topic_enum_str}\n\n\n")

        identify_topic = int(
            await prompt_to_text.async_prompt_to_text(
                PROMPT_CONFIG + load_prompt("identify_topic") + cur_topic_enum_str + task_output,
                max_tokens=1000,
                is_num=False,
                max_len=5,
            )
        )

        if not isinstance(identify_topic, int):
            print(f"\033[91m[ERROR]\033[0m Could not parse topic number for task {task_number}: got '{identify_topic}'", file=sys.stderr)
            identify_topic = 0

        if identify_topic != 0:
            task_exam.topic = get_topic_from_enum(Enum('Temaer', exam.exam_topics), identify_topic)
        else:
            task_exam.topic = str(
                await prompt_to_text.async_prompt_to_text(
                    PROMPT_CONFIG + load_prompt("extract_topic") + task_output,
                    max_tokens=1000,
                    is_num=False,
                    max_len=100,
                )
            )
        if not task_exam.topic or task_exam.topic.lower() in ("unknown topic", "ukjent tema"):
            print(f"\033[91m[ERROR]\033[0m Klarte ikke å identifisere tema for oppgave {task_number}.", file=sys.stderr)
        else:
            print(f"\033[92m[INFO]\033[0m Tema for oppgave {task_number}: {task_exam.topic}")
    
    log(f"Task {task_number}: topic -> {task_exam.topic}")
    task_status[task_idx] = 4
    progress = [task_status[t] for t in range(1, total_task_count + 1)]
    write_progress(progress, LLM_STEPS)

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
        if instruction == "translate_to_bokmaal":
            log(f"Task {task_number}: translated to Bokmål")
        elif instruction == "remove_exam_admin":
            pass
        elif instruction == "format_html_output":
            log(f"Task {task_number}: final HTML formatted")
        task_status[task_idx] = step_idx
        progress = [task_status[t] for t in range(1, total_task_count + 1)]
        write_progress(progress, LLM_STEPS)

    valid = int(
        await prompt_to_text.async_prompt_to_text(
            PROMPT_CONFIG + load_prompt("validate_task") + task_output,
            max_tokens=1000,
            is_num=True,
            max_len=2,
        )
    )
    task_status[task_idx] = 8
    progress = [task_status[t] for t in range(1, total_task_count + 1)]
    write_progress(progress, LLM_STEPS)

    task_exam.task_text = task_output

    if valid == 0:
        log(f"Task {task_number}: not approved")
        result = task_exam
    else:
        log(f"Task {task_number}: approved")
        result = task_exam

    object_handling.add_task(result)
    log(f"Task {task_number} completed in {perf_counter() - start_time:.2f}s")
    return result

async def main_async():
    start_time = perf_counter()
    log("Starting task processing")
    exam_template = await get_exam_info()
    log("Started processing all tasks")

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
            pass

    log(f"Failed tasks: {failed}")
    log(f"Points for tasks: {points}")
    log(f"Final total cost: {prompt_to_text.total_cost:.4f} USD")
    log(f"Total processing time: {perf_counter() - start_time:.2f}s")
    return results


def main():
    return asyncio.run(main_async())

if __name__ == "__main__":
    main()
