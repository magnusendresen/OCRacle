import asyncio
import prompttotext
from dataclasses import dataclass, field
from typing import Optional, List
from copy import deepcopy
from pathlib import Path
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

# Definer sti for progress.txt
progress_file = Path(__file__).resolve().parent / "progress.txt"

# Oppgave-status-sporing (default starter vi med 0)
task_status = defaultdict(lambda: 0)
exam_amount = 0  # Global verdi for antall oppgaver

@dataclass
class Exam:
    version: Optional[str] = None
    task: Optional[int] = None
    subject: Optional[str] = None
    text: Optional[str] = None
    points: Optional[int] = None
    images: List[str] = field(default_factory=list)
    code: Optional[str] = None
    amount: Optional[int] = None

    def __str__(self):
        return f"Task {self.task}: {self.text} (Points: {self.points})"

# Hjelpetekster for prompt
nonchalant = "Do not explain what you are doing, just do it."
boolean = ("MAKE SURE YOU ONLY RESPOND WITH 0 OR 1!!! "
           "Answer 1 if this is a valid task, otherwise 0.")

async def get_exam_info(ocr_text):
    """
    Henter informasjon fra eksamens-OCR.
    Returnerer et Exam-objekt som fungerer som mal for alle oppgaver,
    med subject, version og antall oppgaver (amount) satt.
    """
    exam = Exam()
    
    exam.subject = await prompttotext.async_prompt_to_text(
        f"{nonchalant} What is the subject code for this exam? "
        f"Respond only with the singular formatted subject code (e.g., IFYT1000, IMAT2022). "
        f"In some cases the code will have redundant letters and/or numbers with variations, "
        f"in those cases write IMAX20XX instead. {ocr_text}",
        max_tokens=1000,
        isNum=False,
        maxLen=10
    )
    print(f"[DEEPSEEK] | Subject code found: {exam.subject}\n")

    exam.version = await prompttotext.async_prompt_to_text(
        f"{nonchalant} What exam edition is this exam? "
        f"Respond only with the singular formatted exam edition (e.g., Høst 2023, Vår 2022). "
        f"S20XX means Sommer 20XX. {ocr_text}",
        max_tokens=1000,
        isNum=False,
        maxLen=12
    )
    print(f"[DEEPSEEK] | Exam version found: {exam.version}\n")

    exam.amount = int(await prompttotext.async_prompt_to_text(
        f"{nonchalant} How many tasks are in this text? Answer with a single number only: {ocr_text}",
        max_tokens=1000,
        isNum=True,
        maxLen=2
    ))
    print(f"[DEEPSEEK] | Number of tasks found: {exam.amount}\n")
    
    global exam_amount
    exam_amount = exam.amount
    
    return exam

