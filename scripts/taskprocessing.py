import asyncio
from dataclasses import dataclass, field
from typing import Optional, List
from copy import deepcopy

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
    """
    Henter informasjon fra eksamens-OCR.
    Returnerer et exam-objekt som fungerer som mal for alle oppgaver,
    med subject, version og antall oppgaver (amount) satt.
    """
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
        f"{nonchalant} What exam edition is this exam? Respond only with the singular formatted exam edition (e.g., Høst 2023, Vår 2022). S20XX means Sommer 20XX. {ocr_text}",
        max_tokens=1000,
        isNum=False,
        maxLen=12
    )
    print(f"[DEEPSEEK] | Exam version found: {exam.version}\n")

    exam.amount = await prompttotext.async_prompt_to_text(
        f"{nonchalant} How many tasks are in this text? Answer with a single number only: {ocr_text}",
        max_tokens=1000,
        isNum=True,
        maxLen=2
    )
    print(f"[DEEPSEEK] | Number of tasks found: {exam.amount}\n")

    return exam

async def process_task(task_number, ocr_text, exam):
    """
    Prosesserer én oppgave gjennom 4 steg:
      1. Ekstraher oppgavetekst.
      2. Finn ut hvor mange maks poeng oppgaven har.
      3. Fjern irrelevant tekst.
      4. Valider oppgaven.
      
    Hvis et steg (unntatt validering) feiler (prompttotext returnerer None), markeres oppgaven som feilet
    ved å returnere et Exam med kun task satt.
    Dersom valideringen (Step 4) ikke gir 1, prøves oppgaven på nytt.
    Returnerer et Exam med gyldig data når oppgaven er godkjent.
    """
    prompttotext.current_task.set(f"{task_number:02d}")
    nonchalant = "Do not explain what you are doing, just do it."
    
    # Lag en kopi av exam-objektet for denne oppgaven slik at vi bruker et unikt objekt for hver task.
    task = deepcopy(exam)
    task.task = task_number
    
    while True:
        # Step 1: Ekstraher oppgavetekst (tekst, isNum=False)
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
        
        # Step 2: Finn ut hvor mange maks poeng (numerisk, isNum=True)
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
        
        # Step 3: Fjern irrelevant tekst (tekst, isNum=False)
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
        
        # Step 4: Valider oppgaven (numerisk, isNum=True)
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

async def main_async(ocr_text):
    """
    Asynkron hovedfunksjon som prosesserer et antall oppgaver parallelt.
    """
    exam_template = await get_exam_info(ocr_text)
    print(f"[DEEPSEEK] | Started processing all tasks")
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
    """
    Synkron wrapper for den asynkrone hovedfunksjonen.
    Importeres og kalles fra et annet skript.
    """
    return asyncio.run(main_async(ocr_text))
