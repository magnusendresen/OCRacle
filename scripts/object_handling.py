import json
import re
from dataclasses import asdict
from typing import Any, Dict, List, Optional
from enum import Enum
from project_config import EXAMS_JSON
from utils import *


def _load_json() -> Dict[str, Any]:
    """Load the exams.json file and return its content as a dict."""
    if EXAMS_JSON.exists():
        try:
            with EXAMS_JSON.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            log("JSON-dekoderingsfeil i exams.json. Starter med et tomt oppsett.")
    return {}


def _save_json(data: Dict[str, Any]) -> None:
    """Write the given data back to exams.json."""
    with EXAMS_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def add_subject(subject: str) -> None:
    """Ensure that a subject exists in exams.json."""
    data = _load_json()
    subject = subject.strip().upper()
    data.setdefault(subject, {"topics": [], "ignored_topics": [], "exams": {}})
    _save_json(data)


def add_exam(subject: str, exam_version: str) -> None:
    """Ensure that an exam exists under a subject."""
    data = _load_json()
    subject = subject.strip().upper()
    exam_version = exam_version.strip()
    subj = data.setdefault(subject, {"topics": [], "ignored_topics": [], "exams": {}})
    subj["exams"].setdefault(exam_version, {"tasks": []})
    _save_json(data)


def add_topics(
    subject: str,
    topics: List[Any],
    ignored_topics: Optional[List[str]] = None,
) -> None:
    """Add topics to a subject and optionally store ignored topics."""
    if not topics and not ignored_topics:
        return
    data = _load_json()
    subject = subject.strip().upper()
    subj = data.setdefault(subject, {"topics": [], "ignored_topics": [], "exams": {}})
    existing = [t.name if isinstance(t, Enum) else t for t in subj.get("topics", [])]
    for topic in topics:
        topic_name = topic.name if isinstance(topic, Enum) else topic
        if topic_name not in existing:
            existing.append(topic_name)
    subj["topics"] = existing
    if ignored_topics:
        existing_ignored = subj.get("ignored_topics", [])
        for topic in ignored_topics:
            if topic not in existing_ignored:
                existing_ignored.append(topic)
        subj["ignored_topics"] = existing_ignored
    subj = {
        "topics": subj.get("topics", []),
        "ignored_topics": subj.get("ignored_topics", []),
        "exams": subj.get("exams", {}),
    }
    data[subject] = subj
    _save_json(data)


def add_task(task: Any) -> None:
    """Add a single task object to exams.json with deduplication logic."""
    task_dict = asdict(task) if not isinstance(task, dict) else task
    subject = task_dict.get("subject")
    exam = task_dict.get("exam_version")
    if not subject or not exam:
        return

    data = _load_json()
    subj = data.setdefault(subject, {"topics": [], "ignored_topics": [], "exams": {}})
    exam_data = subj["exams"].setdefault(exam, {"tasks": []})

    if task_dict.get("exam_topics"):
        existing_topics = [t.name if isinstance(t, Enum) else t for t in subj.get("topics", [])]
        for t in task_dict["exam_topics"]:
            topic_name = t.name if isinstance(t, Enum) else t
            if topic_name not in existing_topics:
                existing_topics.append(topic_name)
        subj["topics"] = existing_topics

    task_copy = {
        k: v
        for k, v in task_dict.items()
        if k
        not in {
            "subject",
            "exam_version",
            "exam_topics",
            "task_numbers",
            "ocr_tasks",
            "total_tasks",
            "ignored_topics",
        }
    }

    tasks_list = exam_data["tasks"]
    idx = next((i for i, t in enumerate(tasks_list) if t.get("task_number") == task_copy.get("task_number")), None)
    if idx is not None:
        tasks_list[idx] = task_copy
        action = "replaced"
    else:
        tasks_list.append(task_copy)
        action = "added"

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
    log(
        f"Task {num_str}: "
        f"Task {action}, "
        f"Exam: {exam}, "
        f"Subject: {subject} "
    )



