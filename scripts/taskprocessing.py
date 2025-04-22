import prompttotext
import extractimages

import asyncio
import json
import sys
import re
import difflib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from copy import deepcopy
from collections import defaultdict
import json

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

# Paths and global state
db_dir = Path(__file__).resolve().parent
progress_file = db_dir / "progress.txt"
JSON_PATH = db_dir / "ntnu_emner.json"
task_status = defaultdict(lambda: 0)

# Prompt prefix
nonchalant = (
    "DO AS YOU ARE TOLD AND RESPOND ONLY WITH WHAT IS ASKED FROM YOU. "
    "DO NOT EXPLAIN OR SAY WHAT YOU ARE DOING. "
    "DO NOT WRITE ANY SYMBOLS LIKE - OR \n OR CHANGE LETTER FORMATTING WITH ** AND SIMILAR. "
    "YOU ARE USED IN A TEXT PROCESSING PYTHON PROGRAM SO THE TEXT SHOULD BE PLAIN. "
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

def get_topics(emnekode: str) -> str:
    """
    Return comma-separated unique 'Temaer' for matching emnekoder,
    or default list if fewer than 6 topics are found.
    """
    json_path = Path(__file__).resolve().parent / "ntnu_emner.json"

    with json_path.open('r', encoding='utf-8') as f:
        data = json.load(f)

    all_codes = [entry.get("Emnekode", "").upper() for entry in data]
    matches = difflib.get_close_matches(emnekode.upper(), all_codes, n=len(all_codes), cutoff=0.6)

    unike_temaer = set()

    for entry in data:
        if entry.get("Emnekode", "").upper() in matches:
            temaer = entry.get("Temaer", [])
            unike_temaer.update(map(str.strip, temaer))

    if len(unike_temaer) < 3:
        print("\n Fewer than 3 topics found in subject, reverting to default entries for reference.\n")
        return (
            "Partiell Derivasjon, Kritiske Punkt, Retningsderivert, Graf-Forståelse, Taylor 1D, "
            "Fourierrekke, Jevn og Odd Fourierrekke, PDE, Fouriertransformasjon, Konvolusjon, DFT, IDFT, "
            "Fagverk, Opplagerkrefter, Nullstaver, Strekk og Trykk i Fagverk, Arealtyngdepunkt, "
            "Arealmoment og Steiner, Statisk Bestemthet i Ramme, Reaksjonskrefter i Ramme, "
            "Normalkraftdiagram, Skjærkraftdiagram, Momentdiagram, Bøyespenning i Tverrsnitt, "
            "Tverrsnittdimensjonering, Deformasjonsmønster, Forskyvning og Rotasjon i Punkt, "
            "Pythonkodeanalyse for Nedbøyning"
        )

    print("\n Topics found in subject, using results as reference.\n")
    return ", ".join(sorted(unike_temaer))

def add_topics(topic: str, exam: Exam):
    """
    Adds a topic to the JSON file for matching subject codes if it doesn't already exist.
    """
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

def get_subject_code_variations(subject: str):
    data, emnekart = load_emnekart_from_json(JSON_PATH)
    pattern_parts = []
    for i, ch in enumerate(subject):
        if ch not in {'X', 'A', 'G', 'T'} and i < 3:
            pattern_parts.append(re.escape(ch))
        else:
            if i == 3:
                pattern_parts.append('[AGT]')
            else:
                pattern_parts.append('[0-9]')
    regex = re.compile('^' + ''.join(pattern_parts) + '$')
    matching_codes = [kode for kode in emnekart if regex.match(kode)]
    if matching_codes:
        print(f"[INFO] | Fant matchende emnekoder i JSON: {matching_codes}")
        return matching_codes
    else:
        print(f"[INFO] | Ingen matchende emnekoder i JSON.")

async def get_exam_info(ocr_text: str) -> Exam:
    exam = Exam()

    with open("subject.txt", "r", encoding="utf-8") as f:
                        first_line = f.readline().strip()
                        if len(first_line) > 4:
                            exam.subject = first_line.strip().upper()
                            print("\n\n\n TOPIC FOUND IN FILE:")
                        else:
                            exam.subject = (
                                await prompttotext.async_prompt_to_text(
                                    nonchalant +
                                    "What is the subject code for this exam? "
                                    "Respond only with the singular formatted subject code (e.g., IFYT1000). "
                                    "If there are variation in the last letter (e.g. IMAA, IMAG, IMAT), replace the variating letter with an X instead => IMAX. "
                                    "If there are variation in number(s), e.g 2002, 2012, 2022 - replace the variating number(s) with an X instead => 20X2. "
                                    + ocr_text,
                                    max_tokens=1000,
                                    isNum=False,
                                    maxLen=50
                                )
                            ).strip().upper()
                            print("\n\n\n TOPIC FOUND WITH DEEPSEEK:")

    print(exam.subject+"\n\n\n")
    exam.matching_codes = get_subject_code_variations(exam.subject)
    write_progress({4: exam.subject or ""})
    

    exam.exam_version = (
        await prompttotext.async_prompt_to_text(
            nonchalant +
            "What exam edition is this exam? "
            "Respond only with the singular formatted exam edition (e.g., Høst 2023). "
            "S20XX means Sommer 20XX. "
            + ocr_text,
            max_tokens=1000,
            isNum=False,
            maxLen=12
        )
    )
    print(f"[DEEPSEEK] | Exam version found: {exam.exam_version}")
    write_progress({5: exam.exam_version or ""})

    exam.total_tasks = int(
        await prompttotext.async_prompt_to_text(
            nonchalant +
            "How many tasks are in this text? "
            "Answer with a single number only. "
            + ocr_text,  
            max_tokens=1000,
            isNum=True,
            maxLen=2
        )
    )
    print(f"[DEEPSEEK] | Number of tasks found: {exam.total_tasks}")
    write_progress({6: str(exam.total_tasks)})

    global total_tasks
    total_tasks = exam.total_tasks

    pdf_dir = None
    with open("dir.txt", "r", encoding="utf-8") as dir_file:
        pdf_dir = dir_file.readline().strip()

    await extractimages.extract_images(pdf_dir, exam.subject, exam.exam_version)


    return exam


task_process_instructions = [
    {
        "instruction": (
            nonchalant +
            f"What is task number {{task_number}}? "
            "Write only all text related directly to that one task from the raw text. "
            "Include the topic of the task and how many maximum points you can get. Do not solve the task: "
        ),
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 2000
    },
    {
        "instruction": (
            nonchalant +
            "MAKE SURE YOU ONLY RESPOND WITH A NUMBER!!! "
            "How many points can you get for this task? Only reply with the number of points, nothing else: "
        ),
        "max_tokens": 1000,
        "isNum": True,
        "maxLen": 2
    },
    {
        "instruction": (
            nonchalant + 
            "Hva er temaet i denne oppgaven, potensielt skrevet i tittelen dens? Svar kun med temaet på norsk bokmål, ingenting annet. "
            "Ikke gå for spesifikt, hold deg til overordnede temaer logisk for kategorisering av eksamenssett. "
            "Ettersom dette er for eksamensoppgavekategorisering behøver jeg svar som er generelle og vil fås i flere ulike prompts. "
            "For eksempel Globalt Maksimum og Minimum bør generaliseres til Kritiske Punkt. Gjør passende slike antakelser for hva som er lurt for kategorisering. "
            "Temaer formatteres og kategoriseres noe slik, og dersom en av disse dekker oppgavens tema skal den brukes: "
        ),
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 100
    },
    {
        "instruction": (
            nonchalant + 
            "Translate this task text from norwegian nynorsk or english to norwegian bokmål, do not change anything else. "
            "If it is already in norwegian bokmål respond with the exact same text: "
        ),
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 2000
    },
    {
        "instruction": (
            nonchalant + 
            "Remove all text related to Inspera and exam administration. "
            "Also remove the task number, max points and title/topic of the task. "
            "Be careful to still include the information necessary for being able to solve the task: "
        ),
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 2000
    },
    {
        "instruction": (
            nonchalant + 
            "MAKE SURE YOU ONLY RESPOND WITH 0 OR 1!!! "
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
        task_output = str(ocr_text)
        task_exam.task_number = task_number
        valid = 0

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
                task_exam.points = int(
                    await prompttotext.async_prompt_to_text(
                        task_process_instructions[i]["instruction"] + task_output,
                        max_tokens=task_process_instructions[i]["max_tokens"],
                        isNum=task_process_instructions[i]["isNum"],
                        maxLen=task_process_instructions[i]["maxLen"]
                    )
                )

            # Hent tema og oppdater JSON
            elif i == 2:
                task_exam.topic = str(
                    await prompttotext.async_prompt_to_text(
                        task_process_instructions[i]["instruction"] + get_topics(exam.subject) + task_output,
                        max_tokens=task_process_instructions[i]["max_tokens"],
                        isNum=task_process_instructions[i]["isNum"],
                        maxLen=task_process_instructions[i]["maxLen"]
                    )
                )
                print(f"\n\n\n TOPIC FOUND: {task_exam.topic} \n\n\n")
                add_topics(task_exam.topic, exam)

            # Oppdatering av oppgavetekst for steg 3 og 4
            elif not i == len(task_process_instructions) - 1:
                task_output = str(
                    await prompttotext.async_prompt_to_text(
                        task_process_instructions[i]["instruction"] + task_output,
                        max_tokens=task_process_instructions[i]["max_tokens"],
                        isNum=task_process_instructions[i]["isNum"],
                        maxLen=task_process_instructions[i]["maxLen"]
                    )
                )

            # Validering av oppgaven (siste steg)
            else:
                valid = int(
                    await prompttotext.async_prompt_to_text(
                        task_process_instructions[i]["instruction"] + task_output,
                        max_tokens=task_process_instructions[i]["max_tokens"],
                        isNum=task_process_instructions[i]["isNum"],
                        maxLen=task_process_instructions[i]["maxLen"]
                    )
                )


            # Skriv ut midlertidig resultat og oppdater progress.txt
            if i != 1 and i != 2 and i != len(task_process_instructions) - 1:
                print("\n\n\n\n" + task_output + "\n\n\n\n")

            task_status[task_number] = i + 1
            write_progress()

        # Bygg opp task_exam
        task_exam.task_text = task_output

        if valid == 0:
            # print(f"[DEEPSEEK] [TASK {task_number:02d}] | Task not approved. Retrying...\n")
            print(f"[DEEPSEEK] [TASK {task_number:02d}] | Task not approved.\n")
            return task_exam
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
