import time
from pathlib import Path

# Filsti til progress.txt i samme mappe
progress_file = Path("progress.txt")

# Sørg for at vi starter med 7 linjer
with open(progress_file, "w", encoding="utf-8") as f:
    f.writelines(["\n"] * 7)

def write_line(index: int, content: str):
    with open(progress_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    while len(lines) < 7:
        lines.append("\n")
    lines[index - 1] = content + "\n"
    with open(progress_file, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"[WRITE] Linje {index}: {content}")
    time.sleep(1)

def simulate_progress():
    # Linje 1: Google Vision status
    write_line(1, "1")

    # Linje 3: DeepSeek status
    write_line(3, "1")

    # Linje 2: OCR fremdrift (gradvis fylt med 1)
    ocr_line = list("0" * 10)
    for i in range(10):
        ocr_line[i] = "1"
        write_line(2, "".join(ocr_line))

    # Linje 5–7: Eksamensdata
    write_line(5, "EKS1234")
    write_line(6, "VÅR 20XY")
    write_line(7, "10")

    # Linje 4: Task progress (gradvis fylt med 5)
    task_line = list("0" * 10)
    for i in range(10):
        task_line[i] = "5"
        write_line(4, "".join(task_line))

    print("\n✅ Simulering ferdig – progress.txt er komplett!")

if __name__ == "__main__":
    simulate_progress()
