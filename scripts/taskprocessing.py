import asyncio
import prompttotext
from dataclasses import dataclass, field
from typing import Optional, List
from copy import deepcopy
from pathlib import Path
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

######################
# Konfigurasjon     #
######################

# Definer sti for progress.txt
progress_file = Path(__file__).resolve().parent / "progress.txt"

# Global status-sporing per task (1–5 i dette eksempelet)
task_status = defaultdict(lambda: 0)
exam_amount = 0  # Oppdateres når vi vet hvor mange oppgaver (amount)

# Instruksjoner for steg-prosessering av hver oppgave
# Her kan du legge til/fjerne steg som du vil.
nonchalant = "Do not explain what you are doing, just do it."
task_process_instructions = [
    {
        "instruction": (
            f"{nonchalant} What is task {{task_number}}? "
            "Write only all text related directly to that one task from the raw text. "
            "Include how many maximum points you can get. Do not solve the task."
        ),
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 2000
    },
    {
        "instruction": (
            f"{nonchalant} MAKE SURE YOU ONLY RESPOND WITH A NUMBER!!! "
            "How many points can you get for task {task_number}? Only reply with the number of points, nothing else."
        ),
        "max_tokens": 1000,
        "isNum": True,
        "maxLen": 2
    },
    {
        "instruction": (
            f"{nonchalant} Remove all text related to Inspera and exam administration, "
            "keep only what is necessary for solving the task."
        ),
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 2000
    },
    {
        "instruction": (
            f"{nonchalant} Translate the task to norwegian bokmål if it is not already in norwegian bokmål."
        ),
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 2000
    },
    {
        "instruction": (
            f"{nonchalant} MAKE SURE YOU ONLY RESPOND WITH 0 OR 1!!! "
            "Answer 1 if this is a valid task that has all the contents needed to could be logically solved, otherwise 0."
        ),
        "max_tokens": 1000,
        "isNum": True,
        "maxLen": 1
    }
]


######################
# Dataklasser       #
######################

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


######################
# Filhjelp          #
######################

def ensure_min_lines(lines, min_len):
    """Sørger for at listen 'lines' har minst 'min_len' elementer."""
    while len(lines) < min_len:
        lines.append("\n")
    return lines

