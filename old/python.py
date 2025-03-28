from pathlib import Path
import sys

sys.stdout.reconfigure(encoding='utf-8')

dir_txt = Path(__file__).resolve().parent / "dir.txt"
directory = dir_txt.read_text(encoding="utf-8").strip()

# Skriv som repr for å se hva som faktisk er der
print("Raw:", repr(directory))
