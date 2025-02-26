import ocrpdf
import taskseparation
import os
import json
import tkinter as tk
from tkinter import simpledialog

# ✅ Cache-fil for å lagre de siste 5 resultatene
CACHE_FILE = 'task_cache.json'

# ✅ Last inn cache fra fil om den eksisterer
def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache = json.load(f)
            return cache
    return []

# ✅ Lagre cache til fil
def save_cache(cache):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def main(rawtext):
    """Håndterer cache og lar brukeren velge lagrede resultater."""
    print("\n[INFO] Sjekker cache...\n")

    # ✅ Initialiser cache
    task_cache = load_cache()

    if rawtext and rawtext != []:
        # ✅ Legg til nytt resultat i cache
        task_cache.append(rawtext)
        
        # ✅ Begrens cache til 5 elementer
        if len(task_cache) > 5:
            task_cache.pop(0)

        save_cache(task_cache)
        print(f"[INFO] Nytt resultat lagret i cache. Antall elementer: {len(task_cache)}.\n")

    else:
        # ✅ Håndtering av cache hvis ingen nytt input
        if task_cache:
            print(f"[INFO] {len(task_cache)} resultater funnet i cache.")
            root = tk.Tk()
            root.withdraw()  # ✅ Skjul Tkinter-vinduet

            choice = simpledialog.askinteger(
                "Input",
                "Velg et tall mellom 1 og 5 for å hente et tidligere lagret resultat (1 = nyeste, 5 = eldste):",
                minvalue=1,
                maxvalue=min(5, len(task_cache))
            )

            if choice and 1 <= choice <= len(task_cache):
                rawtext = task_cache[-choice]
                print(f"[INFO] Hentet oppgave {choice} fra cache.\n")
            else:
                print("[WARNING] Ugyldig valg. Ingen oppgave valgt fra cache.\n")
        else:
            print("[WARNING] Cache er tom.\n")

    return rawtext
