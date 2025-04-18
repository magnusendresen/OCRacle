import asyncio
import json
import sys
import prompttotext
import re
import difflib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from copy import deepcopy
from collections import defaultdict

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

# Paths and global state
db_dir = Path(__file__).resolve().parent
progress_file = db_dir / "progress.txt"
JSON_PATH = db_dir / "ntnu_emner.json"
task_status = defaultdict(lambda: 0)
total_tasks = 0

# Prompt prefix
nonchalant = (
    "DONT NOT EXPLAIN OR SAY WHAT YOU ARE DOING. "
    "JUST DO AS YOU ARE TOLD AND RESPOND WITH WHAT IS ASKED FROM YOU. "
)


def load_emnekart_from_json(json_path: Path):
    """
    Leser hele JSON-listen og returnerer:
      - data: rå liste av oppføringer
      - emnekart: dict fra Emnekode (uppercase) -> Emnenavn
    """
    if not json_path.is_file():
        print(f"❌ Feil: JSON-filen '{json_path}' finnes ikke.", file=sys.stderr)
        sys.exit(1)
    try:
        with json_path.open(encoding="utf-8") as jf:
            data = json.load(jf)
    except Exception as e:
        print(f"❌ Kunne ikke lese JSON: {e}", file=sys.stderr)
        sys.exit(1)

    emnekart = {}
    for entry in data:
        kode = entry.get("Emnekode")
        navn = entry.get("Emnenavn")
        if kode and navn:
            emnekart[kode.upper()] = navn
    return data, emnekart

@dataclass
class Exam:
    subject: Optional[str] = None
    matching_codes: List[str] = field(default_factory=list)
    topic: Optional[str] = None
    exam_version: Optional[str] = None
    task_number: Optional[int] = None
    points: Optional[int] = None
    task_text: Optional[str] = None
    images: List[str] = field(default_factory=list)
    code: Optional[str] = None
    total_tasks: Optional[int] = None


