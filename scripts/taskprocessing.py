import asyncio
import time
from pathlib import Path
from typing import List
from dataclasses import dataclass, field

# For enkelhet: Global variabel for antall oppgaver + global step-teller
exam_amount = 0
globalSteps = 0  # Antall fullførte del-steg, for alle oppgaver til sammen
steps_per_task = 4  # F.eks. 4 steg per oppgave

@dataclass
class Exam:
    version: str = ""
    task: int = 0
    subject: str = ""
    text: str = ""
    points: int = 0
    images: List[str] = field(default_factory=list)
    code: str = ""
    amount: int = 0

def write_progress(level: int):
    """
    Skriver 'level' (0–9) til progress.txt
    """
    script_dir = Path(__file__).resolve().parent
    progress_file = script_dir / "progress.txt"
    try:
        with open(progress_file, "w", encoding="utf-8") as f:
            f.write(str(level))
    except Exception as e:
        print(f"[ERROR] Could not write to progress.txt: {e}")

async def continuous_status_updater():
    """
    Mens oppgaver prosesseres, oppdaterer denne total progress (0-9).
    Kjøres i bakgrunn, stopper når vi har nådd 9 (altså 100%).
    """
    global globalSteps

    while True:
        # Hvor langt har vi kommet i sum?
        total_needed = exam_amount * steps_per_task
        fraction = 0.0
        if total_needed > 0:
            fraction = globalSteps / total_needed
        level = min(int(fraction * 9.999), 9)

        # Skriv til progress.txt
        write_progress(level)

        # Er vi i mål?
        if level == 9:  # 100%
            break

        await asyncio.sleep(1)

async def get_exam_info(ocr_text: str) -> Exam:
    """
    Hent basisinfo (antall oppgaver, subject, etc.)
    Tilpass til din AI/DeepSeek/regex.
    """
    exam = Exam()
    exam.amount = 3        # F.eks. 3 oppgaver
    exam.subject = "IMAX20XX"
    exam.version = "H24"
    return exam

async def process_task(task_number: int, exam_template: Exam, rawtext: str):
    """
    Prosesser én oppgave. Øk globalSteps for hver "del-steg" i denne funksjonen.
    """
    global globalSteps

    # Step 1
    # ... kjør AI, prompt osv. ...
    time.sleep(0.5)
    globalSteps += 1  # Ferdig med del-steg 1 for denne oppgaven

    # Step 2
    time.sleep(0.5)
    globalSteps += 1

    # Step 3
    time.sleep(0.5)
    globalSteps += 1

    # Step 4
    time.sleep(0.5)
    globalSteps += 1

    # Returner fullført oppgave
    return Exam(
        version=exam_template.version,
        subject=exam_template.subject,
        task=task_number,
        text=f"Oppgave {task_number} ...",
        points=5,
        amount=exam_template.amount
    )

async def main_async(rawtext: str):
    global exam_amount, globalSteps

    # Sett tellerne til 0 hver gang (i tilfelle gjentatte kall)
    globalSteps = 0

    # Hent info om eksamen
    exam_template = await get_exam_info(rawtext)
    exam_amount = exam_template.amount  # antall oppgaver

    # Sett i gang en bakgrunnsoppgave som jevnlig skriver progress
    status_task = asyncio.create_task(continuous_status_updater())

    # Kjør alle oppgaver parallelt
    tasks = []
    for i in range(1, exam_amount + 1):
        tasks.append(asyncio.create_task(process_task(i, exam_template, rawtext)))

    # Vent på at alle oppgaver fullføres
    results = await asyncio.gather(*tasks)

    # Vent på at status-oppdaterer er ferdig
    await status_task

    return results

def main(rawtext: str):
    """
    Kalles synkront fra main.py
    """
    return asyncio.run(main_async(rawtext))
