import os
import json

CACHE_FILE = 'task_cache.json'

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_cache(cache):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def main(rawtext):
    """Håndterer cache og lar brukeren velge lagrede resultater fra terminalen.
    Dersom brukeren ikke skriver et tall innenfor det gitte intervallet, stoppes koden.
    """
    print("\n[INFO] Checking cache...")

    task_cache = load_cache()

    if rawtext and rawtext != []:
        # Legg til ny oppgave i cachen
        task_cache.append(rawtext)
        if len(task_cache) > 5:
            task_cache.pop(0)
        save_cache(task_cache)
        print(f"[INFO] New result stored in cache. Total entries: {len(task_cache)}.")
    else:
        if task_cache:
            print(f"[INFO] {len(task_cache)} results found in cache.")
            max_choice = min(5, len(task_cache))
            try:
                choice = int(input(f"[INFO] Select a number between 1 and {max_choice} to retrieve a cached exam: "))
            except ValueError:
                print("[ERROR] Invalid input, must be an integer. Exiting.")
                exit(1)
            if 1 <= choice <= max_choice:
                rawtext = task_cache[-choice]
                print(f"[INFO] Retrieved task {choice} from cache.\n")
            else:
                print("[ERROR] Input out of allowed interval. Exiting.")
                exit(1)
        else:
            print("[WARNING] Cache is empty.\n")

    return rawtext
