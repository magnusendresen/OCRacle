import os
import time
import asyncio
from openai import OpenAI  # Using OpenAI SDK for DeepSeek

# Hent API-nøkkelen fra miljøvariabler
api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise ValueError("API key not found in environment variables.")

# Initialiser DeepSeek-klienten
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# Prisestimater for API-kall
usd_per_1m_input_tokens = 0.27
usd_per_1m_output_tokens = 1.10

MODEL_NAME = "deepseek-chat"
total_cost = 0  # Variabel for å akkumulere total kostnad

print("[DEEPSEEK] Connected to DeepSeekAPI!\n")

def prompt_to_text(prompt, max_retries=3, max_tokens=1000):
    """Synkron funksjon for å sende API-kall og beregne kostnad."""
    global total_cost
    for attempt in range(max_retries):
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
                total_tokens = response.usage.total_tokens

                # Beregn kostnad
                request_cost = (input_tokens * usd_per_1m_input_tokens +
                                output_tokens * usd_per_1m_output_tokens) / 1e6
                total_cost += request_cost

                print(f"[DEEPSEEK] Input Tokens: {input_tokens}, Output Tokens: {output_tokens}, Total Tokens: {total_tokens}")
                print(f"[DEEPSEEK] Cost: {request_cost:.4f} USD, Total Cost: {total_cost:.4f} USD\n")
                return result_text

            print(f"[ERROR] Invalid response (forsøk {attempt+1}/{max_retries}). Retrying...")
        except Exception as e:
            print(f"[ERROR] Request failed: {e} (forsøk {attempt+1}/{max_retries})")
            time.sleep(2)
    return ""  # Returner tom streng hvis alle forsøk mislykkes

async def async_prompt_to_text(prompt, max_retries=3, max_tokens=1000):
    """
    Asynkron wrapper for prompt_to_text ved bruk av asyncio.to_thread.
    Dette gjør at vi kan kjøre de blokkerende API-kallene parallelt.
    """
    return await asyncio.to_thread(prompt_to_text, prompt, max_retries, max_tokens)

async def main_async():
    """
    Hovedfunksjonen for asynkrone kall.
    Vi definerer flere prompt og sender API-kallene samtidig med asyncio.gather.
    """
    prompts = [
        "Hva er hovedstaden i Frankrike?",
        "Forklar kort hva kvanteberegning er.",
        "Oppsummer handlingen i filmen Inception med én setning."
    ]

    # Opprett asynkrone oppgaver for hvert API-kall
    tasks = [asyncio.create_task(async_prompt_to_text(prompt)) for prompt in prompts]

    # Vent på at alle oppgaver skal fullføres samtidig
    results = await asyncio.gather(*tasks)

    # Skriv ut resultatene
    for i, result in enumerate(results, start=1):
        print(f"Resultat {i}: {result}\n")

if __name__ == "__main__":
    asyncio.run(main_async())