def update_progress_file():
    """
    Oppdaterer linje 4 i progress.txt med statusstrengen.
    Statusstrengen består av ett siffer for hver oppgave (1,2,3 eller 4),
    avhengig av hvor langt hver oppgave har kommet.
    """
    status_str = ''.join(str(task_status[i]) for i in range(1, exam_amount + 1))
    try:
        if progress_file.exists():
            with open(progress_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        else:
            lines = []
        if len(lines) < 4:
            lines += ["\n"] * (4 - len(lines))
        lines[3] = f"{status_str}\n"
        with open(progress_file, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"[STATUS] | Updated progress to '{status_str}' in {progress_file}")
    except Exception as e:
        print(f"[ERROR] Could not update progress file: {e}")

async def process_task(task_number, ocr_text, exam):
    """
    Prosesserer én oppgave gjennom 4 steg, asynkront og uavhengig av andre oppgaver:
      1. Ekstraher oppgavetekst.
      2. Finn ut hvor mange maks poeng oppgaven har.
      3. Fjern irrelevant tekst.
      4. Valider oppgaven.
      
    Hvis et steg (unntatt validering) feiler (prompttotext returnerer None),
    markeres oppgaven som feilet ved å returnere et Exam med kun task satt.
    Dersom valideringen (Step 4) ikke gir 1, prøves oppgaven på nytt.
    Returnerer et Exam med gyldig data når oppgaven er godkjent.
    
    Viktig: Oppgaven kjører disse stegene i rekkefølge for seg selv og
    venter ikke på andre oppgaver.
    """
    # Lokal kopi av exam-objektet for denne oppgaven
    task_exam = deepcopy(exam)
    task_exam.task = task_number

    while True:
        # Step 1: Ekstraher oppgavetekst (tekst, isNum=False)
        step1_prompt = (
            f"{nonchalant} What is task {task_number:02d}? "
            f"Write ONLY all text related to that one task from the raw text. "
            f"Include how many maximum points you can get, do not solve the task. {ocr_text}"
        )
        task_output = await prompttotext.async_prompt_to_text(
            step1_prompt,
            max_tokens=1000,
            isNum=False,
            maxLen=2000
        )
        if task_output is None:
            print(f"[DEEPSEEK] [TASK {task_number:02d}] | FAILED at Step 1. Skipping task.")
            task_exam.text = None
            return task_exam
        task_status[task_number] = 1
        update_progress_file()

        # Step 2: Finn ut hvor mange maks poeng (numerisk, isNum=True)
        step2_prompt = (
            f"{nonchalant} MAKE SURE YOU ONLY RESPOND WITH A NUMBER!!! "
            f"How many points can you get for task {task_number:02d}? "
            f"Only reply with the number, nothing else. {task_output}"
        )
        point = await prompttotext.async_prompt_to_text(
            step2_prompt,
            max_tokens=1000,
            isNum=True,
            maxLen=2
        )
        if point is None:
            print(f"[DEEPSEEK] [TASK {task_number:02d}] | FAILED at Step 2. Skipping task.")
            task_exam.text = None
            return task_exam
        task_status[task_number] = 2
        update_progress_file()

        # Step 3: Fjern irrelevant tekst
        step3_prompt = (
            f"{nonchalant} Remove all text related to Inspera and exam administration, "
            f"keep only what is necessary for solving the task: {task_output}"
        )
        task_output_clean = await prompttotext.async_prompt_to_text(
            step3_prompt,
            max_tokens=1000,
            isNum=False,
            maxLen=2000
        )
        if task_output_clean is None:
            print(f"[DEEPSEEK] [TASK {task_number:02d}] | FAILED at Step 3. Skipping task.")
            task_exam.text = None
            return task_exam
        task_output = task_output_clean
        task_status[task_number] = 3
        update_progress_file()

        # Step 4: Valider oppgaven (numerisk, isNum=True)
        step4_prompt = (
            f"{nonchalant} MAKE SURE YOU ONLY RESPOND WITH 0 OR 1!!! "
            f"Answer 1 if this is a valid task, otherwise 0: {task_output}"
        )
        valid_response = await prompttotext.async_prompt_to_text(
            step4_prompt,
            max_tokens=1000,
            isNum=True,
            maxLen=1
        )
        if valid_response is None:
            print(f"[DEEPSEEK] [TASK {task_number:02d}] | FAILED at Step 4. Skipping task.")
            task_exam.text = None
            return task_exam

        if valid_response == 0:
            print(f"[DEEPSEEK] [TASK {task_number:02d}] | Task not approved. Retrying...")
            continue
        elif valid_response == 1:
            print(f"[DEEPSEEK] [TASK {task_number:02d}] | Task approved.")
            task_exam.text = task_output
            task_exam.points = point
            task_status[task_number] = 4
            update_progress_file()
            return task_exam

async def main_async(ocr_text):
    """
    Asynkron hovedfunksjon som prosesserer et antall oppgaver parallelt.
    Hver oppgave kjører sin egen process_task, og venter kun på seg selv.
    """
    exam_template = await get_exam_info(ocr_text)
    print(f"[DEEPSEEK] | Started processing all tasks\n")

    # Start alle oppgaver parallelt
    tasks = [
        asyncio.create_task(process_task(i, ocr_text, exam_template))
        for i in range(1, exam_template.amount + 1)
    ]
    
    # Vent til alle oppgaver er ferdige (hver oppgave kjører 1-4 i egen rekkefølge)
    results = await asyncio.gather(*tasks)

    failed_tasks = [res.task for res in results if res.text is None]
    points = [res.points for res in results if res.text is not None]

    for res in results:
        if res.text is not None:
            print(f"Result for task {res.task:02d}: {res.text}  (Points: {res.points})\n")

    print(f"[DEEPSEEK] | Failed tasks: {failed_tasks}")
    print(f"[DEEPSEEK] | Points for tasks: {points}")
    print(f"[DEEPSEEK] | Final total cost: {prompttotext.total_cost:.4f} USD")
    return results

def main(ocr_text):
    """
    Synkron wrapper for den asynkrone hovedfunksjonen.
    Importeres og kalles fra et annet skript.
    """
    return asyncio.run(main_async(ocr_text))
