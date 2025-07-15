import json
JSON_PATH = "objects.json"


def write_task_to_json(task, subject_code, exam_version, file):
    # Check if the file exists
    try:
        data = json.load(file)
    except FileNotFoundError:
        data = {"exams": []}

    # Check if the subject code already exists, if not, add it
    code_exists = False
    for code in list(data.keys()):
        if code == subject_code:
            print("Subject code already exists in JSON file.")
            code_exists = True
            break
    if not code_exists:
        data[subject_code] = {
            exam_version: {
                "tasks": task
            }
        }
        file.seek(0)
        json.dump(data, file, indent=4)
        file.truncate()

    # Check if the exam version already exists, if not, add it
    if subject_code in data and exam_version not in data[subject_code]:
        data[subject_code][exam_version] = {
            "tasks": task
        }
        file.seek(0)
        json.dump(data, file, indent=4)
        file.truncate()
    else:
        print("Exam version already exists for this subject code.")

    # Check if the task number already exists, if not, add the task
    if subject_code in data and exam_version in data[subject_code]:
        existing_tasks = data[subject_code][exam_version].get("tasks", [])
        task_numbers = [t['task_number'] for t in existing_tasks]
        
        if task['task_number'] not in task_numbers:
            existing_tasks.append(task)
            data[subject_code][exam_version]['tasks'] = existing_tasks
            file.seek(0)
            json.dump(data, file, indent=4)
            file.truncate()
        else:
            print(f"Task number {task['task_number']} already exists for this subject code and exam version.")



# Example object to write
exam = {
    "exam": "INGX1002",
}

tasks = [
    {
        "topic": "Math",
        "task_number": 1,
        "task_text": "What is 2 + 2?",
    },
    {
        "topic": "Science",
        "task_number": 2,
        "task_text": "What is the chemical symbol for water?",
    },
    {
        "topic": "History",
        "task_number": 3,
        "task_text": "Who was the first president of the United States?",
    }
]

version = "H24"

# Path to objects.json

    

# Open the JSON file in read mode
with open(JSON_PATH, 'r+') as file:
    write_task_to_json(tasks, exam['exam'], version, file)