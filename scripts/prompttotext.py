import os
import time
import asyncio
import contextvars
from openai import OpenAI  # Using OpenAI SDK for DeepSeek
import builtins
from project_paths import PROJECT_ROOT

# Definer sti for progress.txt
progress_file = PROJECT_ROOT / "progress.txt"

def update_progress_line3(value="1"):
    """
    Oppdaterer kun linje 3 i progress.txt med den angitte verdien.
    """
    try:
        if progress_file.exists():
            with open(progress_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        else:
            lines = []
        if len(lines) < 3:
            lines += ["\n"] * (3 - len(lines))
        # Linje 3 er indeks 2
        lines[2] = f"{value}\n"
        with open(progress_file, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"[STATUS] | Updated line 3 of {progress_file} with '{value}'")
    except Exception as e:
        print(f"[ERROR] Could not update line 3 in {progress_file}: {e}")

# Context variables for task-ID og processing step
current_task = contextvars.ContextVar("current_task", default="")
current_step = contextvars.ContextVar("current_step", default="")

# Hent API-nøkkel og initialiser DeepSeek-klienten
api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise ValueError("API key not found in environment variables.")

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# Prisestimater
usd_per_1m_input_tokens = 0.27
usd_per_1m_output_tokens = 1.10

MODEL_NAME = "deepseek-chat"
total_cost = 0  # Global variabel for akkumulert kostnad

print("[DEEPSEEK] Successfully connected to DeepSeekAPI!\n")
# Oppdaterer progress.txt linje 3 med "1" når DeepSeek er kobla til.
update_progress_line3("1")

def isNumber(a):
    return a.strip().isnumeric()

def isType(a, b):
    return type(a) == b

def prompt_to_text(prompt, max_tokens=1000, isNum=True, maxLen=None):
    """
    Synkron funksjon som sender API-kall, beregner tokenbruk og kostnad.
    Prøver opp til 3 ganger til et gyldig svar mottas.
    Dersom isNum er True, sjekkes det at svaret er numerisk og konverteres til int.
    Dersom maxLen er angitt og lengden på resultatet (etter strip) overstiger denne,
    skrives "Exceeded max letters" og loopen fortsetter.
    Returnerer None dersom prompten feiler etter 3 forsøk.
    """
    global total_cost
    task_id = current_task.get()
    step = current_step.get()
    if task_id and step:
        prefix = f"[DEEPSEEK] [TASK {task_id}] | {step}, "
    elif task_id:
        prefix = f"[DEEPSEEK] [TASK {task_id}] | "
    else:
        prefix = "[DEEPSEEK] | "
    
    max_attempts = 3
    attempt = 0
    while attempt < max_attempts:
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
                if maxLen is not None and len(result_text) > maxLen:
                    print(f"{prefix}[ERROR] Exceeded max letters. (attempt {attempt}/{max_attempts})")
                    continue
                if isNum:
                    if not isNumber(result_text):
                        print(f"{prefix}[ERROR] Expected numeric result. (attempt {attempt}/{max_attempts})")
                        continue
                    result_text = int(result_text)
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
                request_cost = (input_tokens * usd_per_1m_input_tokens +
                                output_tokens * usd_per_1m_output_tokens) / 1e6
                total_cost += request_cost
                print(f"{prefix}Tokens in: {input_tokens:04d}, Tokens out: {output_tokens:04d}")
                return result_text
            print(f"{prefix}[ERROR] Invalid response. (attempt {attempt}/{max_attempts})")
        except:
            print(f"{prefix}[ERROR] Request failed. (attempt {attempt}/{max_attempts})")
            time.sleep(2)
    print(f"{prefix}[ERROR] Prompt failed after {max_attempts} attempts.")
    return None

async def async_prompt_to_text(prompt, max_tokens=1000, isNum=True, maxLen=None):
    """
    Asynkron wrapper for prompt_to_text med propagasjon av context variables.
    """
    ctx = contextvars.copy_context()
    return await asyncio.to_thread(ctx.run, prompt_to_text, prompt, max_tokens, isNum, maxLen)