def write_progress(updates: Optional[Dict[int, str]] = None):
    """
    Skriver til progress.txt:
      - Hvis `updates` er None: oppdater linje 4 (0-indeks 3) med task_status
      - Ellers: bruk `updates` som {0-indeks linjenr: tekst uten newline}
    """
    try:
        if progress_file.exists():
            with open(progress_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        else:
            lines = []

        if updates is None:
            status_str = ''.join(str(task_status[i]) for i in range(1, total_tasks + 1))
            updates = {3: status_str}

        max_idx = max(updates.keys())
        while len(lines) < max_idx + 1:
            lines.append("\n")

        for idx, text in updates.items():
            lines[idx] = f"{text}\n"

        with open(progress_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

        for idx, text in updates.items():
            print(f"[STATUS] | Wrote '{text}' to line {idx + 1} in {progress_file}")
    except Exception as e:
        print(f"[ERROR] Could not update progress file: {e}")


async def get_exam_info(ocr_text: str) -> Exam:
    exam = Exam()

    # 1) Hent subject-kode via modellen
    exam.subject = await prompttotext.async_prompt_to_text(
        nonchalant
        + "What is the subject code for this exam? "
          "Respond only with the singular formatted subject code (e.g., IFYT1000). "
          "If there are variation in the last letter (e.g. IMAA, IMAG, IMAT), replace the variating letter with an X instead => IMAX. "
          "If there are variation in number(s), e.g 2002, 2012, 2022 - replace the variating number with an X instead => 20X2. "
        + ocr_text,
        max_tokens=1000,
        isNum=False,
        maxLen=50
    )
    exam.subject = exam.subject.strip().upper()
    print(f"[DEEPSEEK] | Subject code found: {exam.subject}")

    # 2) Match mot ntnu_emner.json med strengere X-logikk
    data, emnekart = load_emnekart_from_json(JSON_PATH)
    pattern_parts = []
    for i, ch in enumerate(exam.subject):
        if ch != 'X':
            pattern_parts.append(re.escape(ch))
        else:
            if i == 3:
                pattern_parts.append('[AGT]')
            else:
                pattern_parts.append('[0-9]')
    regex = re.compile('^' + ''.join(pattern_parts) + '$')
    exam.matching_codes = [kode for kode in emnekart if regex.match(kode)]
    if exam.matching_codes:
        print(f"[DEEPSEEK] | Fant matchende emnekoder i JSON: {exam.matching_codes}")
    else:
        print(f"[DEEPSEEK] | Ingen emnekoder matchet mønsteret '{exam.subject}' i ntnu_emner.json")

    # 3) Fortsett med exam_version
    exam.exam_version = await prompttotext.async_prompt_to_text(
        f"{nonchalant} What exam edition is this exam? "
        f"Respond only with the singular formatted exam edition (e.g., Høst 2023). "
        f"S20XX means Sommer 20XX. "
        + ocr_text,
        max_tokens=1000,
        isNum=False,
        maxLen=12
    )
    print(f"[DEEPSEEK] | Exam version found: {exam.exam_version}")
    write_progress({4: exam.subject or ""})

    # 4) Hent total antall tasks
    exam.total_tasks = int(
        await prompttotext.async_prompt_to_text(
            f"{nonchalant} How many tasks are in this text? "
            f"Answer with a single number only. Here is the text: {ocr_text}",
            max_tokens=1000,
            isNum=True,
            maxLen=2
        )
    )
    print(f"[DEEPSEEK] | Number of tasks found: {exam.total_tasks}")
    write_progress({5: str(exam.total_tasks)})

    global total_tasks
    total_tasks = exam.total_tasks
    return exam


task_process_instructions = [
    {
        "instruction": (
            f"{nonchalant} What is task number {{task_number}}? "
            "Write only all text related directly to that one task from the raw text. "
            "Include the topic of the task and how many maximum points you can get. Do not solve the task: "
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
            f"{nonchalant} What is the topic of this task, potentially written in its title? Only reply with the topic, nothing else: "
        ),
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 100
    },
    {
        "instruction": (
            f"{nonchalant} Translate this task text from norwegian nynorsk or english to norwegian bokmål, do not change anything else. "
            "If it is already in norwegian bokmål respond with the exact same text: "
        ),
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 2000
    },
    {
        "instruction": (
            f"{nonchalant} Remove all text related to Inspera and exam administration. "
            "Also remove the task number, max points and title/topic of the task. "
            "Keep only what is necessary for solving the task: "
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

async def process_task(task_number: int, ocr_text: str, exam: Exam) -> Exam:
    task_exam = deepcopy(exam)

    while True:
        task_output = ocr_text
        points = None
        topic = None
        valid = 0

        for i, instr in enumerate(task_process_instructions):
            prompt = instr["instruction"].format(task_number=task_number) + task_output
            response = await prompttotext.async_prompt_to_text(
                prompt,
                max_tokens=instr["max_tokens"],
                isNum=instr["isNum"],
                maxLen=instr["maxLen"]
            )

            if i == 0:
                task_output = str(response)
            elif i == 1:
                points = int(response)
            elif i == 2:
                topic = str(response)
                print(f"\n\n\n TOPIC FOUND: {topic} \n\n\n")
                # Oppdater JSON med nytt tema
                try:
                    with JSON_PATH.open('r', encoding='utf-8') as jf:
                        json_data = json.load(jf)
                    for entry in json_data:
                        if entry.get("Emnekode", "").upper() in exam.matching_codes:
                            temas = entry.get("Temaer", [])
                            exists = any(
                                difflib.SequenceMatcher(None, t.lower(), topic.lower()).ratio() >= 0.9
                                for t in temas
                            )
                            if not exists:
                                temas.append(topic)
                                entry["Temaer"] = temas
                    with JSON_PATH.open('w', encoding='utf-8') as jf:
                        json.dump(json_data, jf, ensure_ascii=False, indent=4)
                    print(f"[DEEPSEEK] | Lagt til tema '{topic}' for emnekoder {exam.matching_codes}")
                except Exception as e:
                    print(f"[ERROR] Kunne ikke oppdatere temaer i JSON: {e}", file=sys.stderr)
            elif i < len(task_process_instructions) - 1:
                task_output = str(response)
            else:
                valid = int(response)

            task_status[task_number] = i + 1
            write_progress()
            print(f"\n\n\n\n{task_output}\n\n\n\n")

        # Bygg opp task_exam
        task_exam.task_number = task_number
        task_exam.task_text = task_output
        task_exam.points = points
        task_exam.topic = topic

        if valid == 0:
            print(f"[DEEPSEEK] [TASK {task_number:02d}] | Task not approved. Retrying...\n")
        else:
            print(f"[DEEPSEEK] [TASK {task_number:02d}] | Task approved.\n")
            return task_exam

async def main_async(ocr_text: str):
    exam_template = await get_exam_info(ocr_text)
    print(f"[DEEPSEEK] | Started processing all tasks")

    tasks = [
        asyncio.create_task(process_task(i, ocr_text, exam_template))
        for i in range(1, exam_template.total_tasks + 1)
    ]
    results = await asyncio.gather(*tasks)

    failed = [res.task_number for res in results if res.task_text is None]
    points = [res.points for res in results if res.task_text is not None]

    for idx, res in enumerate(results, start=1):
        if res.task_text is not None:
            print(f"Result for task {idx:02d}: {res.task_text}\n   (Points: {res.points})\n")

    print(f"[DEEPSEEK] | Failed tasks: {failed}")
    print(f"[DEEPSEEK] | Points for tasks: {points}")
    print(f"[DEEPSEEK] | Final total cost: {prompttotext.total_cost:.4f} USD")
    return results


def main(ocr_text: str):
    return asyncio.run(main_async(ocr_text))

if __name__ == "__main__":
    ocr_input = sys.stdin.read()
    main(ocr_input)
