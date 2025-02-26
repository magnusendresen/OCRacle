import os
import time
from openai import OpenAI  # Bruker OpenAI SDK for DeepSeek

# Hent API-nøkkel fra miljøvariabler
api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise ValueError("API key not found in environment variables.")

# Initialiser DeepSeek-klienten
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# Kostnadsberegning per 1000 tokens (NOK)
COST_PER_1000_TOKENS_NOK = 0.01

MODEL_NAME = "deepseek-chat"
total_cost = 0  # Variabel for å akkumulere total kostnad

# ✅ Print at API-forbindelsen er vellykket
print("[INFO] Successfully made contact with DeepSeek API!\n")

def prompt_to_text(prompt, max_retries=3, max_tokens=1000):
    """Sender forespørsel til DeepSeek, viser token-bruk og beregner kostnad."""
    global total_cost  # Sørger for at vi oppdaterer den globale kostnadsvariabelen
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

                # Beregn kostnad for denne forespørselen
                request_cost = (total_tokens / 1000) * COST_PER_1000_TOKENS_NOK
                total_cost += request_cost  # Akkumuler kostnaden

                # Print tokenforbruk og kostnad
                print(f"[INFO] Input tokens: {input_tokens}, Output tokens: {output_tokens}, "
                      f"Total tokens: {total_tokens}, Cost: {request_cost:.4f} NOK, Total Cost: {total_cost:.4f} NOK")

                return result_text, total_tokens
            
            print(f"[ERROR] Ugyldig respons fra DeepSeek (forsøk {attempt+1}/{max_retries}). Prøver på nytt...")
        except Exception as e:
            print(f"[ERROR] Feil ved forespørsel til DeepSeek: {e} (forsøk {attempt+1}/{max_retries})")
            time.sleep(2)
    
    return "", 0  # Returnerer tom respons hvis alle forsøk feiler

def main(text):
    """Hovedfunksjon som ekstraherer oppgaver fra en gitt tekst."""
    global total_cost  # Sikrer at total kostnad oppdateres

    nonchalant = "Ikke forklar hva du gjør, bare gjør det."

    test = 100
    while test > 30:
        response, tokens_used = prompt_to_text(
            f"{nonchalant} Hvor mange oppgaver er det i denne teksten? Svar kun med ett tall:"
        )
        try:
            test = int(response)
        except ValueError:
            print("[ERROR] DeepSeek returnerte ikke et gyldig tall, prøver igjen...")
            continue

    amount = test

    # ✅ Print antall oppgaver i eksamenssettet før prosessering starter
    print(f"\n[INFO] Antall oppgaver funnet i eksamenssettet: {amount}\n")

    tasks = []
    instructions = [
        ("Hva er oppgave ", "?: Skriv all tekst knyttet til oppgaven rett fra råteksten, ikke løs oppgaven."),
        ("Fjern all tekst knyttet til Inspera og eksamensgjennomførelse: ", ""),
        ("Oversett oppgaven til norsk bokmål: ", ""),
        ("Skriv all teksten over på en enkelt linje (ingen newlines): ", "")
    ]

    for i in range(amount):
        print(f"\n[INFO] Task {i+1} started processing...")  # ✅ Ny print for start

        task_valid = False
        while not task_valid:
            task = text
            for prefix, suffix in instructions:
                response, tokens_used = prompt_to_text(nonchalant + prefix + str(i+1) + suffix + task)
                task = response
                if not task:
                    print(f"[ERROR] Ingen respons fra DeepSeek for oppgave {i+1}, prøver på nytt...")
                    break

            test = ""
            while test not in ["0", "1"]:
                response, tokens_used = prompt_to_text(
                    f"{nonchalant} PASS PÅ AT DU KUN SVARER MED 0 ELLER 1 HER!!! Svar 1 hvis dette er en gyldig oppgave, ellers 0: {task}"
                )
                test = response.strip()

                if test not in ["0", "1"]:
                    print(f"[ERROR] DeepSeek returnerte ikke en gyldig boolean for oppgave {i+1}, prøver igjen...")

            if test == "0":
                print(f"[WARNING] Oppgave {i+1} ble ikke godkjent, prøver på nytt...")
                continue

            tasks.append(task)
            task_valid = True

        print(f"[INFO] Task {i+1} finished processing.")  # ✅ Ny print for slutt

    # ✅ Print total kostnad etter all prosessering
    print(f"\n[INFO] Endelig total kostnad for hele eksamenssettet: {total_cost:.4f} NOK\n")

    return tasks
