import os
import json
from dataclasses import asdict
import main

def main(tasks):
    """
    Tar inn en liste med oppgaveobjekter, og lagrer/oppdaterer disse i tasks.json.
    Dersom en oppgave med samme exam_version, task_number og subject finnes,
    byttes den ut med den nye prosesseringen av oppgaven.
    """
    file_path = main.PROJECT_ROOT / 'tasks.json'

    # Last inn eksisterende oppgaver dersom fila finnes
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                existing_tasks = json.load(f)
            except json.JSONDecodeError:
                print("[INFO] | JSON-dekoderingsfeil i tasks.json. Starter med en tom liste.")
                existing_tasks = []
    else:
        existing_tasks = []

    # Lag et oppslagsverk for eksisterende oppgaver basert på (exam_version, task_number, subject)
    existing_index = {}
    for index, task in enumerate(existing_tasks):
        key = (task.get('exam_version'), task.get('task_number'), task.get('subject'))
        existing_index[key] = index

    # Gå gjennom de nye oppgavene og oppdater eller legg til
    for task in tasks:
        if not isinstance(task, dict):
            task_dict = asdict(task)
        else:
            task_dict = task

        key = (task_dict.get('exam_version'), task_dict.get('task_number'), task_dict.get('subject'))
        task_num = task_dict.get('task_number') or 0

        if key in existing_index:
            existing_tasks[existing_index[key]] = task_dict
            print(
                f"[INFO] | Oppgave erstattet: "
                f"Exam: {task_dict.get('exam_version')}, "
                f"Task: {task_num:02}, "
                f"Subject: {task_dict.get('subject')} "
                f"({len(task_dict.get('images', []))} bilder)"
            )
        else:
            existing_tasks.append(task_dict)
            print(
                f"[INFO] | Oppgave lagt til : "
                f"Exam: {task_dict.get('exam_version')}, "
                f"Task: {task_num:02}, "
                f"Subject: {task_dict.get('subject')} "
                f"({len(task_dict.get('images', []))} bilder)"
            )

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(existing_tasks, f, ensure_ascii=False, indent=4)

    print("[INFO] | Oppgavene er skrevet til tasks.json.")
