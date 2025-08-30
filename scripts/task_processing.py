import prompt_to_text
import extract_images
import task_boundaries
import ocr_pdf
from project_config import *
from project_config import load_prompt, emphasize
from utils import log, write_progress, update_progress_fraction, timer

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
import requests
from bs4 import BeautifulSoup
from datetime import date


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
    exam_topics: Enum = field(default_factory=lambda: Enum('Topics', []))
    task_numbers: List[str] = field(default_factory=list)
    ocr_tasks: Dict[str, str] = field(default_factory=dict)
    ignored_topics: List[str] = field(default_factory=list)


def get_topics_from_json(emnekode: str) -> Enum:
    """Return available topics for a subject code."""
    with EXAMS_JSON.open('r', encoding='utf-8') as f:
        data = json.load(f)

    entry = data.get(emnekode.upper().strip(), {})
    topics = [t for t in entry.get("topics", []) if t is not None]
    return Enum('Topics', topics)

def get_ignored_topics_from_json(emnekode: str) -> str:
    """Return ignored topics for a subject code."""
    with EXAMS_JSON.open('r', encoding='utf-8') as f:
        data = json.load(f)

    entry = data.get(emnekode.upper().strip(), {})
    ignored = entry.get("ignored_topics", [])
    return ", ".join(ignored) if ignored else ""


def enum_to_str(enum: Enum) -> str:
    return str([f"{e.value}: {e.name}" for e in enum])

def get_topic_from_enum(topic_enum: Enum, num: int) -> str:
    """Get topic name from enum based on enum and number."""
    for topic in topic_enum:
        if topic.value == num:
            return topic.name
    return "Unknown Topic"

