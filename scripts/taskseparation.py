import os
import regex as re
from textnormalization import normalize_text

def is_valid_task(text_segment, min_length=60):
    result = len(text_segment) > min_length
    if not result:
        print(f"DEBUG: Task removed due to length ({len(text_segment)} characters): {text_segment[:50]}...")
    return result

def is_excluded_task(task, exclusion_keywords, min_match=5):
    match_count = sum(1 for keyword in exclusion_keywords if keyword.lower() in task.lower())
    result = match_count >= min_match
    if result:
        print(f"DEBUG: Task excluded due to keywords (matches: {match_count}): {task[:50]}...")
    return result

def extract_tasks(text):
    task_pattern = re.compile(r"((Oppgave|oppgave|Oppg\u00e5ve|oppg\u00e5ve)\s*\d+|\d+\([a-zA-Z]\))")
    max_points_pattern = re.compile(r"Maks poeng\s*:\s*\d+")

    task_starts = [match.start() for match in task_pattern.finditer(text)]
    max_points_matches = [match.end() for match in max_points_pattern.finditer(text)]

    if not task_starts:
        print("DEBUG: No tasks found in the text.")
        return [text]

    tasks = []

    first_task_start = task_starts[0]
    first_task_end = max_points_matches[0] if max_points_matches else len(text)
    print(f"DEBUG: Starting first task at position {first_task_start}, ending at {first_task_end}.")
    tasks.append(text[first_task_start:first_task_end].strip())

    for i in range(1, len(max_points_matches)):
        start = max_points_matches[i - 1]
        end = max_points_matches[i]
        print(f"DEBUG: Starting new task after 'Maks poeng' at position {start}, ending at {end}.")
        tasks.append(text[start:end].strip())

    if max_points_matches and max_points_matches[-1] < len(text):
        print(f"DEBUG: Adding final task starting at position {max_points_matches[-1]} to the end of the text.")
        tasks.append(text[max_points_matches[-1]:].strip())

    return tasks

def main(input_text):
    exclusion_keywords = [
        "eksamen", "kandidatnummer", "sensur", "hjelpemiddel",
        "informasjon", "vurdering", "beskjeder", "beskjedar",
        "varsling", "sensurfrist", "oppgavesettet", "levering",
        "poeng", "vektig", "sensurtidspunkt", "kalkulator",
        "tillatne", "h\u00e5ndteikningar", "h\u00e5ndtegninger",
        "kontaktperson", "kontaktinformasjon", "oppgavefrister",
        "tillatelse", "gir maksimalt", "maksimalt",
        "formelark", "inspera", "eksamensoppgave", "svar",
        "utfylte", "kommentarer", "eksempel", "notater"
    ]

    text = normalize_text(input_text)
    tasks = extract_tasks(text)

    valid_tasks = []
    for task in tasks:
        if is_valid_task(task) and not is_excluded_task(task, exclusion_keywords):
            valid_tasks.append(task)

    return valid_tasks
