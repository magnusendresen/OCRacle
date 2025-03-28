import asyncio
import prompttotext
from dataclasses import dataclass, field
from typing import Optional, List
from copy import deepcopy
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Progress.txt-plassering
progress_file = Path(__file__).resolve().parent / "progress.txt"

# Oppgave-status-sporing (default til steg 1)
from collections import defaultdict
task_status = defaultdict(lambda: 1)

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

async def get_exam_info(ocr_text):
    nonchalant = "Do not explain what you are doing, just do it."
    exam = Exam()

    exam.subject = await prompttotext.async_prompt_to_text(
        f"{nonchalant} What is the subject code for this exam? Respond only with the singular formatted subject code (e.g., IFYT1000, IMAT2022). In some cases the code wil have redundant letters and/or numbers with variations, in those cases write IMAX20XX instead. {ocr_text}",
        max_tokens=1000,
        isNum=False,
        maxLen=10
    )
    print(f"[DEEPSEEK] | Subject code found: {exam.subject}\n")

    exam.version = await prompttotext.async_prompt_to_text(
        f"{nonchalant} What exam edition is this exam? Respond only with the singular formatted exam edition (e.g., H\u00f8st 2023, V\u00e5r 2022). S20XX means Sommer 20XX. {ocr_text}",
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

    return exam

async def process_task(task_number, ocr_text, exam):
    prompttotext.current_task.set(f"{task_number:02d}")
    nonchalant = "Do not explain what you are doing, just do it."

    task = deepcopy(exam)
    task.task = task_number

    while True:
        task_status[task_number] = 1
        prompttotext.current_step.set("Step 1")
        task_output = await prompttotext.async_prompt_to_text(
            f"{nonchalant} What is task {prompttotext.current_task.get()}? Write only all text related directly to that one task from the raw text. Include how many maximum points you can get. Do not solve the task. {ocr_text}",
            max_tokens=1000,
            isNum=False,
            maxLen=2000
        )
        if task_output is None:
            print(f"[DEEPSEEK] [TASK {prompttotext.current_task.get()}] | FAILED at Step 1. Skipping task.")
            return task

        task_status[task_number] = 2
        prompttotext.current_step.set("Step 2")
        point = await prompttotext.async_prompt_to_text(
            f"{nonchalant} MAKE SURE YOU ONLY RESPOND WITH A NUMBER!!! How many points can you get for task {prompttotext.current_task.get()}? Only reply with the number of points, nothing else. {task_output}",
            max_tokens=1000,
            isNum=True,
            maxLen=2
        )
        if point is None:
            print(f"[DEEPSEEK] [TASK {prompttotext.current_task.get()}] | FAILED at Step 2. Skipping task.")
            return task

        task_status[task_number] = 3
        prompttotext.current_step.set("Step 3")
        task_output_clean = await prompttotext.async_prompt_to_text(
            f"{nonchalant} Remove all text related to Inspera and exam administration, keep only what is necessary for solving the task: {task_output}",
            max_tokens=1000,
            isNum=False,
            maxLen=2000
        )
        if task_output_clean is None:
            print(f"[DEEPSEEK] [TASK {prompttotext.current_task.get()}] | FAILED at Step 3. Skipping task.")
            return task
        task_output = task_output_clean

        task_status[task_number] = 4
        prompttotext.current_step.set("Step 4")
        valid_response = await prompttotext.async_prompt_to_text(
            f"{nonchalant} MAKE SURE YOU ONLY RESPOND WITH 0 OR 1!!! Answer 1 if this is a valid task, otherwise 0: {task_output}",
            max_tokens=1000,
            isNum=True,
            maxLen=1
        )
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

async def print_task_status(exam_template):
    while True:
        status_array = [str(task_status[i]) for i in range(1, exam_template.amount + 1)]
        status_str = ''.join(status_array)
        print(f"[STATUS] | {status_str}")
        try:
            with open(progress_file, "w", encoding="utf-8") as f:
                f.write(status_str)
                f.flush()
            print(f"[STATUS] | Wrote {status_str} to progress.txt")
        except Exception as e:
            print(f"[ERROR] Could not write progress.txt: {e}")
        await asyncio.sleep(5)

async def main_async(ocr_text):
    exam_template = await get_exam_info(ocr_text)
    print(f"[DEEPSEEK] | Started processing all tasks")

    asyncio.create_task(print_task_status(exam_template))

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
