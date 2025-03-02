import os
import time
import asyncio
import contextvars
from openai import OpenAI  # Using OpenAI SDK for DeepSeek

# Context variables for task-ID og processing step
current_task = contextvars.ContextVar("current_task", default="")
current_step = contextvars.ContextVar("current_step", default="")

# Hent API-nøkkel fra miljøvariabler
api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise ValueError("API key not found in environment variables.")

# Initialiser DeepSeek-klienten
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# Prisestimater for API-kall
usd_per_1m_input_tokens = 0.27
usd_per_1m_output_tokens = 1.10

MODEL_NAME = "deepseek-chat"
total_cost = 0  # Global variabel for akkumulert kostnad

print("[DEEPSEEK] Successfully connected to DeepSeekAPI!\n")

def prompt_to_text(prompt, max_tokens=1000):
    """Synkron funksjon som sender API-kall, beregner tokenbruk og kostnad.
    Den prøver uendelig til den får et gyldig svar.
    """
    global total_cost
    # Hent task-ID og processing step fra context
    task_id = current_task.get()
    step = current_step.get()
    if task_id and step:
        prefix = f"[DEEPSEEK] [TASK {task_id}] | {step}, "
    elif task_id:
        prefix = f"[DEEPSEEK] [TASK {task_id}] | "
    else:
        prefix = "[DEEPSEEK] | "

    attempt = 0
    while True:
        attempt += 1
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                stream=False
            )
            if response.choices:
                result_text = response.choices[0].message.content.strip()
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens

                request_cost = (input_tokens * usd_per_1m_input_tokens +
                                output_tokens * usd_per_1m_output_tokens) / 1e6
                total_cost += request_cost

                print(f"{prefix}Tokens in: {input_tokens:02d}, Tokens out: {output_tokens:02d}")
                return result_text

            print(f"{prefix}[ERROR] Invalid response. Retrying...")
        except:
            print(f"{prefix}[ERROR] Request failed. Retrying...")
            time.sleep(2)

async def async_prompt_to_text(prompt, max_tokens=1000):
    """Asynkron wrapper for prompt_to_text, med propagasjon av context variable."""
    ctx = contextvars.copy_context()
    return await asyncio.to_thread(ctx.run, prompt_to_text, prompt, max_tokens)

async def get_amount(ocr_text):
    """
    Henter antallet oppgaver fra OCR-teksten.
    """
    nonchalant = "Do not explain what you are doing, just do it."
    while True:
        response = await async_prompt_to_text(
            f"{nonchalant} How many tasks are in this text? Answer with a single number only: {ocr_text}",
            max_tokens=1000
        )
        if not response.strip().isdigit() or len(response.strip()) > 2:
            print("[DEEPSEEK] | [ERROR] Invalid integer, retrying...")
            continue
        try:
            return int(response.strip())
        except ValueError:
            print("[DEEPSEEK] | [ERROR] Unable to convert response to int, retrying...")
            continue

async def process_task(task_number, ocr_text):
    """
    Prosesserer én oppgave gjennom 3 steg:
      1. Ekstraher oppgavetekst.
      2. Fjern irrelevant tekst.
      3. Valider oppgaven.
      
    Ved restart logges forsøksnummer. Det vil forsøkes uendelig til et gyldig svar mottas.
    """
    # Sett tasknummer med to sifre i context variable
    current_task.set(f"{task_number:02d}")
    nonchalant = "Do not explain what you are doing, just do it."
    attempt = 0
    while True:
        attempt += 1
        if attempt > 1:
            print(f"[DEEPSEEK] [TASK {current_task.get()}] | Restarting, attempt {attempt:02d}")
        # Step 1: Ekstraher oppgavetekst (ingen individuell logging her)
        current_step.set("Step 1/3")
        task_output = await async_prompt_to_text(
            f"{nonchalant} What is task {current_task.get()}? Write all text related to the task directly from the raw text, do not solve the task. {ocr_text}",
            max_tokens=1000
        )
        # Step 2: Fjern irrelevant tekst
        current_step.set("Step 2/3")
        task_output = await async_prompt_to_text(
            f"{nonchalant} Remove all text related to Inspera and exam administration, keep only what is necessary for solving the task: {task_output}",
            max_tokens=1000
        )
        # Step 3: Valider oppgaven
        current_step.set("Step 3/3")
        valid_response = await async_prompt_to_text(
            f"{nonchalant} MAKE SURE YOU ONLY RESPOND WITH 0 OR 1!!! Answer 1 if this is a valid task, otherwise 0: {task_output}",
            max_tokens=1000
        )
        if valid_response not in ["0", "1"]:
            print(f"[DEEPSEEK] [TASK {current_task.get()}] | [ERROR] Invalid response. Retrying...")
            continue
        if valid_response == "0":
            print(f"[DEEPSEEK] [TASK {current_task.get()}] | [WARNING] Task not approved. Retrying task...")
            continue
        elif valid_response == "1":
            print(f"[DEEPSEEK] [TASK {current_task.get()}] | Task approved")
            return task_output

async def main_async(ocr_text):
    """
    Asynkron hovedfunksjon som prosesserer et antall oppgaver parallelt.
    """
    amount = await get_amount(ocr_text)
    print(f"[DEEPSEEK] Number of tasks found: {amount}\n")
    print(f"[DEEPSEEK] Started Step 1 for all tasks")
    tasks = [asyncio.create_task(process_task(i, ocr_text)) for i in range(1, amount + 1)]
    results = await asyncio.gather(*tasks)
    for i, result in enumerate(results, start=1):
        print(f"Result for task {i:02d}: {result}\n")
    print(f"[DEEPSEEK] Final total cost: {total_cost:.4f} USD")
    return results

def main(ocr_text):
    """
    Synkron wrapper for den asynkrone hovedfunksjonen. Importeres og kalles fra et annet skript.
    """
    return asyncio.run(main_async(ocr_text))
