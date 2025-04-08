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
nonchalant = "Do not explain what you are doing, just do it."
task_process_instructions = [
    {
        "instruction": (
            f"{nonchalant} What is task number {{task_number}}? "
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
            f"{nonchalant} Translate the task to norwegian bokmål. Keep everything else."
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
            "Answer 1 if this is a valid task that could be in an exam and that can be logically solved, otherwise 0."
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
    task: Optional[str] = None
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
        f"in those cases write e.g. IMAX20XX instead. {ocr_text}",
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
        f"{nonchalant} How many tasks are in this text? "
        f"Answer with a single number only. "
        f"Here is the text: {ocr_text}",
        max_tokens=1000,
        isNum=True,
        maxLen=2
    )
    # Merk: For testing har du hardkodet exam.amount = 5
    exam.amount = 5 if not amount_str else int(amount_str)

    print(f"[DEEPSEEK] | Number of tasks found: {exam.amount}\n")
    write_exam_info_line(6, str(exam.amount))

    global exam_amount
    exam_amount = exam.amount

    return exam


##########################
# Prosesser én oppgave   #
##########################

async def process_task(task_number, ocr_text, exam):
    # Sett resultatet til ocr-teksten som utgangspunkt
    result = ocr_text
    task_exam = deepcopy(exam)

    while True:  # Gjenta inntil valideringssteget (siste instruksjon) svarer 1
        task_output = None  # Tekstlig innhold for denne oppgaven
        points = None       # Antall poeng, hentes i steg 2

        for i, step_info in enumerate(task_process_instructions, start=1):
            # Bytt ut placeholder {task_number} i instruksjonen
            instruction_text = step_info["instruction"].format(task_number=f"{task_number:02d}") + result

            print("\n\n\n\n" + instruction_text + "\n\n\n\n")

            # Kall promptfunksjonen
            result = await prompttotext.async_prompt_to_text(
                instruction_text,
                max_tokens=step_info["max_tokens"],
                isNum=step_info["isNum"],
                maxLen=step_info["maxLen"]
            )

            # Oppdater status for denne oppgaven til "steg i"
            task_status[task_number] = i
            update_progress_file()

            # Steg 2: Antall poeng
            if i == 2:
                task_exam.points = result

            # VALIDERINGSSTEG: Bruker i == len(task_process_instructions)
            elif i == len(task_process_instructions):
                valid = int(result) if result.isdigit() else 0
                if valid == 0:
                    print(f"[DEEPSEEK] [TASK {task_number:02d}] | Task not approved. Retrying from first step...\n")
                    break  # Avbryt for-løkka, gå tilbake i while-løkka
                else:
                    # Gyldig oppgave, sett endelig tekst
                    task_exam.text = task_output
                    task_status[task_number] = 6
                    update_progress_file()
                    print(f"[DEEPSEEK] [TASK {task_number:02d}] | Task approved.\n")
                    return task_exam

            # For oppdatering av oppgavetekst ved alle andre steg
            else:
                task_output = result

        else:
            # Hvis vi kom hit uten break (dvs. ingen validering), returner det vi har
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
      3) Kjør stegvis prosessering av hver oppgave.
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
    for idx, res in enumerate(results, start=1):
        if res.text is not None:
            print(f"Result for task {idx:02d}: {res.text}\n   (Points: {res.points})\n")

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
