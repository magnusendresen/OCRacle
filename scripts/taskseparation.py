import re
import json

def extract_coordinates(text):
    task_pattern = re.compile(r"((Oppgave|oppgave|Oppg\u00e5ve|oppg\u00e5ve)\s*\d+|\d+\([a-zA-Z]\))")
    max_points_pattern = re.compile(r"Maks poeng\s*:\s*\d+")

    task_key = [match.start() for match in task_pattern.finditer(text)]
    points_key = [match.end() for match in max_points_pattern.finditer(text)]

    return task_key, points_key

def filejson(file):
    with open(file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data

def main(text):
    task_key, points_key = extract_coordinates(text)

    filtered_task_key = []
    previous_end = None

    for end in points_key:
        closest_start = None
        if previous_end is None:
            closest_start = min([start for start in task_key if start < end], default=None)
        else:
            valid_starts = [start for start in task_key if previous_end <= start < end]
            if valid_starts:
                closest_start = min(valid_starts, key=lambda x: end - x)

        if closest_start is not None:
            filtered_task_key.append(closest_start)
        previous_end = end

    tasks = []
    for i in range(len(filtered_task_key)-1):
        tasks.append(text[filtered_task_key[i]:filtered_task_key[i+1]])
        

    # for task in tasks:
    #     print(task)
    #     print("\n\n")
    # print("Filtered Task Starts:", filtered_task_key)

    return tasks
