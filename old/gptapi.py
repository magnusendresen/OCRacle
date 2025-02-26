from openai import OpenAI
from tqdm import tqdm

client = OpenAI()

COST_PER_1000_TOKENS_NOK = 0.01  # Estimert pris per 1000 tokens i NOK

def promptToText(prompt):
    try:
        completion = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        tokens_used = completion.usage.total_tokens if hasattr(completion, 'usage') else "Ukjent"
        return completion.choices[0].message.content, tokens_used
    except Exception as e:
        print(f"\n[ERROR] Feil ved forespørsel til OpenAI: {e}\n")
        return "", "Ukjent"

nonchalant = "Ikke forklar hva du gjør, bare gjør det."

def main(text):
    test = 100
    while test > 30:
        try:
            response, tokens_used = promptToText("Hvor mange oppgaver er det i denne teksten som er extractet? Svar kun med ett tall som skal omgjøres til en int og brukes til programmering: " + text)
            test = int(response)
        except ValueError:
            print("\n[ERROR] OpenAI returnerte ikke et gyldig tall, prøver på nytt...\n")
            continue

    amount = test
    tasks = []
    instructions = [
        ("Hva er oppgave ", "?: Skriv all tekst knyttet til oppgaven rett fra råteksten, ikke løs oppgaven: "),
        ("Fjern all tekst knyttet til Inspera og eksamensgjennomførelse: ", ""),
        ("Oversett oppgaven til norsk bokmål: ", ""),
        ("Skriv all teksten over på en enkelt linje altså uten noen newlines: ", "")
    ]
    step_size = 100 // len(instructions)
    
    with tqdm(total=amount, desc="Prosesserer oppgaver") as pbar:
        for i in range(amount):
            task_valid = False
            total_tokens = 0
            while not task_valid:
                task = text
                with tqdm(total=100, desc=f"Oppgave {i+1}", leave=True) as task_pbar:
                    for _, (prefix, suffix) in enumerate(instructions):
                        task, tokens_used = promptToText(nonchalant + prefix + str(i+1) + suffix + task)
                        total_tokens += tokens_used if isinstance(tokens_used, int) else 0
                        task_pbar.update(step_size)
                        if not task:
                            print(f"\n[ERROR] Ingen respons fra OpenAI for instruksjon i oppgave {i+1}, prøver på nytt...\n")
                            break

                test = ""
                while test not in ["0", "1"]:
                    test, tokens_used = promptToText(nonchalant + "PASS PÅ AT DU KUN SVARER MED 0 ELLER 1 HER!!! Svar 1 for True og 0 for False: Er dette en legitim oppgave som kan brukes i et eksamenssett? " + task)
                    total_tokens += tokens_used if isinstance(tokens_used, int) else 0
                    if test not in ["0", "1"]:
                        print(f"\n[ERROR] ChatGPT returnerte ikke en gyldig boolean for oppgave {i+1}, prøver på nytt...\n")
                
                if test == "0":
                    print(f"\n[WARNING] Oppgave {i+1} ble ikke godkjent, prøver på nytt...\n")
                    continue
                
                tasks.append(task)
                task_valid = True
                pbar.update(1)
                cost_estimate = (total_tokens / 1000) * COST_PER_1000_TOKENS_NOK
                print(f"\n[INFO] Totale tokens brukt for oppgave {i+1}: {total_tokens} (Estimert kostnad: {cost_estimate:.4f} NOK)\n")
    
    return tasks