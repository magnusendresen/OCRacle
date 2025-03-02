import asyncio
import prompttotext
from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class TaskResult:
    eksamen: Optional[str] = None
    oppgave: Optional[int] = None
    tema: Optional[str] = None
    tekst: Optional[str] = None
    maksPoeng: Optional[int] = None
    bilder: List[str] = field(default_factory=list)
    kode: Optional[str] = None

    def __str__(self):
        return f"Oppgave {self.oppgave}: {self.tekst} (Maks poeng: {self.maksPoeng})"

async def get_amount(ocr_text):
    """
    Henter antallet oppgaver fra OCR-teksten.
    Forventet svar er numerisk (isNum=True) og konverteres i prompt_to_text.
    """
    nonchalant = "Do not explain what you are doing, just do it."
    response = await prompttotext.async_prompt_to_text(
        f"{nonchalant} How many tasks are in this text? Answer with a single number only: {ocr_text}",
        max_tokens=1000,
        isNum=True
    )
    return response

async def process_task(task_number, ocr_text):
    """
    Prosesserer én oppgave gjennom 4 steg:
      1. Ekstraher oppgavetekst.
      2. Finn ut hvor mange maks poeng oppgaven har.
      3. Fjern irrelevant tekst.
      4. Valider oppgaven.
      
    Hvis et hvilket som helst steg feiler (dvs. prompttotext returnerer None),
    avsluttes prosesseringen for denne oppgaven, og funksjonen returnerer et TaskResult
    med kun oppgavenummer satt (dette legges til i listen med feilede oppgaver).
    Dersom valid_response (Step 4) ikke er lik 1, prøves hele oppgaven på nytt.
    """
    prompttotext.current_task.set(f"{task_number:02d}")
    nonchalant = "Do not explain what you are doing, just do it."
    
    while True:
        # Step 1: Ekstraher oppgavetekst (forvent tekst, isNum=False)
        prompttotext.current_step.set("Step 1")
        task_output = await prompttotext.async_prompt_to_text(
            f"{nonchalant} What is task {prompttotext.current_task.get()}? Write all text related to the task directly from the raw text. Include how many maximum points you can get. Do not solve the task. {ocr_text}",
            max_tokens=1000,
            isNum=False
        )
        if task_output is None:
            print(f"[DEEPSEEK] [TASK {prompttotext.current_task.get()}] | FAILED at Step 1. Skipping task.")
            return TaskResult(oppgave=task_number)
        
        # Step 2: Finn ut hvor mange maks poeng (forvent numerisk svar, isNum=True)
        prompttotext.current_step.set("Step 2")
        point = await prompttotext.async_prompt_to_text(
            f"{nonchalant} MAKE SURE YOU ONLY RESPOND WITH A NUMBER!!! How many points can you get for task {prompttotext.current_task.get()}? Only reply with the number of points, nothing else. {task_output}",
            max_tokens=1000,
            isNum=True
        )
        if point is None:
            print(f"[DEEPSEEK] [TASK {prompttotext.current_task.get()}] | FAILED at Step 2. Skipping task.")
            return TaskResult(oppgave=task_number)
        
        # Step 3: Fjern irrelevant tekst (forvent tekst, isNum=False)
        prompttotext.current_step.set("Step 3")
        task_output_clean = await prompttotext.async_prompt_to_text(
            f"{nonchalant} Remove all text related to Inspera and exam administration, keep only what is necessary for solving the task: {task_output}",
            max_tokens=1000,
            isNum=False
        )
        if task_output_clean is None:
            print(f"[DEEPSEEK] [TASK {prompttotext.current_task.get()}] | FAILED at Step 3. Skipping task.")
            return TaskResult(oppgave=task_number)
        task_output = task_output_clean
        
        # Step 4: Valider oppgaven (forvent numerisk svar, isNum=True)
        prompttotext.current_step.set("Step 4")
        valid_response = await prompttotext.async_prompt_to_text(
            f"{nonchalant} MAKE SURE YOU ONLY RESPOND WITH 0 OR 1!!! Answer 1 if this is a valid task, otherwise 0: {task_output}",
            max_tokens=1000,
            isNum=True
        )
        if valid_response is None:
            print(f"[DEEPSEEK] [TASK {prompttotext.current_task.get()}] | FAILED at Step 4. Skipping task.")
            return TaskResult(oppgave=task_number)
        if valid_response == 0:
            print(f"[DEEPSEEK] [TASK {prompttotext.current_task.get()}] | Task not approved. Retrying task.")
            continue  # Prøver hele oppgaven på nytt dersom den ikke blir godkjent.
        elif valid_response == 1:
            print(f"[DEEPSEEK] [TASK {prompttotext.current_task.get()}] | Task approved.")
            return TaskResult(oppgave=task_number, tekst=task_output, maksPoeng=point)

async def main_async(ocr_text):
    """
    Asynkron hovedfunksjon som prosesserer et antall oppgaver parallelt.
    """
    amount = await get_amount(ocr_text)
    print(f"[DEEPSEEK] Number of tasks found: {amount}\n")
    print(f"[DEEPSEEK] Started Step 1 for all tasks")
    tasks = [asyncio.create_task(process_task(i, ocr_text)) for i in range(1, amount + 1)]
    results = await asyncio.gather(*tasks)
    
    # Lag en liste med oppgavenumre for de oppgavene som feilet (hvor tekst er None)
    failed_tasks = [res.oppgave for res in results if res.tekst is None]
    # Lag en liste med poeng for de oppgavene som ble behandlet
    points = [res.maksPoeng for res in results if res.tekst is not None]
    
    for res in results:
        if res.tekst is not None:
            print(f"Result for task {res.oppgave:02d}: {res.tekst}  (Points: {res.maksPoeng})\n")
    print(f"[DEEPSEEK] Failed tasks: {failed_tasks}")
    print(f"[DEEPSEEK] Points for tasks: {points}")
    print(f"[DEEPSEEK] Final total cost: {prompttotext.total_cost:.4f} USD")
    return results

def main(ocr_text):
    """
    Synkron wrapper for den asynkrone hovedfunksjonen.
    Importeres og kalles fra et annet skript.
    """
    return asyncio.run(main_async(ocr_text))
