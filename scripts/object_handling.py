import json
import re
from dataclasses import asdict
from typing import Any, Dict, List
from project_config import EXAMS_JSON


def _load_json() -> Dict[str, Any]:
    """Load the exams.json file and return its content as a dict."""
    if EXAMS_JSON.exists():
        try:
            with EXAMS_JSON.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("[INFO] | JSON-dekoderingsfeil i exams.json. Starter med et tomt oppsett.")
    return {}


def _save_json(data: Dict[str, Any]) -> None:
    """Write the given data back to exams.json."""
    with EXAMS_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def add_subject(subject: str) -> None:
    """Ensure that a subject exists in exams.json."""
    data = _load_json()
    subject = subject.strip().upper()
    data.setdefault(subject, {"topics": [], "exams": {}})
    _save_json(data)


def add_exam(subject: str, exam_version: str) -> None:
    """Ensure that an exam exists under a subject."""
    data = _load_json()
    subject = subject.strip().upper()
    exam_version = exam_version.strip()
    subj = data.setdefault(subject, {"topics": [], "exams": {}})
    subj["exams"].setdefault(exam_version, {"tasks": []})
    _save_json(data)


def add_topics(subject: str, exam_version: str, topics: List[str]) -> None:
    """Add topics to a subject if they are not already present."""
    if not topics:
        return
    data = _load_json()
    subject = subject.strip().upper()
    exam_version = exam_version.strip()
    subj = data.setdefault(subject, {"topics": [], "exams": {}})
    subj["exams"].setdefault(exam_version, {"tasks": []})
    existing = subj.get("topics", [])
    for topic in topics:
        if topic not in existing:
            existing.append(topic)
    subj["topics"] = existing
    _save_json(data)


def add_task(task: Any) -> None:
    """Add a single task object to exams.json with deduplication logic."""
    task_dict = asdict(task) if not isinstance(task, dict) else task
    subject = task_dict.get("subject")
    exam = task_dict.get("exam_version")
    if not subject or not exam:
        return

    data = _load_json()
    subj = data.setdefault(subject, {"topics": [], "exams": {}})
    exam_data = subj["exams"].setdefault(exam, {"tasks": []})

    if task_dict.get("exam_topics"):
        existing_topics = subj.get("topics", [])
        for t in task_dict["exam_topics"]:
            if t not in existing_topics:
                existing_topics.append(t)
        subj["topics"] = existing_topics

    image_count = len(task_dict.get("images", []))
    task_copy = {
        k: v
        for k, v in task_dict.items()
        if k
        not in {
            "subject",
            "exam_version",
            "total_tasks",
            "exam_topics",
            "task_numbers",
            "ocr_tasks",
            "images",
            "code",
        }
    }

    tasks_list = exam_data["tasks"]
    idx = next((i for i, t in enumerate(tasks_list) if t.get("task_number") == task_copy.get("task_number")), None)
    if idx is not None:
        tasks_list[idx] = task_copy
        action = "erstattet"
    else:
        tasks_list.append(task_copy)
        action = "lagt til"

    # Remove duplicates while keeping the latest entry
    seen = set()
    deduped = []
    for t in reversed(tasks_list):
        num = t.get("task_number")
        if num in seen:
            continue
        seen.add(num)
        deduped.append(t)
    tasks_list[:] = list(reversed(deduped))

    def _sort_key(t: Dict[str, Any]) -> tuple:
        num = t.get("task_number", "")
        m = re.search(r"\d+", str(num))
        return (int(m.group()) if m else float("inf"), str(num))

    tasks_list.sort(key=_sort_key)
    _save_json(data)

    num_str = str(task_copy.get("task_number") or 0)
    if num_str.isdigit():
        num_str = num_str.zfill(2)
    print(
        f"[INFO] | Oppgave {action}: "
        f"Exam: {exam}, "
        f"Task: {num_str}, "
        f"Subject: {subject} "
        f"({image_count} bilder)"
    )

