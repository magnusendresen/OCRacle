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
    exam_topics: Enum = field(default_factory=lambda: Enum('Temaer', []))
    task_numbers: List[str] = field(default_factory=list)
    ocr_tasks: Dict[str, str] = field(default_factory=dict)
    ignored_topics: List[str] = field(default_factory=list)


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
        data = json.load(f)
        exam.subject = data.get("subject", "").strip().upper()
    if exam.subject:
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

    try:
        with IGNORED_FILE.open("r", encoding="utf-8") as f:
            ignored_raw = json.load(f).get("ignored", "")
        exam.ignored_topics = [t.strip() for t in ignored_raw.split(",") if t.strip()]
    except Exception as e:
        log(f"Could not read ignored topics: {e}")
    log(f"Subject code: {exam.subject}")
    object_handling.add_subject(exam.subject)
    progress = [task_status[t] for t in range(1, total_task_count + 1)]
    write_progress(progress, LLM_STEPS, {4: exam.subject or ""})

    log("Prompting exam version")
    exam_raw_version = await prompt_to_text.async_prompt_to_text(
        PROMPT_CONFIG + load_prompt("get_exam_version") + ocr_text,
        max_tokens=1000,
        is_num=False,
        max_len=20,
    )
    exam_raw_version = str(exam_raw_version).strip().upper()
    if exam_raw_version[0] in ["V", "H", "K"]:
        version_abbr = exam_raw_version[0].upper() + exam_raw_version[-2:]
    else:
        version_abbr = exam_raw_version[8:]
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
        cur_topics = "Temaene funnet i tidligere eksamner for dette emnet er: " + topics 
    except ValueError:
        cur_topics = "Det er ingen temaer registrert enda i dette emnet. "

    log(cur_topics)
    
    new_topics = await prompt_to_text.async_prompt_to_text(
        PROMPT_CONFIG + load_prompt("exam_topics") + cur_topics + ocr_text,
        max_tokens=1000,
        is_num=False,
        max_len=4000,
    )
    if new_topics not in [None, "", "0", 0]:
        print(f"New topics identified: {new_topics}")
        new_topics = [t.strip() for t in str(new_topics).split(',')]
        object_handling.add_topics(exam.subject, exam.exam_version, new_topics)
    else:
        print("No new topics identified.")

    exam.exam_topics = get_topics_from_json(exam.subject)
    log(f"Total in subject is now: {len(list(exam.exam_topics))}")

    
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

    task_number_str = task_number.zfill(2)

    task_output = str(exam.ocr_tasks.get(task_number, ""))

    valid = 0

    task_status[task_idx] = 1
    progress = [task_status[t] for t in range(1, total_task_count + 1)]
    write_progress(progress, LLM_STEPS)

    task_output = str(
        await prompt_to_text.async_prompt_to_text(
            PROMPT_CONFIG + load_prompt("extract_task_text").format(task_number=task_number) + task_output,
            max_tokens=1000,
            is_num=False,
            max_len=5000,
        )
    )

    task_status[task_idx] = 2
    progress = [task_status[t] for t in range(1, total_task_count + 1)]
    write_progress(progress, LLM_STEPS)



    remove_topic = int(
        await prompt_to_text.async_prompt_to_text(
            (
                PROMPT_CONFIG +
                "Is this task about any of the following topics?: " + ", ".join([ignored for ignored in task_exam.ignored_topics]) + "\n" +
                "ONLY RESPOND WITH A 1 OR 0. NOTHING ELSE!!!! " +
                "If it is, answer with a 1, otherwise answer with a 0. Here is the task text: " +
                task_output
            ),
            max_tokens=1000,
            is_num=True,
            max_len=2,
        )
    )

    if remove_topic:
        log(f"Task {task_number_str}: ignored due to topic")
        task_status[task_idx] = 8
        progress = [task_status[t] for t in range(1, total_task_count + 1)]
        write_progress(progress, LLM_STEPS)
        return

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
        log(f"Task {task_number_str}: points extracted -> {task_exam.points}p")


    if exam.exam_topics:
        cur_topic_enum_str = enum_to_str(exam.exam_topics)

        identify_topic = int(
            await prompt_to_text.async_prompt_to_text(
                PROMPT_CONFIG + load_prompt("identify_topic") + cur_topic_enum_str + task_output,
                max_tokens=1000,
                is_num=False,
                max_len=5,
            )
        )

        if not isinstance(identify_topic, int):
            identify_topic = 0

        if identify_topic != 0:
            task_exam.topic = get_topic_from_enum(exam.exam_topics, identify_topic)
        else:
            task_exam.topic = "Unknown Topic"
    
    log(f"Task {task_number_str}: topic identified -> {task_exam.topic}")
    task_status[task_idx] = 4
    progress = [task_status[t] for t in range(1, total_task_count + 1)]
    write_progress(progress, LLM_STEPS)

    for step_idx, instruction in enumerate([
        "remove_exam_admin",
        "format_html_output",
        "translate_to_bokmaal"
    ], start=5):
        task_output = str(
            await prompt_to_text.async_prompt_to_text(
                PROMPT_CONFIG + load_prompt(instruction) + task_output,
                max_tokens=1000,
                is_num=False,
                max_len=5000,
            )
        )
        if instruction == "translate_to_bokmaal":
            log(f"Task {task_number_str}: translated to Bokmål")
        elif instruction == "remove_exam_admin":
            pass
        elif instruction == "format_html_output":
            log(f"Task {task_number_str}: HTML formatted")
        task_status[task_idx] = step_idx
        progress = [task_status[t] for t in range(1, total_task_count + 1)]
        write_progress(progress, LLM_STEPS)

    valid = int(
        (
            await prompt_to_text.async_prompt_to_text(
                PROMPT_CONFIG + load_prompt("validate_task") + task_output,
                max_tokens=1000,
                is_num=False,
                max_len=4,
            )
        ).strip()[0]
    )
    task_status[task_idx] = 8
    progress = [task_status[t] for t in range(1, total_task_count + 1)]
    write_progress(progress, LLM_STEPS)

    task_exam.task_text = task_output

    if valid == 0:
        log(f"Task {task_number_str}: not approved")
        return
    else:
        log(f"Task {task_number_str}: approved")
        result = task_exam

    object_handling.add_task(result)
    log(f"Task {task_number_str}: completed in {perf_counter() - start_time:.2f}s")
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

    valid_results = [res for res in results if res is not None]
    failed = [res.task_number for res in valid_results if res.task_text is None]
    points = [res.points for res in valid_results if res.task_text is not None]

    log(f"Failed tasks: {failed}")
    log(f"Points for tasks: {points}")
    log(f"Final total cost: {prompt_to_text.total_cost:.4f} USD")
    log(f"Total processing time: {perf_counter() - start_time:.2f}s")
    return results


def main():
    return asyncio.run(main_async())

if __name__ == "__main__":
    main()
