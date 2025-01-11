import os

def does_it_include(text):
    keywords = {
        "oppgave", "Oppgave", "oppgåve", "Oppgåve", 
        "o ppgave", "O ppgave", "o ppgåve", "O ppgåve", 
        "oppg ave", "Oppg ave", "oppg åve", "Oppg åve",
        "OppgÃ¥ve", "Oppg Ã¥ve", "OppgÃ ¥ve", "Op pgÃ¥ve",
        "Oppg", "oppg", "OppgÃ¥ve", "Oppg Ã¥ve", "OppgÃ ¥ve", "Op pgÃ¥ve"
    }
    return any(keyword in text for keyword in keywords)

def binary_search(text, start, end):
    precision = 1
    while end - start > precision:
        mid = (start + end) // 2
        if does_it_include(text[start:mid]):
            end = mid
        else:
            start = mid
    return start

def find_task_starts(text):
    task_starts = [0]
    end = 0
    length = len(text)

    while True:
        start = binary_search(text, end, length)
        if does_it_include(text[start:length]):
            task_starts.append(start)
            end = start + 1
        else:
            break

    return task_starts

def extract_tasks(text):
    offset = 22
    task_starts = find_task_starts(text)
    tasks = []
    for i in range(len(task_starts) - 1):
        start = max(0, task_starts[i] - offset if i > 0 else task_starts[i])
        end = task_starts[i + 1]
        tasks.append(text[start:end])

    # Adjust the first task's range by trimming from the end
    if tasks:
        tasks[0] = tasks[0][:-offset]

    # Add the final portion from the last task start to the end of the text
    if task_starts:
        tasks.append(text[task_starts[-1]:])

    return tasks


# Get the directory of the Python file
current_directory = os.path.dirname(__file__)

# File name
file_name = "output.txt"

# Full path to the file
file_path = os.path.join(current_directory, file_name)

# Read the contents of the file
with open(file_path, 'r') as file:
    file_contents = file.read()


# Example usage
print(extract_tasks(file_contents)[18])