def get_learning_goals(subject_code: str) -> str:
    try:
        subject_code = subject_code.upper()
        if subject_code[-5].upper() == 'X':
            subject_code = subject_code[: -5] + 'T' + subject_code[-4:]
        year = str(date.today().year)
        web_url = f"https://www.ntnu.no/studier/emner/{subject_code}/{year}#tab=omEmnet"

        response = requests.get(web_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        div = soup.find("div", id="learning-goal-toggler")
        if not div:
            return ""

        return div.get_text(separator=" ", strip=True)

    except Exception as e:
        return f"Feil ved henting av {subject_code}: {e}"

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


    containers, task_map, exam.task_numbers, exam.ocr_tasks = await task_boundaries.validate_containers(
        containers, task_map, ocr_text, exam.ocr_tasks, exam.task_numbers
    )
    total_task_count = len(exam.task_numbers)


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
    log(f"Raw exam version response: {exam_raw_version}")    
    
    exam_raw_version = str(exam_raw_version).strip().upper()
    if exam_raw_version[0] in ["V", "H", "K"]:
        version_abbr = exam_raw_version[0].upper() + exam_raw_version[-2:]
        log(f"Detected this pdf to be an exam from {version_abbr}.")
    else:
        version_abbr = exam_raw_version

    exam.exam_version = version_abbr
    object_handling.add_exam(exam.subject, exam.exam_version)
    progress = [task_status[t] for t in range(1, total_task_count + 1)]
    write_progress(progress, LLM_STEPS, {5: exam.exam_version or ""})

    with timer("Extracting figures"):
        await extract_images.extract_figures(
            str(pdf_path), containers, task_map, exam.subject, exam.exam_version
        )

    log("Extracting exam topics")

    input_ign_topics: List[str] = []
    try:
        with IGNORED_FILE.open("r", encoding="utf-8") as f:
            ignored_raw = json.load(f).get("ignored", "")
        input_ign_topics = [t.strip() for t in ignored_raw.split(",") if t.strip()]
    except Exception as e:
        log(f"Could not read ignored topics: {e}")
    
    json_ign_topics = get_ignored_topics_from_json(exam.subject)

    json_enum_topics = enum_to_str(get_topics_from_json(exam.subject))

    prev_topics = ""
    if json_enum_topics is not None and len(json_enum_topics) > 1:
        prev_topics = (
            f"Følgende temaer er funnet i tidligere eksamner, som du dermed ikke trenger å skrive er: {json_enum_topics}, {json_ign_topics}. " +
            "Om det ikke er noen temaer som mangler, svar kun med tallet null '0' (uten anførselstegn). " +
            "Dette betyr ikke nødvendigvis at de dekker hele denne eksamen, så du må da fortsatt finne de temaene som er relevante for denne eksamen. " +
            "Hver eneste oppgave må ha et tema det passer til, ikke nødvendigvis et tema per oppgave, men hver oppgave må ha et tema. " +
            "Hvis det er temaer som mangler, skriv alle temaene som mangler, separert med komma, nøyaktig likt formattert som ovenfor. "
        )
        log(f"Previous topics found: {json_enum_topics}")
    else:
        log("No previous topics found.")

    learning_goals = get_learning_goals(exam.subject)
    log(f"Fetched learning goals from NTNU website for {str(exam.subject)} with {len(learning_goals)} characters.")
    Learning_goals_str = ""
    if learning_goals and len(learning_goals) > 1000:
        Learning_goals_str = (
            "Her er beskrivelsen av emnet fra NTNU sine nettsider: " + learning_goals +
            "Det er derimot viktigst at du baserer deg på teksten knyttet til hver enkelt oppgave fra eksamen, så ikke stol blindt på beskrivelsen av emnet. "
            "Det er trolig et forhold på omtrent 0.7-1.0 temaer per oppgave i denne eksamen. "
        )
        log(f"Learning goals extracted from NTNU website.")
    else:
        log("No learning goals found on NTNU website.")


    # Making a test to see if all contents of the upcoming prompt is has contents
    for content in [PROMPT_CONFIG, load_prompt("exam_topics"), prev_topics, Learning_goals_str, ocr_text]:
        if content is None or len(content) < 5:
            log(f"[WARNING] One of the contents for the exam topics prompt is very short or empty: {content}")

    new_topics = await prompt_to_text.async_prompt_to_text(
        PROMPT_CONFIG + load_prompt("exam_topics") + prev_topics + Learning_goals_str +
        "Her er teksten fra eksamen: " + ocr_text,
        max_tokens=1000,
        is_num=False,
        max_len=4000,
    )

    removed_topics = set()

    if new_topics is not None and len(new_topics) > 1:
        log(f"New topics identified: {new_topics}")

        if (json_ign_topics is not None and len(json_ign_topics) > 1) or (input_ign_topics is not None and len(input_ign_topics) > 0):        
            log(f"Removing ignored topics.")

            new_topics_list_0 = [t.strip() for t in str(new_topics).split(',') if t.strip()]

            new_topics = await prompt_to_text.async_prompt_to_text(
                PROMPT_CONFIG + "Fjern alle temaer direkte knyttet til " + ', '.join(input_ign_topics) + json_ign_topics + " fra listen." + new_topics + 
                ". Skriv kun de temaene som er igjen, separert med komma, nøyaktig likt formattert som ovenfor. ",
                max_tokens=1000,
                is_num=False,
                max_len=4000,
            )

            new_topics_list_1 = [t.strip() for t in str(new_topics).split(',') if t.strip()]

            removed_topics = set(new_topics_list_0) - set(new_topics_list_1)

            emphasize(f"Removed topics: {', '.join(removed_topics)}")

            emphasize(f"New topics after removal: {new_topics}")

        new_topics = [t.strip() for t in str(new_topics).split(',')]

    else:
        print(f"No new topics identified due to response being {new_topics}")
        new_topics = []

    object_handling.add_topics(
        exam.subject, new_topics, removed_topics
    )

    exam.exam_topics = get_topics_from_json(exam.subject)
    log(f"Total topics in subject is now: {len(list(exam.exam_topics))}")

    exam.ignored_topics = get_ignored_topics_from_json(exam.subject)
    log(f"Ignored topics is now: {exam.ignored_topics}")


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


    if task_exam.ignored_topics is not None and len(task_exam.ignored_topics) > 1:
        remove_topic = int(
            await prompt_to_text.async_prompt_to_text(
            (
                PROMPT_CONFIG +
                "Is this task related to any of the following ignored topics?: " + str(task_exam.ignored_topics) + "\n" +
                "If the task is related to any ignored topic, respond with 1. " +
                "If the task is related to any allowed topic from this list: " + str(task_exam.exam_topics) + ", respond with 0. " +
                "ONLY RESPOND WITH A 1 OR 0. NOTHING ELSE!!!! " +
                "Here is the task text: " +
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
