import os
import json
from dataclasses import asdict

def main(tasks):
    """
    Tar inn en liste med oppgaveobjekter, og lagrer/oppdaterer disse i tasks.json.
    Dersom en oppgave med samme exam.version, exam.task og exam.subject finnes,
    byttes den ut med den nye prosesseringen av oppgaven.
    """
    file_path = os.path.join(os.path.dirname(__file__), 'tasks.json')

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

    # Lag et oppslagsverk for eksisterende oppgaver basert på (version, task, subject)
    existing_index = {}
    for index, task in enumerate(existing_tasks):
        key = (task.get('version'), task.get('task'), task.get('subject'))
        existing_index[key] = index

    # Gå gjennom de nye oppgavene og oppdater eller legg til
    for task in tasks:
        # Dersom oppgaven ikke allerede er et dictionary, konverter den med asdict
        if not isinstance(task, dict):
            task_dict = asdict(task)
        else:
            task_dict = task

        key = (task_dict.get('version'), task_dict.get('task'), task_dict.get('subject'))
        if key in existing_index:
            existing_tasks[existing_index[key]] = task_dict
            print(f"[INFO] | Oppgave erstattet: Exam: {task_dict.get('version')}, Task: {task_dict.get('task'):02}, Subject: {task_dict.get('subject')}")
        else:
            existing_tasks.append(task_dict)
            print(f"[INFO] | Oppgave lagt til : Exam: {task_dict.get('version')}, Task: {task_dict.get('task'):02}, Subject: {task_dict.get('subject')}")

    # Skriv tilbake alle oppgavene til tasks.json
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(existing_tasks, f, ensure_ascii=False, indent=4)
    
    print("[INFO] | Oppgavene er skrevet til tasks.json.")