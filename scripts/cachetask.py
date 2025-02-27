import ocrpdf
import os
import json
import tkinter as tk
from tkinter import simpledialog

# Cache file to store the last 5 results
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
    """Handles cache and allows the user to select stored results."""
    print("\n[INFO] Checking cache...\n")

    # Initialize cache
    task_cache = load_cache()

    if rawtext and rawtext != []:
        # Add new result to cache
        task_cache.append(rawtext)
        
        # Limit cache to 5 entries
        if len(task_cache) > 5:
            task_cache.pop(0)

        save_cache(task_cache)
        print(f"[INFO] New result stored in cache. Total entries: {len(task_cache)}.\n")
    else:
        # Handle cache if no new input is provided
        if task_cache:
            print(f"[INFO] {len(task_cache)} results found in cache.")
            root = tk.Tk()
            root.withdraw()  # Hide Tkinter window

            choice = simpledialog.askinteger(
                "Input",
                "Select a number between 1 and 5 to retrieve a previously stored result (1 = newest, 5 = oldest):",
                minvalue=1,
                maxvalue=min(5, len(task_cache))
            )

            if choice and 1 <= choice <= len(task_cache):
                rawtext = task_cache[-choice]
                print(f"[INFO] Retrieved task {choice} from cache.\n")
            else:
                print("[WARNING] Invalid choice. No task selected from cache.\n")
        else:
            print("[WARNING] Cache is empty.\n")

    return rawtext
