import json
import re
from dataclasses import asdict
from typing import Any, Dict, Iterable, List, Optional
from enum import Enum
from project_config import EXAMS_JSON
from utils import *


def normalize_subject_code(code: str) -> str:
    """Normalize a subject code string for consistent comparisons."""
    return str(code or "").strip().upper()


def _ensure_subject_entry(data: Dict[str, Any], subject: str) -> Dict[str, Any]:
    """Guarantee that a subject entry exists with the expected structure."""
    entry = data.get(subject) or {}
    alt_codes = list(entry.get("alternate_codes", []))
    topics = list(entry.get("topics", []))
    ignored = list(entry.get("ignored_topics", []))
    exams = entry.get("exams", {})
    normalized_entry = {
        "alternate_codes": alt_codes,
        "topics": topics,
        "ignored_topics": ignored,
        "exams": exams,
    }
    data[subject] = normalized_entry
    return normalized_entry


def load_subject_alias_map() -> Dict[str, str]:
    """
    Build a mapping from any known subject or alternate code to its canonical subject key.
    """
    alias_map: Dict[str, str] = {}
    data = _load_json()
    for canonical, entry in data.items():
        canonical_norm = normalize_subject_code(canonical)
        alias_map[canonical_norm] = canonical
        for alt in entry.get("alternate_codes", []):
            alias_map[normalize_subject_code(alt)] = canonical
    return alias_map


def resolve_subject_code(code: str) -> Optional[str]:
    """Resolve a code (canonical or alternate) to the stored canonical subject key."""
    normalized = normalize_subject_code(code)
    if not normalized:
        return None
    return load_subject_alias_map().get(normalized)


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
    subject = normalize_subject_code(subject)
    _ensure_subject_entry(data, subject)
    _save_json(data)


def update_alternate_codes(subject: str, codes: Iterable[str]) -> None:
    """Merge alternate subject codes into the canonical subject entry."""
    codes = list(codes or [])
    if not codes:
        return
    data = _load_json()
    canonical_key = resolve_subject_code(subject) or normalize_subject_code(subject)
    entry = _ensure_subject_entry(data, canonical_key)

    existing: Dict[str, str] = {
        normalize_subject_code(code): normalize_subject_code(code)
        for code in entry.get("alternate_codes", [])
        if normalize_subject_code(code)
    }
    canonical_norm = normalize_subject_code(canonical_key)

    for code in codes:
        normalized = normalize_subject_code(code)
        if not normalized or normalized == canonical_norm:
            continue
        existing.setdefault(normalized, normalized)

    entry["alternate_codes"] = sorted(existing.values())
    data[canonical_key] = entry
    _save_json(data)


def add_exam(subject: str, exam_version: str, *, source_subject_code: Optional[str] = None) -> None:
    """Ensure that an exam exists under a subject."""
    data = _load_json()
    subject = normalize_subject_code(subject)
    exam_version = exam_version.strip()
    subj = _ensure_subject_entry(data, subject)
    exams = subj.setdefault("exams", {})
    exam_entry = exams.setdefault(exam_version, {})
    exam_entry.setdefault("tasks", [])
    if source_subject_code:
        exam_entry["source_subject_code"] = normalize_subject_code(source_subject_code)
    else:
        exam_entry.setdefault("source_subject_code", subject)
    exams[exam_version] = {
        "source_subject_code": exam_entry.get("source_subject_code", subject),
        "tasks": exam_entry.get("tasks", []),
    }
    subj["exams"] = exams
    data[subject] = subj
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
    subject = normalize_subject_code(subject)
    subj = _ensure_subject_entry(data, subject)
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
        "alternate_codes": subj.get("alternate_codes", []),
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
    subject = normalize_subject_code(subject)
    subj = _ensure_subject_entry(data, subject)

    alt_codes = [
        normalize_subject_code(code)
        for code in task_dict.get("alternate_subject_codes", [])
        if normalize_subject_code(code)
    ]
    if alt_codes:
        canonical_norm = subject
        existing_alts = {
            normalize_subject_code(code): normalize_subject_code(code)
            for code in subj.get("alternate_codes", [])
            if normalize_subject_code(code)
        }
        for code in alt_codes:
            if code != canonical_norm:
                existing_alts.setdefault(code, code)
        subj["alternate_codes"] = sorted(existing_alts.values())

    exam_data = subj["exams"].setdefault(exam, {"tasks": []})
    if task_dict.get("source_subject_code"):
        exam_data["source_subject_code"] = normalize_subject_code(task_dict["source_subject_code"])
    else:
        exam_data.setdefault("source_subject_code", subject)

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
            "source_subject_code",
            "alternate_subject_codes",
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



