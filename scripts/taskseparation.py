import re
import json

def extract_coordinates(text):
    max_points_pattern = re.compile(r"Maks poeng\s*:\s*\d+")
    points_key = [match.end() for match in max_points_pattern.finditer(text)]
    print(f"Extracted {len(points_key)} coordinate points from text.")
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
        print(f"First task marker detected at position {match.end()}.")
        return match.end()
    print("No task marker detected; defaulting to position 0.")
    return 0

def taskvalidation(tasks):
    invalidtasks = []
    task_matches = [0] * len(tasks)
    total_invalid_tasks = 0
    merged_tasks = 0

    for i in range(len(tasks)):
        task = tasks[i]
        if len(task) < 100:
            invalidtasks.append(1)
            total_invalid_tasks += 1
        else:
            invalidtasks.append(0)

        task_patterns = [
            re.compile(r"oppgave\s*\d+", re.IGNORECASE),
            re.compile(r"oppgåve\s*\d+", re.IGNORECASE),
            re.compile(r"\d+\s*\(\s*[A-Z]\s*\)", re.IGNORECASE)
        ]
        for pattern in task_patterns:
            match = pattern.search(task[25:])  # Start reading after 25 characters
            if match:
                task_matches[i] = match.start() + 25  # Store the position of the match
                break

    for j in range(1, len(tasks)):
        if invalidtasks[j] != 0 and task_matches[j-1] != 0:

            # Find the parts to be swapped
            split_point_j_1 = task_matches[j-1]
            part_to_move_to_j = tasks[j-1][split_point_j_1:]
            remaining_j_1 = tasks[j-1][:split_point_j_1]

            # Update task j-1 and task j
            tasks[j-1] = remaining_j_1 + tasks[j]
            tasks[j] = part_to_move_to_j

            merged_tasks += 1

    print(f"Validation completed. Total tasks: {len(tasks)}, Invalid tasks: {total_invalid_tasks}, Merged tasks: {merged_tasks}.")
    return tasks

def main(text):
    # Detect where the first task begins
    first_task_start = detect_first_task_start(text)

    # Extract coordinates starting from the detected first task
    trimmed_text = text[first_task_start:]
    points_key = extract_coordinates(trimmed_text)

    # Ensure filtered_task_key starts with the detected first task start
    filtered_task_key = [first_task_start] + [first_task_start + point for point in points_key]
    print(f"Processing text: Detected first task at {first_task_start}, Extracted {len(filtered_task_key) - 1} tasks.")

    tasks = []
    for i in range(len(filtered_task_key) - 1):
        tasks.append(text[filtered_task_key[i]:filtered_task_key[i+1]])

    tasks = taskvalidation(tasks)

    return tasks
