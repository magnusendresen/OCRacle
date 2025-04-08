import asyncio
import prompttotext
from dataclasses import dataclass, field
from typing import Optional, List
from copy import deepcopy
from pathlib import Path
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

progress_file = Path(__file__).resolve().parent / "progress.txt"
task_status = defaultdict(lambda: 0)
exam_amount = 0

nonchalant = "DONT EVER EXPLAIN OR SAY WHAT YOU ARE DOING. JUST DO AS YOU ARE TOLD AND RESPOND WITH WHAT IS ASKED FROM YOU. "
task_process_instructions = [
    {
        "instruction": (
            f"{nonchalant} What is task number {{task_number}}? "
            "Write only all text related directly to that one task from the raw text. "
            "Include how many maximum points you can get. Do not solve the task: "
        ),
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 2000
    },
    {
        "instruction": (
            f"{nonchalant} MAKE SURE YOU ONLY RESPOND WITH A NUMBER!!! "
            "How many points can you get for this task? Only reply with the number of points, nothing else: "
        ),
        "max_tokens": 1000,
        "isNum": True,
        "maxLen": 2
    },
    {
        "instruction": (
            f"{nonchalant} Remove all text related to Inspera and exam administration, "
            "keep only what is necessary for solving the task: "
        ),
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 2000
    },
    {
        "instruction": (
            f"{nonchalant} Translate this task text from norwegian bokmål or english to norwegian bokmål, do not change anything else."
            "If it is already in norwegian bokmål respond with the exact same text: "
        ),
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 2000
    },
    {
        "instruction": (
            f"{nonchalant} MAKE SURE YOU ONLY RESPOND WITH 0 OR 1!!! "
            "Answer 1 if this is a valid task that could be in an exam and that can be logically solved, otherwise 0:"
        ),
        "max_tokens": 1000,
        "isNum": True,
        "maxLen": 2
    }
]

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

def ensure_min_lines(lines, min_len):
    while len(lines) < min_len:
        lines.append("\n")
    return lines

def update_progress_file():
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

async def get_exam_info(ocr_text):
    exam = Exam()
    exam.subject = await prompttotext.async_prompt_to_text(
        f"{nonchalant} What is the subject code for this exam? "
        f"Respond only with the singular formatted subject code (e.g., IFYT1000). "
        f"In some cases the code will have redundant letters/numbers, "
        f"in those cases write e.g. IMAX20XX instead. {ocr_text}",
        max_tokens=1000,
        isNum=False,
        maxLen=10
    )
    print(f"[DEEPSEEK] | Subject code found: {exam.subject}\n")
    write_exam_info_line(4, exam.subject if exam.subject else "")

    exam.version = await prompttotext.async_prompt_to_text(
        f"{nonchalant} What exam edition is this exam? "
        f"Respond only with the singular formatted exam edition (e.g., Høst 2023). "
        f"S20XX means Sommer 20XX. {ocr_text}",
        max_tokens=1000,
        isNum=False,
        maxLen=12
    )
    print(f"[DEEPSEEK] | Exam version found: {exam.version}\n")
    write_exam_info_line(5, exam.version if exam.version else "")

    amount_str = await prompttotext.async_prompt_to_text(
        f"{nonchalant} How many tasks are in this text? "
        f"Answer with a single number only. "
        f"Here is the text: {ocr_text}",
        max_tokens=1000,
        isNum=True,
        maxLen=2
    )
    exam.amount = 5 if not amount_str else int(str(amount_str))
    print(f"[DEEPSEEK] | Number of tasks found: {exam.amount}\n")
    write_exam_info_line(6, str(exam.amount))

    global exam_amount
    exam_amount = exam.amount
    return exam

async def process_task(task_number, ocr_text, exam):
    task_exam = deepcopy(exam)

    while True:
        task_output = str(ocr_text)
        points = None
        valid = 0

        # Loop for alle steg
        for i in range(len(task_process_instructions)):

            # Initiell innhenting av oppgavetekst
            if i == 0:
                task_output = str(
                    await prompttotext.async_prompt_to_text(
                        task_process_instructions[i]["instruction"].format(task_number=f"{task_number}") + task_output,
                        max_tokens=task_process_instructions[i]["max_tokens"],
                        isNum=task_process_instructions[i]["isNum"],
                        maxLen=task_process_instructions[i]["maxLen"]
                    )
                )
            
            # Innhenting av poeng
            elif i == 1:
                points = int(
                    await prompttotext.async_prompt_to_text(
                        task_process_instructions[i]["instruction"] + task_output,
                        max_tokens=task_process_instructions[i]["max_tokens"],
                        isNum=task_process_instructions[i]["isNum"],
                        maxLen=task_process_instructions[i]["maxLen"]
                    )
                )
            
            # Oppdatering av oppgavetekst
            elif not i == len(task_process_instructions) - 1:
                task_output = str(
                    await prompttotext.async_prompt_to_text(
                        task_process_instructions[i]["instruction"] + task_output,
                        max_tokens=task_process_instructions[i]["max_tokens"],
                        isNum=task_process_instructions[i]["isNum"],
                        maxLen=task_process_instructions[i]["maxLen"]
                    )
                )

            # Validering av oppgava
            else:
                valid = int(
                    await prompttotext.async_prompt_to_text(
                        task_process_instructions[i]["instruction"] + task_output,
                        max_tokens=task_process_instructions[i]["max_tokens"],
                        isNum=task_process_instructions[i]["isNum"],
                        maxLen=task_process_instructions[i]["maxLen"]
                    )
                )
                

            print("\n\n\n\n" + task_output + "\n\n\n\n")

            # Oppdatering av progress.txt til c++
            task_status[task_number] = i + 1
            update_progress_file()
            

        # Behandling av valideringsboolean
        if valid == 0:
            print(f"[DEEPSEEK] [TASK {task_number:02d}] | Task not approved. Retrying...\n")
            return None
        else:
            task_exam.task = task_number
            task_exam.text = task_output
            task_exam.points = points
            task_status[task_number] = 6
            update_progress_file()
            print(f"[DEEPSEEK] [TASK {task_number:02d}] | Task approved.\n")
            return task_exam

async def main_async(ocr_text):
    exam_template = await get_exam_info(ocr_text)
    print(f"[DEEPSEEK] | Started processing all tasks\n")

    tasks = [
        asyncio.create_task(process_task(i, ocr_text, exam_template))
        for i in range(1, exam_template.amount + 1)
    ]
    results = await asyncio.gather(*tasks)

    failed_tasks = [res.task for res in results if res.text is None]
    points = [res.points for res in results if res.text is not None]

    for idx, res in enumerate(results, start=1):
        if res.text is not None:
            print(f"Result for task {idx:02d}: {res.text}\n   (Points: {res.points})\n")

    print(f"[DEEPSEEK] | Failed tasks: {failed_tasks}")
    print(f"[DEEPSEEK] | Points for tasks: {points}")
    print(f"[DEEPSEEK] | Final total cost: {prompttotext.total_cost:.4f} USD")
    return results

def main(ocr_text):
    return asyncio.run(main_async(ocr_text))
