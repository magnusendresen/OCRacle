import ocrpdf
import taskseparation
import os
import json
import tkinter as tk
from tkinter import simpledialog

# Cache file to store the last 5 results persistently
CACHE_FILE = 'task_cache.json'

# Load cache from file if it exists
def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# Save cache to file
def save_cache(cache):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def main(rawtext):
    # Initialize cache
    task_cache = load_cache()

    if rawtext and rawtext != []:
        # Add the new result to the cache
        task_cache.append(rawtext)
        if len(task_cache) > 5:
            task_cache.pop(0)
        save_cache(task_cache)
    else:
        root = tk.Tk()
        root.withdraw()  # Hide the main Tkinter window

        if task_cache:
            choice = simpledialog.askinteger(
                "Input",
                "Choose a number between 1 and 5 to select a cached result (1=most recent, 5=oldest):",
                minvalue=1,
                maxvalue=min(5, len(task_cache))
            )

            if choice and 1 <= choice <= len(task_cache):
                # Adjust for most recent to oldest
                rawtext = task_cache[-choice]
            else:
                print("Invalid choice or no cached results available.")
        else:
            print("Cache is empty. No results available to select.")

    return rawtext