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
IMG_PATH = db_dir / "img"
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
    task_number: Optional[str] = None
    points: Optional[int] = None
    task_text: Optional[str] = None
    images: List[str] = field(default_factory=list)
    code: Optional[str] = None
    total_tasks: List[str] = field(default_factory=list)


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
            status_str = ''.join(str(task_status[t]) for t in total_tasks)
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

import re

def get_subject_code_variations(subject: str):
    data, emnekart = load_emnekart_from_json(JSON_PATH)
    pattern_parts = []
    for ch in subject:
        if ch == 'X':
            # Tillat både bokstaver A, G, T og tall for X
            pattern_parts.append('[AGT0-9]')
        else:
            # Escapet for sikkerhets skyld
            pattern_parts.append(re.escape(ch))
    regex = re.compile('^' + ''.join(pattern_parts) + '$')
    matching_codes = [kode for kode in emnekart if regex.match(kode)]
    if matching_codes:
        print(f"[INFO] | Fant matchende emnekoder i JSON: {matching_codes}")
        return matching_codes
    else:
        print(f"[INFO] | Ingen matchende emnekoder i JSON.")
        return []

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

    exam.total_tasks = (
        await prompttotext.async_prompt_to_text(
            nonchalant +
            "How many tasks are in this text? "
            "Respond with each task number separated by a comma. "
            "If the subtasks are related in topic and need the answer to the previous subtask to be solved, respond with the main task number only (e.g. 1, 2, 5, 8, etc.). . "
            "If the subtasks are unrelated (e.g. opplagerkrefter, nullstaver, stavkrefter) even if the same topic (e.g. fagverk), respond with each subtask by itself (e.g. 1a, 1b, 1c, 5a, 5b, etc.). "
            "The exam may have a mixture of both types of tasks (e.g. 1, 2, 3a, 3b, 4, 5a, 5b, 6a, 6b, 7a, 7b, 8a, 8b, etc.). "
            "Do not include any symbols like ) or - or similar. "
            + ocr_text,  
            max_tokens=1000,
            isNum=False,
            maxLen=250
        )
    )
    exam.total_tasks = [task.strip() for task in exam.total_tasks.split(",")]
    print(f"[DEEPSEEK] | Tasks found for processing: {exam.total_tasks}")
    write_progress({6: str(exam.total_tasks)})

    global total_tasks
    total_tasks = exam.total_tasks

    pdf_dir = None
    with open("dir.txt", "r", encoding="utf-8") as dir_file:
        pdf_dir = dir_file.readline().strip()

    await extractimages.extract_images(
        pdf_path=pdf_dir,
        subject=exam.subject,
        version=exam.exam_version,
        total_tasks=exam.total_tasks,
        full_text=ocr_text,
        output_folder=None
    )

    return exam


