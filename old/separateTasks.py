import os
import re

def extract_tasks(text):
    """
    Extracts tasks from the given text based on the keyword 'Oppgave' and its variations.

    Parameters:
        text (str): The entire content of the document as a string.

    Returns:
        list: A list of task sections as strings.
    """
    # Define a regex pattern to match "Oppgave" followed by a space and optional digits
    pattern = re.compile(r"(Oppgave|oppgave|Oppgåve|oppgåve)\s*\d*")

    # Find all matches for the pattern
    matches = [match.start() for match in pattern.finditer(text)]

    # If no tasks are found, return the entire text as a single task
    if not matches:
        return [text]

    # Split the text into tasks using the matched indices
    tasks = []
    for i in range(len(matches)):
        start = matches[i]
        end = matches[i + 1] if i + 1 < len(matches) else len(text)
        tasks.append(text[start:end].strip())

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
tasks = extract_tasks(file_contents)

# Access a specific task by index
print(tasks[9])  # Adjust the index as needed