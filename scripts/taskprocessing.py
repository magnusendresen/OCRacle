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

# Oppgave-status-sporing (default starter vi med 0, og oppdaterer til 1,2,3,4 etter hvert steg)
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
    
nonchalant = "Do not explain what you are doing, just do it."

exam_info_instructions = [
    {
        "instruction": f"{nonchalant} What is the subject code for this exam? Respond only with the singular formatted subject code (e.g., IFYT1000, IMAT2022). In some cases the code will have redundant letters and/or numbers with variations, in those cases write eg. IMAX20XX instead.",
        "verification": "Is this a valid subject code, consisting of 3-4 letters followed by 3-4 digits?",
        "error": "Invalid subject code.",
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 10
    },
    {
        "instruction": f"{nonchalant} What exam edition is this exam? Respond only with the singular formatted exam edition (e.g., Høst 2023, Vår 2022). S20XX means Sommer 20XX.",
        "verification": "Is this a valid exam edition written in norwegian, consisting of a season and year?",
        "error": "Invalid exam edition.",
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 12
    },
    {
        "instruction": f"{nonchalant} How many tasks are in this text? Answer with a single number only.",
        "verification": "Is this a valid integer?",
        "error": "Invalid number of tasks.",
        "max_tokens": 1000,
        "isNum": True,
        "maxLen": 2
    }
]

task_process_instructions = [
    {
        "instruction": f"{nonchalant} What is task {prompttotext.current_task.get()}? Write only all text related directly to that one task from the raw text. Include how many maximum points you can get. Do not solve the task.",
        "verification": "Is this a valid task?",
        "error": "Invalid task detected in step ",
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 2000
    },
    {
        "instruction": f"{nonchalant} MAKE SURE YOU ONLY RESPOND WITH A NUMBER!!! How many points can you get for task {prompttotext.current_task.get()}? Only reply with the number of points, nothing else.",
        "verification": "Is this a valid integer?",
        "error": "Invalid number of points detected in step ",
        "max_tokens": 1000,
        "isNum": True,
        "maxLen": 2
    },
    {
        "instruction": f"{nonchalant} Remove all text related to Inspera and exam administration, keep only what is necessary for solving the task.",
        "verification": "Is this a valid task description, without information about exam administration and/or Inspera?",
        "error": "Invalid task detected in step ",
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 2000
    },
    {
        "instruction": f"{nonchalant} Translate the task to norwegian bokmål if it is not already in norwegian bokmål.",
        "verification": "Is the following task written in norwegian bokmål?",
        "error": "Invalid task detected in step ",
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 2000
    },
    {
        "instruction": f"{nonchalant} MAKE SURE YOU ONLY RESPOND WITH 0 OR 1!!! Answer 1 if this is a valid task that has all the contents needed to could be logically solved, otherwise 0.",
        "verification": "Is this a valid response as a boolean (0 or 1)?",
        "error": "Invalid response detected in step ",
        "max_tokens": 1000,
        "isNum": True,
        "maxLen": 1
    }
]

async def get_exam_info(ocr_text):
    global exam_amount
    
    # Start alle tre kall asynkront
    subject_task = asyncio.create_task(
        prompttotext.async_prompt_to_text(
            f"{nonchalant} What is the subject code for this exam? Respond only with the singular formatted subject code (e.g., IFYT1000, IMAT2022). In some cases the code will have redundant letters and/or numbers with variations, in those cases write IMAX20XX instead. {ocr_text}",
            max_tokens=1000,
            isNum=False,
            maxLen=10
        )
    )
    version_task = asyncio.create_task(
        prompttotext.async_prompt_to_text(
            f"{nonchalant} What exam edition is this exam? Respond only with the singular formatted exam edition (e.g., Høst 2023, Vår 2022). S20XX means Sommer 20XX. {ocr_text}",
            max_tokens=1000,
            isNum=False,
            maxLen=12
        )
    )
    amount_task = asyncio.create_task(
        prompttotext.async_prompt_to_text(
            f"{nonchalant} How many tasks are in this text? Answer with a single number only: {ocr_text}",
            max_tokens=1000,
            isNum=True,
            maxLen=2
        )
    )
    
    subject_result, version_result, amount_result = await asyncio.gather(
        subject_task, version_task, amount_task
    )
    
    exam = Exam(
        subject=subject_result,
        version=version_result,
        amount=int(amount_result)
    )
    exam_amount = exam.amount
    print(f"[DEEPSEEK] | Subject code found: {exam.subject}\n")
    print(f"[DEEPSEEK] | Exam edition found: {exam.version}\n")
    print(f"[DEEPSEEK] | Number of tasks found: {exam.amount}\n")
    
    return exam

