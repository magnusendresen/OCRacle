import prompt_to_text
import extract_images
from project_config import *

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

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

# Paths and global state
JSON_PATH = EXAM_CODES_JSON
task_status = defaultdict(lambda: 0)

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
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
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

        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)

        for idx, text in updates.items():
            print(f"[STATUS] | Wrote '{text}' to line {idx + 1} in {PROGRESS_FILE}")
    except Exception as e:
        print(f"[ERROR] Could not update progress file: {e}")

def get_topics(emnekode: str) -> str:
    """
    Return comma-separated unique 'Temaer' for matching emnekoder,
    or default list if fewer than 6 topics are found.
    """
    json_path = EXAM_CODES_JSON

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
        print("\n Fewer than 3 topics found in subject, returning empty string.\n")
        return ""

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
        if ch == 'Y':
            pattern_parts.append(r'\d')  # ett valgfritt siffer
        else:
            pattern_parts.append(re.escape(ch))  # bokstavelig match

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

    with SUBJECT_FILE.open("r", encoding="utf-8") as f:
                        first_line = f.readline().strip()
                        if len(first_line) > 4:
                            exam.subject = first_line.strip().upper()
                            print("\n\n\n TOPIC FOUND IN FILE:")
                        else:
                            exam.subject = (
                                await prompt_to_text.async_prompt_to_text(
                                    PROMPT_CONFIG +
                                    "What is the subject code for this exam? "
                                    "Respond only with the singular formatted subject code (e.g., IFYT1000). "
                                    "If there are variation in the last letter (e.g. IMAA, IMAG, IMAT), replace the variating letter with an X instead => IMAX. "
                                    "If there are variation in number(s), e.g 2002, 2012, 2022 - replace the variating number(s) with an Y instead => 20Y2. "
                                    "Only replace a number with a letter if the subject code clearly has variations. "
                                    "Here is the text from the OCR: "
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
    
    pdf_dir = None
    with DIR_FILE.open("r", encoding="utf-8") as dir_file:
        pdf_dir = dir_file.readline().strip()

    exam.exam_version = (
        await prompt_to_text.async_prompt_to_text(
            PROMPT_CONFIG +
            "What exam edition is this exam? "
            "Respond only with the singular formatted exam edition written in norwegian. "
            "If the exam is in the spring or early summer, it should be titled Vår 20XX. "
            "If the exam is in the autumn or early winter, it should be titled Høst 20XX. "
            "If the exam is in the late summer or early autumn, it should be titled Kont 20XX. "
            "Of course 20XX is just an example here, write the actual year. "
            f"The title of the pdf is {pdf_dir} which might help you, or not. "
            "Make an educated guess from all the information above collectively. "
            + ocr_text,
            max_tokens=1000,
            isNum=False,
            maxLen=12
        )
    )
    print(f"[DEEPSEEK] | Exam version found: {exam.exam_version}")
    write_progress({5: exam.exam_version or ""})

    exam.total_tasks = (
        await prompt_to_text.async_prompt_to_text(
            PROMPT_CONFIG +
            "How many tasks are in this text? "
            "Respond with each task number separated by a comma. "
            # "If the subtasks are related in topic and need the answer to the previous subtask to be solved, respond with the main task number only (e.g. 1, 2, 5, 8, etc.). . "
            # "If the subtasks are unrelated (e.g. opplagerkrefter, nullstaver, stavkrefter) even if the same topic (e.g. fagverk), respond with each subtask by itself (e.g. 1a, 1b, 1c, 5a, 5b, etc.). "
            # "The exam may have a mixture of both types of tasks (e.g. 1, 2, 3a, 3b, 4, 5a, 5b, 6a, 6b, 7a, 7b, 8a, 8b, etc.). "
            # "There will under no circumstances be instances of both for the SAME task, e.g. 1, 1a, 1b, 2, 2a, 2b, etc. "
            "Only include the task number, do not account for subtasks, only the main task number. "
            "Do not include any symbols like ) or - or similar. "
            "Here is the text: "
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

    version_abbr = exam.exam_version[0].upper() + exam.exam_version[-2:]

    print("[INFO] | Set exam version abbreviation to: " + version_abbr)

    await extract_images.extract_images_with_tasks(
        pdf_path=pdf_dir,
        subject=exam.subject,
        version=version_abbr,
        output_folder=None,
    )


    return exam


task_process_instructions = [
    {
        "instruction": (
            PROMPT_CONFIG +
            f"What is task {{task_number}}? "
            "Write only all text that is required for solving that one TASK or SUBTASK from the raw text. "
            "If the task is a subtask (e.g. 1a), only include the text related to solving that subtask, not the full task, but be sure to have what is necessary for solving the task. "
            "Include the topic (if there is one in the title) of the task and how many maximum points you can get. "
            "Do not include the solution to the task. "
            "If the text is written in multiple languages, respond with the text in norwegian bokmål. "
        ),
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 2000
    },
    {
        "instruction": (
            PROMPT_CONFIG +
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
            PROMPT_CONFIG +
            "MAKE SURE YOU ONLY RESPOND WITH A NUMBER!!! "
            "How many points can you get for this task? Only reply with the number of points, nothing else: "
        ),
        "max_tokens": 1000,
        "isNum": True,
        "maxLen": 2
    },
    {
        "instruction": (
            PROMPT_CONFIG + 
            "Hva er temaet i denne oppgaven? Svar kun med temaet på norsk bokmål, ingenting annet. "
            "I noen tilfeller vil temaet stå i oppgavetittelen, men i andre tilfeller gjør den ikke det, og da må du gjøre et meget godt educated guess utifra instruksjonene nedenfor. "
            "Ikke gå for spesifikt, hold deg til overordnede temaer logisk for kategorisering av eksamenssett. "
            "Ettersom dette er for eksamensoppgavekategorisering behøver jeg svar som er generelle og vil fås i flere ulike prompts. "
            "For å unngå for mange og konkrete temaer gjøres forenklinger. Gjør passende slike antakelser for hva som er lurt for kategorisering. Her kommer noen eksempler: "
            "- Globalt Maksimum og Minimum => Kritiske Punkt. "
            "- Derivasjon => Derivasjon. "
            "- Partiell Derivasjon => Partiell Derivasjon. "
            "- Taylor 1D, Taylor 2D, Taylorrekke,  => Taylorrekker. "
            "- Oppgaver der energibevaring er viktig => Energibevaring. "
            "- Alt av bevegelsesmengde - med eller uten fjærer og friksjon => Bevegelsesmengde. "
            "- Oppgaver med rotasjon, treghetsmoment, vinkelhastighet, vinkelakselerasjon og/eller vinkelmoment => Rotasjonsmekanikk. "
            "- Oppgaver med friksjon, krefter og akselerasjon i skråplan og tau => Mekanikk. "
            "- Svingning med fjær eller pendel, med eller uten demping => Svingninger. "
            "- Hvis oppgaven handler om regning med matriser (matriseprodukt, invers, determinant, rang, etc.) => Matriseregning. "
            "- Hvis oppgaven handler om vektorer, vektorprodukt, skalarprodukt, projeksjon, vektorrom, etc. => Vektorregning. "
            "- Osv. Osv. Osv. "
            "Hvis det finnes en referanse for relevante temaer for emnet, vil den stå under. Bruk referansen som støtte for å velge passende tema, men ikke nødvendigvis spesifikt for temaet hvis det virker feil. "
            "Hvis det ikke finnes en referanse, gjør en god vurdering basert på oppgaveteksten og forklaringen over. Målet er å få det samme resultatet ved ulike eksamenssett. "
            "Svar kun med temaet på norsk bokmål, ingenting annet. "
            "Her kommer den eventuelle referansen, samt teksten til oppgaven: "
        ),
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 100
    },
    {
        "instruction": (
            PROMPT_CONFIG + 
            "Translate this task text from norwegian nynorsk or english to norwegian bokmål, do not change anything else. "
            "If it is already in norwegian bokmål respond with the exact same text. "
            "Here is the text: "
        ),
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 2000
    },
    {
        "instruction": (
            PROMPT_CONFIG + 
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
            "Be sure to still include ALL the information necessary for being able to solve the task, such as the main question itself. "
            "Do not include the solution to the task, only the task text itself. "
        ),
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 2000
    },
    {
        "instruction": (
            PROMPT_CONFIG +
            "Format this exam task as a valid HTML string for use in a JavaScript variable. "
            "Use <p>...</p> for all text paragraphs. "
            "Use <h3>a)</h3>, <h3>b)</h3> etc for subtask labels if present. "
            "Use MathJax-compatible LaTeX. "
            "Wrap display math in $$...$$. "
            "Wrap inline math in $...$. "
            "Use a single backslash for LaTeX commands (e.g., \\frac, \\sqrt). "
            "Do not use \\( ... \\) or \\[ ... \\]. "
            "Do not double-escape backslashes. "
            "Do not explain, summarize, or add anything outside the HTML. "
            "Output must be usable directly inside const oppgaveTekst = `<the content here>`. "
            "Do not add any other text or explanation. "
            "Do not add any HTML tags outside the <p>...</p> and <h3>...</h3> tags. "
            "Make sure that e.g. infty, omega, theta, etc. are properly formatted. "
            "Do not write the result as you would write in a programming box, but as you would write it as clean text. "
            "Do not include ```html or const oppgaveTekst = `` or similar. "
            "You are allowed to make som assumptions about OCR artifacts in the text, such as \\sqrt{\\sqrt{\\sqrt most likely being an error for a single square root. "
            "Be sure to include spaces and newlines where appropriate. "
            "Just write the task in plaintext in the format described above. "
            "Here is the task text: "
        ),
        "max_tokens": 1000,
        "isNum": False,
        "maxLen": 2000
    },
    {
        "instruction": (
            PROMPT_CONFIG + 
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
                    await prompt_to_text.async_prompt_to_text(
                        task_process_instructions[i]["instruction"].format(task_number=task_number) + task_output,
                        max_tokens=task_process_instructions[i]["max_tokens"],
                        isNum=task_process_instructions[i]["isNum"],
                        maxLen=task_process_instructions[i]["maxLen"]
                    )
                )

            # Image extraction
            elif i == 1:
                images = int(
                    await prompt_to_text.async_prompt_to_text(
                        task_process_instructions[i]["instruction"] + task_output,
                        max_tokens=task_process_instructions[i]["max_tokens"],
                        isNum=task_process_instructions[i]["isNum"],
                        maxLen=task_process_instructions[i]["maxLen"]
                    )
                )
                if images > 0:
                    print(f"[DEEPSEEK] | Images were found in task {task_number}.")
                    task_dir = IMG_DIR / task_exam.subject / task_exam.exam_version / task_number
                    if task_dir.exists():
                        found_images = sorted(task_dir.glob("*.png"))
                        task_exam.images = [str(img.relative_to(PROJECT_ROOT)) for img in found_images]
                    else:
                        task_exam.images = []
                    print(f"[DEEPSEEK] | Found {len(task_exam.images)} images for task {task_number}.")
                else:
                    print(f"[DEEPSEEK] | No images were found in task {task_number}.")
                    task_exam.images = []

            # Points extraction
            elif i == 2:
                points_str = await prompt_to_text.async_prompt_to_text(
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
                    await prompt_to_text.async_prompt_to_text(
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
                    await prompt_to_text.async_prompt_to_text(
                        task_process_instructions[i]["instruction"] + task_output,
                        max_tokens=task_process_instructions[i]["max_tokens"],
                        isNum=task_process_instructions[i]["isNum"],
                        maxLen=task_process_instructions[i]["maxLen"]
                    )
                )

            # Validation step
            else:
                valid = int(
                    await prompt_to_text.async_prompt_to_text(
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

    # Bilder beholdes for fremtidig bruk og slettes ikke automatisk

    for res in results:
        if res.task_text is not None:
            print(f"Result for task {res.task_number}: {res.task_text}\n   (Points: {res.points})\n")

    print(f"[DEEPSEEK] | Failed tasks: {failed}")
    print(f"[DEEPSEEK] | Points for tasks: {points}")
    print(f"[DEEPSEEK] | Final total cost: {prompt_to_text.total_cost:.4f} USD")
    return results


def main(ocr_text: str):
    return asyncio.run(main_async(ocr_text))

if __name__ == "__main__":
    ocr_input = sys.stdin.read()
    main(ocr_input)