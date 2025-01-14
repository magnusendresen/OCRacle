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

if __name__ == "__main__":
    json_data = filejson("task_cache.json")

    # Ensure the input to extract_coordinates is a string
    if isinstance(json_data, list):
        text_data = " ".join(json_data)
    elif isinstance(json_data, dict):
        text_data = json.dumps(json_data)
    else:
        text_data = str(json_data)

    task_key, points_key = extract_coordinates(text_data)

    print("Task Starts (Oppgave):")
    print(task_key)

    print("Task Ends (Maks poeng):")
    print(points_key)

    # Filter task_key to ensure only closest starts remain
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

    print("Filtered Task Starts (Closest to Task Ends):")
    print(filtered_task_key)