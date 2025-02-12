from openai import OpenAI

client = OpenAI()

def promptToText(prompt):
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    return completion.choices[0].message.content

nonchalant = "Ikke forklar hva du gjør, bare gjør det."

def main(text):
    amount = int(promptToText("Hvor mange oppgaver er det i denne teksten som er extractet? Svar kun med ett tall som skal omgjøres til en int og brukes til programmering: " + text))
    print("Antall oppgaver: " + str(amount))
    print("Det er omtrent", round(len(text) / 5), "ord i teksten fra pdf-en.")
    tasks = []
    for i in range(amount):
        task = promptToText(nonchalant + "Hva er oppgave " + str(i+1) + "?: Skriv all tekst knyttet til oppgaven rett fra råteksten, ikke løs oppgaven: " + text)
        print("Oppgave ", i+1, " er omtrent ", round(len(task) / 5), " ord lang.")
        task = promptToText(nonchalant + "Fjern all tekst knyttet til Inspera og eksamensgjennomførelse: " + task)
        task = promptToText(nonchalant + "Oversett oppgaven til norsk bokmål: " + task)
        task = promptToText(nonchalant + "Skriv all teksten over på en enkelt linje altså uten noen newlines: " + task)

        if int(promptToText(nonchalant + "PASS PÅ AT DU KUN SVARER MED 0 ELLER 1 HER!!! Svar 1 for True og 0 for False: Er dette en legitim oppgave?  " + task)):
            print("Oppgave " + str(i+1) + " er en legitim oppgave.")
            tasks.append(task)
        else:
            print("Oppgave " + str(i+1) + " er ikke en legitim oppgave.")

        

        

    return tasks