task_process_instructions = [
    {
        "instruction": (
            nonchalant +
            f"What is task number {{task_number}}? "
            "Write only all text related directly to that one TASK or SUBTASK from the raw text. "
            "Include the topic of the task and how many maximum points you can get. Do not solve the task: "
            "Do not include the solution to the task. "
            "If the text is written in multiple languages, respond with the text in norwegian. "
        ),
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 2000
    },
    {
        "instruction": (
            nonchalant +
            "MAKE SURE YOU ONLY RESPOND WITH 0 OR 1!!! "
            "Does this task likely contain any images or figures that are relevant for solving the task? "
            "Respond with 1 if you think there are images, 0 if not. "
            "Only reply with 0 or 1, nothing else. "
        ),
        "max_tokens": 1000,
        "isNum": True,
        "maxLen": 2
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
            "This includes information about the exam, such as: "
            "- Denne oppgaven skal besvares i Inspera. Du skal ikke legge ved utregninger på papir. "
            "- Skriv enten 1, 2, eller 3 i svarfeltet. "
            "- Skriv bare én av bokstavene A, B, C, D, E i hvert felt under. "
            "- Skriv ditt svar her, eller bruk scantronark. "
            "- Denne oppgaven skal besvares i tekstboksen under, eller ved bruk av scantronark. "
            "- Du kan skrive svaret i boksen under, eller skrive på Scantronark som leveres for innskanning. "
            "- Vi anbefaler bruk av Scantron-ark. "
            "- Nederst i oppgaven finner du en sjusifret kode. Fyll inn denne koden øverst til venstre på arkene du ønsker å levere. "
            "- Etter eksamen finner du besvarelsen din i arkivet i Inspera. "
            "- Varslinger vil bli gitt via Inspera. "
            "- Kontaktinformasjon til faglærer under eksamen. "
            "- Hjelpemiddelkoder og kalkulatorliste. "
            "- Eksamensdato og klokkeslett. "
            "Also remove the task number (1, Oppgave 1, 1a, a), etc.), max points and title/topic of the task. "
            "Be careful to still include the information necessary for being able to solve the task, such as the main question itself. "
        ),
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 2000
    },
    {
        "instruction": (
            nonchalant +
            "Format this exam task as a valid HTML string for use in a JavaScript variable. "
            "Use <p>...</p> for all text paragraphs. "
            "Use <h3>a)</h3>, <h3>b)</h3> etc for subtask labels if present. "
            "Use MathJax LaTeX. "
            "Wrap display math in $$...$$. "
            "Wrap inline math in $...$. "
            "Do not use \\( ... \\) or \\[ ... \\]. "
            "Escape all LaTeX backslashes with double backslashes. "
            "Do not explain summarize or add anything outside the HTML. "
            "Output must be usable directly inside const oppgaveTekst = `<the content here>`. "
            "Do not add any other text or explanation. "
            "Do not add any HTML tags outside the <p>...</p> and <h3>...</h3> tags. "
            "Make sure that e.g. infty, omega, theta, etc. are properly formatted."
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

async def process_task(task_number: str, ocr_text: str, exam: Exam) -> Exam:
    task_exam = deepcopy(exam)
    task_exam.task_number = task_number
    task_exam.exam_version = exam.exam_version

    while True:
        task_output = str(ocr_text)
        valid = 0
        images = 0

        for i in range(len(task_process_instructions)):

            # Initial extraction of task text
            if i == 0:
                task_output = str(
                    await prompttotext.async_prompt_to_text(
                        task_process_instructions[i]["instruction"].format(task_number=task_number) + task_output,
                        max_tokens=task_process_instructions[i]["max_tokens"],
                        isNum=task_process_instructions[i]["isNum"],
                        maxLen=task_process_instructions[i]["maxLen"]
                    )
                )

            # Image extraction
            elif i == 1:
                images = int(
                    await prompttotext.async_prompt_to_text(
                        task_process_instructions[i]["instruction"] + task_output,
                        max_tokens=task_process_instructions[i]["max_tokens"],
                        isNum=task_process_instructions[i]["isNum"],
                        maxLen=task_process_instructions[i]["maxLen"]
                    )
                )
                if images > 0:
                    print(f"[DEEPSEEK] | Images were found in task {task_number}.")
                    EXAM_IMG_PATH = IMG_PATH / f"{task_exam.subject}_{task_exam.exam_version}_images"
                    # Finn alle bilder som matcher patternet for denne oppgaven
                    pattern = f"{task_exam.subject}_{task_exam.exam_version}_{task_number}_*.png"
                    found_images = sorted(EXAM_IMG_PATH.glob(pattern))
                    task_exam.images = [str(img) for img in found_images]
                    print(f"[DEEPSEEK] | Found {len(task_exam.images)} images for task {task_number}.")
                else:
                    print(f"[DEEPSEEK] | No images were found in task {task_number}.")
                    task_exam.images = []

            # Points extraction
            elif i == 2:
                points_str = await prompttotext.async_prompt_to_text(
                    task_process_instructions[i]["instruction"] + task_output,
                    max_tokens=task_process_instructions[i]["max_tokens"],
                    isNum=task_process_instructions[i]["isNum"],
                    maxLen=task_process_instructions[i]["maxLen"]
                )
                try:
                    task_exam.points = int(points_str) if points_str is not None else None
                except (TypeError, ValueError):
                    task_exam.points = None

            # Topic extraction
            elif i == 3:
                task_exam.topic = str(
                    await prompttotext.async_prompt_to_text(
                        task_process_instructions[i]["instruction"] + get_topics(exam.subject) + task_output,
                        max_tokens=task_process_instructions[i]["max_tokens"],
                        isNum=task_process_instructions[i]["isNum"],
                        maxLen=task_process_instructions[i]["maxLen"]
                    )
                )
                print(f"[DEEPSEEK] | Topic found for task {task_number}: {task_exam.topic}")
                add_topics(task_exam.topic, exam)

            # Update task_output for middle steps
            elif not i == len(task_process_instructions) - 1:
                task_output = str(
                    await prompttotext.async_prompt_to_text(
                        task_process_instructions[i]["instruction"] + task_output,
                        max_tokens=task_process_instructions[i]["max_tokens"],
                        isNum=task_process_instructions[i]["isNum"],
                        maxLen=task_process_instructions[i]["maxLen"]
                    )
                )

            # Validation step
            else:
                valid = int(
                    await prompttotext.async_prompt_to_text(
                        task_process_instructions[i]["instruction"] + task_output,
                        max_tokens=task_process_instructions[i]["max_tokens"],
                        isNum=task_process_instructions[i]["isNum"],
                        maxLen=task_process_instructions[i]["maxLen"]
                    )
                )

            # Print intermediate result with task identifier
            if i not in (1, 2, len(task_process_instructions) - 1):
                print(f"\n\n\nOppgave {task_number}:\n{task_output}\n\n\n\n")

            task_status[task_number] = i + 1
            write_progress()

        task_exam.task_text = task_output

        if valid == 0:
            print(f"[DEEPSEEK] [TASK {task_number}] | Task not approved.\n")
            return task_exam
        else:
            print(f"[DEEPSEEK] [TASK {task_number}] | Task approved.\n")
            return task_exam

async def main_async(ocr_text: str):
    exam_template = await get_exam_info(ocr_text)
    print(f"[DEEPSEEK] | Started processing all tasks")

    # Iterate through string identifiers
    tasks = [
        asyncio.create_task(process_task(task, ocr_text, exam_template))
        for task in exam_template.total_tasks
    ]
    results = await asyncio.gather(*tasks)

    failed = [res.task_number for res in results if res.task_text is None]
    points = [res.points for res in results if res.task_text is not None]

    # Slett alle bilder i IMG_PATH som ikke er knyttet til noen oppgave
    used_images = set()
    for res in results:
        if res.images:
            used_images.update(res.images)

    for img_file in IMG_PATH.glob("*.png"):
        if str(img_file) not in used_images:
            try:
                img_file.unlink()
                print(f"[CLEANUP] | Deleted unused image: {img_file}")
            except Exception as e:
                print(f"[CLEANUP ERROR] | Could not delete {img_file}: {e}")

    for res in results:
        if res.task_text is not None:
            print(f"Result for task {res.task_number}: {res.task_text}\n   (Points: {res.points})\n")

    print(f"[DEEPSEEK] | Failed tasks: {failed}")
    print(f"[DEEPSEEK] | Points for tasks: {points}")
    print(f"[DEEPSEEK] | Final total cost: {prompttotext.total_cost:.4f} USD")
    return results


def main(ocr_text: str):
    return asyncio.run(main_async(ocr_text))

if __name__ == "__main__":
    ocr_input = sys.stdin.read()
    main(ocr_input)