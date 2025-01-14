import re
import json

def extract_coordinates(text):
    max_points_pattern = re.compile(r"Maks poeng\s*:\s*\d+")
    points_key = [match.end() for match in max_points_pattern.finditer(text)]
    return points_key

def detect_first_task_start(text):
    # Define possible markers that precede the first task
    markers = [
        "prøvar».",
        "prøver».",
        "tilgjengelige i arkivet",
        "tekstverktøyet i Inspera",
        "slike spørsmål",
        "eksamen er passert",
        "med InsperaScan"
    ]
    marker_pattern = re.compile(r"(" + "|".join(re.escape(marker) for marker in markers) + r")", re.IGNORECASE)

    match = marker_pattern.search(text)
    if match:
        return match.end()
    return 0

def main(text):
    # Detect where the first task begins
    first_task_start = detect_first_task_start(text)

    # Extract coordinates starting from the detected first task
    trimmed_text = text[first_task_start:]
    points_key = extract_coordinates(trimmed_text)

    # Ensure filtered_task_key starts with the detected first task start
    filtered_task_key = [first_task_start] + [first_task_start + point for point in points_key]

    tasks = []
    for i in range(len(filtered_task_key) - 1):
        tasks.append(text[filtered_task_key[i]:filtered_task_key[i+1]])

    print("Filtered Task Starts:", filtered_task_key)

    return tasks