def update_progress_file():
    """
    Oppdaterer linje 4 (index=3) i progress.txt med status.
    status_str = '1234...' der hvert siffer angir status for en oppgave.
    """
    status_str = ''.join(str(task_status[i]) for i in range(1, exam_amount + 1))
    try:
        if progress_file.exists():
            with open(progress_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        else:
            lines = []

        lines = ensure_min_lines(lines, 4)
        lines[3] = f"{status_str}\n"

        with open(progress_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

        print(f"[STATUS] | Updated progress to '{status_str}' in {progress_file}")
    except Exception as e:
        print(f"[ERROR] Could not update progress file: {e}")

def write_exam_info_line(line_index: int, info_text: str):
    """
    Skriver 'info_text' til progress.txt på en bestemt linje.
    """
    try:
        if progress_file.exists():
            with open(progress_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        else:
            lines = []

        lines = ensure_min_lines(lines, line_index + 1)
        lines[line_index] = f"{info_text}\n"

        with open(progress_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

        print(f"[STATUS] | Wrote '{info_text}' to line {line_index + 1} in {progress_file}")
    except Exception as e:
        print(f"[ERROR] Could not write '{info_text}' to line {line_index+1} in progress file: {e}")


######################
# Henter eksamensinfo
######################

async def get_exam_info(ocr_text):
    """
    Henter info om eksamen (subject, version, amount).
    Oppdaterer linje 5,6,7 i progress.txt etter hver innhentet verdi.
    """
    exam = Exam()
    # Step: Subject
    exam.subject = await prompttotext.async_prompt_to_text(
        f"{nonchalant} What is the subject code for this exam? "
        f"Respond only with the singular formatted subject code (e.g., IFYT1000, IMAT2022). "
        f"In some cases the code will have redundant letters/numbers with variations, "
        f"in those cases write IMAX20XX instead. {ocr_text}",
        max_tokens=1000,
        isNum=False,
        maxLen=10
    )
    print(f"[DEEPSEEK] | Subject code found: {exam.subject}\n")
    write_exam_info_line(4, exam.subject if exam.subject else "")

    # Step: Version
    exam.version = await prompttotext.async_prompt_to_text(
        f"{nonchalant} What exam edition is this exam? "
        f"Respond only with the singular formatted exam edition (e.g., Høst 2023, Vår 2022). "
        f"S20XX means Sommer 20XX. {ocr_text}",
        max_tokens=1000,
        isNum=False,
        maxLen=12
    )
    print(f"[DEEPSEEK] | Exam version found: {exam.version}\n")
    write_exam_info_line(5, exam.version if exam.version else "")

    # Step: Amount
    amount_str = await prompttotext.async_prompt_to_text(
        f"{nonchalant} How many tasks are in this text? Answer with a single number only: {ocr_text}",
        max_tokens=1000,
        isNum=True,
        maxLen=2
    )
    exam.amount = int(amount_str) if amount_str else 0
    print(f"[DEEPSEEK] | Number of tasks found: {exam.amount}\n")
    write_exam_info_line(6, str(exam.amount))

    global exam_amount
    exam_amount = exam.amount

    return exam


##########################
# Prosesser én oppgave   #
##########################

async def process_task(task_number, ocr_text, exam):
    """
    Kjører en while-løkke som gjentar seg selv helt til den siste instruksjonen (validering) gir 1.
    - For hvert steg i `task_process_instructions` (1–5) kjører vi en prompt.
    - For nest siste steg lagrer vi output i henholdsvis 'task_output' eller 'points'.
    - For siste steg (validering = 0/1), fortsetter løkken ved 0, og avslutter ved 1.
    
    Koden er asynkron, så Oppgave 1 venter ikke på Oppgave 2. 
    """
    # Vi lager en kopi av exam-objektet for denne oppgaven
    task_exam = deepcopy(exam)
    task_exam.task = task_number

    while True:  # Gjenta inntil valideringssteget (siste instruksjon) svarer 1
        task_output = None  # Tekstlig innhold for denne runden
        points = None       # Antall poeng, hentes i steg 2

        for i, step_info in enumerate(task_process_instructions, start=1):
            # Bytt ut placeholder {task_number} i instruksjonen
            instruction_text = step_info["instruction"].format(task_number=f"{task_number:02d}")
            
            # Kall promptfunksjonen
            result = await prompttotext.async_prompt_to_text(
                instruction_text,
                max_tokens=step_info["max_tokens"],
                isNum=step_info["isNum"],
                maxLen=step_info["maxLen"]
            )

            if result is None:
                # Hvis None, feilet prompt. Oppgaven avbrytes
                print(f"[DEEPSEEK] [TASK {task_number:02d}] | FAILED at step {i}. Skipping task.")
                task_exam.text = None
                return task_exam

            # Oppdater status for denne oppgaven til "steg i" (1–5)
            task_status[task_number] = i
            update_progress_file()

            # Hvis ikke siste steg, behandler vi output:
            #   Steg 1: Oppgavetekst
            #   Steg 2: Poeng
            #   Steg 3: Renset tekst
            #   Steg 4: Oversatt tekst
            #   Steg 5: Validering (0/1)
            if i == 1:
                # Steg 1: Tekst
                task_output = result
            elif i == 2:
                # Steg 2: Poeng
                points = result  # Tekstlig tall (siden isNum=True)
            elif i == 3 or i == 4:
                # Steg 3 & 4: Oppdaterer oppgavetekst
                task_output = result
            elif i == 5:
                # Siste steg: Validering
                valid = int(result) if result.isdigit() else 0
                if valid == 0:
                    print(f"[DEEPSEEK] [TASK {task_number:02d}] | Task not approved. Retrying from first step...\n")
                    break  # Avbryt for-løkke, men while-løkka fortsetter
                else:
                    # Gyldig oppgave
                    task_exam.text = task_output
                    task_exam.points = points
                    task_status[task_number] = 5
                    update_progress_file()
                    print(f"[DEEPSEEK] [TASK {task_number:02d}] | Task approved.\n")
                    return task_exam
        else:
            # Hvis vi fullførte for-løkka uten `break`, da er vi ferdig
            # (Skjer om det ikke finnes en validering i siste steg, men det gjør det her.)
            # Returner oppgaven likevel
            task_exam.text = task_output
            task_exam.points = points
            return task_exam


######################
# Hovedfunksjon     #
######################

async def main_async(ocr_text):
    """
    Asynkron hovedfunksjon som:
      1) Henter exam-info (subject, version, amount).
      2) Lager async tasks for hver oppgave.
      3) Hver oppgave kjører sine 5 steg uavhengig av andres.
      4) Samler resultater og skriver ut.
    """
    exam_template = await get_exam_info(ocr_text)
    print(f"[DEEPSEEK] | Started processing all tasks\n")

    # Opprett asynkrone tasks for hver oppgave
    tasks = [
        asyncio.create_task(process_task(i, ocr_text, exam_template))
        for i in range(1, exam_template.amount + 1)
    ]

    # Vent på at alle skal fullføre
    results = await asyncio.gather(*tasks)

    # Hent ut hvem som feilet, etc.
    failed_tasks = [res.task for res in results if res.text is None]
    points = [res.points for res in results if res.text is not None]

    # Skriv ut resultater
    for res in results:
        if res.text is not None:
            print(f"Result for task {res.task:02d}: {res.text}\n   (Points: {res.points})\n")

    print(f"[DEEPSEEK] | Failed tasks: {failed_tasks}")
    print(f"[DEEPSEEK] | Points for tasks: {points}")
    print(f"[DEEPSEEK] | Final total cost: {prompttotext.total_cost:.4f} USD")

    return results


def main(ocr_text):
    """
    Synkron wrapper for den asynkrone hovedfunksjonen.
    Kalles fra annet script i applikasjonen.
    """
    return asyncio.run(main_async(ocr_text))