def write_status_to_file():
    """
    Oppdaterer kun linje 4 i progress.txt med statusstrengen.
    Statusstrengen består av tall (1, 2, 3 eller 4) for hver oppgave.
    """
    status_str = ''.join(str(task_status[i]) for i in range(1, exam_amount + 1))
    if not hasattr(write_status_to_file, "last_status") or status_str != write_status_to_file.last_status:
        print(f"[STATUS] | {status_str}")
        try:
            if progress_file.exists():
                with open(progress_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            else:
                lines = []

            # Sørg for at vi har minst fire linjer slik at vi kan oppdatere linje 4 (indeks 3)
            if len(lines) < 4:
                lines += ["\n"] * (4 - len(lines))

            # Oppdater kun linje 4 med statusstrengen
            lines[3] = f"{status_str}\n"

            with open(progress_file, "w", encoding="utf-8") as f:
                f.writelines(lines)

            print(f"[STATUS] | Wrote '{status_str}' to line 4 of {progress_file}")
            write_status_to_file.last_status = status_str
        except Exception as e:
            print(f"[ERROR] Could not write to {progress_file}: {e}")

async def alternating_status_writer():
    while exam_amount == 0:
        await asyncio.sleep(0.1)
    while True:
        write_status_to_file()
        await asyncio.sleep(2)

async def print_task_status_loop():
    await alternating_status_writer()

async def process_task(task_number, ocr_text, exam):
    prompttotext.current_task.set(f"{task_number:02d}")
    nonchalant = "Do not explain what you are doing, just do it."

    task = deepcopy(exam)
    task.task = task_number

    while True:
        # Steg 1: Etter denne skal status være 1.
        prompttotext.current_step.set("Step 1")
        task_output = await prompttotext.async_prompt_to_text(
            f"{nonchalant} What is task {prompttotext.current_task.get()}? Write only all text related directly to that one task from the raw text. Include how many maximum points you can get. Do not solve the task. {ocr_text}",
            max_tokens=1000,
            isNum=False,
            maxLen=2000
        )
        task_status[task_number] = 1
        if task_output is None:
            print(f"[DEEPSEEK] [TASK {prompttotext.current_task.get()}] | FAILED at Step 1. Skipping task.")
            return task

        # Steg 2: Etter denne skal status være 2.
        prompttotext.current_step.set("Step 2")
        point = await prompttotext.async_prompt_to_text(
            f"{nonchalant} MAKE SURE YOU ONLY RESPOND WITH A NUMBER!!! How many points can you get for task {prompttotext.current_task.get()}? Only reply with the number of points, nothing else. {task_output}",
            max_tokens=1000,
            isNum=True,
            maxLen=2
        )
        task_status[task_number] = 2
        if point is None:
            print(f"[DEEPSEEK] [TASK {prompttotext.current_task.get()}] | FAILED at Step 2. Skipping task.")
            return task

        # Steg 3: Etter denne skal status være 3.
        prompttotext.current_step.set("Step 3")
        task_output_clean = await prompttotext.async_prompt_to_text(
            f"{nonchalant} Remove all text related to Inspera and exam administration, keep only what is necessary for solving the task: {task_output}",
            max_tokens=1000,
            isNum=False,
            maxLen=2000
        )
        task_status[task_number] = 3
        if task_output_clean is None:
            print(f"[DEEPSEEK] [TASK {prompttotext.current_task.get()}] | FAILED at Step 3. Skipping task.")
            return task
        task_output = task_output_clean

        # Steg 4: Etter denne skal status være 4.
        prompttotext.current_step.set("Step 4")
        valid_response = await prompttotext.async_prompt_to_text(
            f"{nonchalant} MAKE SURE YOU ONLY RESPOND WITH 0 OR 1!!! Answer 1 if this is a valid task, otherwise 0: {task_output}",
            max_tokens=1000,
            isNum=True,
            maxLen=1
        )
        task_status[task_number] = 4
        if valid_response is None:
            print(f"[DEEPSEEK] [TASK {prompttotext.current_task.get()}] | FAILED at Step 4. Skipping task.")
            return task
        if valid_response == 0:
            print(f"[DEEPSEEK] [TASK {prompttotext.current_task.get()}] | Task not approved. Retrying task.")
            continue
        elif valid_response == 1:
            print(f"[DEEPSEEK] [TASK {prompttotext.current_task.get()}] | Task approved.")
            task.text = task_output
            task.points = point
            return task

async def main_async(ocr_text):
    exam_template = await get_exam_info(ocr_text)
    print(f"[DEEPSEEK] | Started processing all tasks")

    asyncio.create_task(print_task_status_loop())

    tasks = [
        asyncio.create_task(process_task(i, ocr_text, exam_template))
        for i in range(1, exam_template.amount + 1)
    ]
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
    return asyncio.run(main_async(ocr_text))
