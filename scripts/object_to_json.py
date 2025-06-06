import os
import json
from dataclasses import asdict
from project_config import *


def main(tasks):
    """Lag eller oppdater tasks.json i struktur emne -> eksamensutgivelse -> oppgave."""
    file_path = TASKS_JSON

    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except json.JSONDecodeError:
            print("[INFO] | JSON-dekoderingsfeil i tasks.json. Starter med et tomt oppsett.")
            existing = {}
    else:
        existing = {}

    for task in tasks:
        task_dict = asdict(task) if not isinstance(task, dict) else task
        subject = task_dict.get("subject")
        exam = task_dict.get("exam_version")
        if not subject or not exam:
            continue

        subject_data = existing.setdefault(subject, {})
        exam_data = subject_data.setdefault(exam, {
            "total_tasks": task_dict.get("total_tasks", []),
            "matching_codes": task_dict.get("matching_codes", []),
            "tasks": []
        })

        if task_dict.get("total_tasks"):
            exam_data["total_tasks"] = task_dict["total_tasks"]
        if task_dict.get("matching_codes"):
            exam_data["matching_codes"] = task_dict["matching_codes"]

        task_copy = {k: v for k, v in task_dict.items() if k not in {"subject", "exam_version", "total_tasks", "matching_codes"}}
        task_num = task_copy.get("task_number") or 0

        tasks_list = exam_data["tasks"]
        idx = next((i for i, t in enumerate(tasks_list) if t.get("task_number") == task_copy.get("task_number")), None)
        if idx is not None:
            tasks_list[idx] = task_copy
            action = "erstattet"
        else:
            tasks_list.append(task_copy)
            action = "lagt til"

        print(
            f"[INFO] | Oppgave {action}: "
            f"Exam: {exam}, "
            f"Task: {task_num:02}, "
            f"Subject: {subject} "
            f"({len(task_copy.get('images', []))} bilder)"
        )

    for subject_data in existing.values():
        for exam_data in subject_data.values():
            exam_data["tasks"].sort(key=lambda x: x.get("task_number"))

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=4)

    print("[INFO] | Oppgavene er skrevet til tasks.json.")
