# OCRacle – prosessering og sortering av eksamensoppgaver, for bedre eksamensøving

## Samarbeid mellom Python og C++
Programmet er et brukergrensesnitt laget i C++ for et allerede påbegynt prosjekt skrevet i Python. Kommunikasjonen mellom språkene skjer enkelt via skriving og lesing av tekstfiler, ettersom den nødvendige informasjonen som deles er minimal. C++ styrer alt visuelt med AnimationWindow, mens all behandling av PDF og tekst gjøres i Python ved bruk av Google Vision og DeepSeek API.

I `dir.json` skrives banene til valgte filer (eksamen, løsningsforslag og formelsamling), som deretter leses av Python-programmet.
I `progress.json` skrives følgende informasjon fra Python, som oppdaterer GUI-et i AnimationWindow hver gang C++ oppdager en endring i filen:
- Status på tilkobling til API-ene Google Vision og DeepSeek  
- Fremdrift for OCR (optical character recognition) og AI-behandling  
- Eksamensinformasjon (emnekode, versjon, antall oppgaver)

---

## C++-delen

### Klassen `App` arver fra `AnimationWindow` og har følgende funksjoner:
- `pdfHandling()` – viser et popup-vindu for valg av PDF-fil
- `calculateProgress()` – overvåker `progress.json` og oppdaterer GUI og progress-variabler
- `startTimer()` og `stopTimer()` – viser hvor lenge prosesseringen har kjørt
- Statiske GUI-variabler og pekere til elementene som vises i vinduet

### Klassen `ProgressBar`:
- Har funksjonen `setCount()` som tegner fremdrift
- Har en `progress`-variabel som kontrollerer fremdriften

---

## Python-skriptene
 - `ocr_pdf.py` – bruker Google Vision API til å lese PDF som bilder og hente tekst
 - `text_normalization.py` – renser opp i artifacts og symboler etter OCR
- `cachetask.py` – brukt under utvikling for å teste DeepSeek uten ny OCR
- `prompt_to_text.py` – sender prompts til DeepSeek og henter svar
- `task_processing.py` – styrer hele prompt-prosessen og bygger oppgaveobjekter
- `object_handling.py` – håndterer oppdateringer av `exams.json`
  i strukturen `emne -> exams -> oppgave`.
  Eksempel:

  ```json
  {
      "INGX1002": {
          "topics": ["Matematiske operasjoner", "Funksjoner"],
          "exams": {
              "H24": {
                  "tasks": [
                      {
                          "topic": "Matematiske operasjoner",
                          "task_number": "1",
                          "points": 4,
                          "task_text": "<p>..."
                      }
                  ]
              }
          }
      }
  }
  ```
  Feltene `total_tasks`, `code` og `images` lagres ikke i filen.
- `prompt_tuning_plot.py` – kjører tuning, lagrer resultater og lager mer
  utfyllende plott med annotasjoner

## Start av Python-arbeidsflyten
Python-delen startes med

```bash
python -m scripts.main
```

Du kan også bruke `python scripts/main.py`. Før kjøring må miljøvariabler som `OCRACLE_JSON_PATH` og `DEEPSEEK_API_KEY` settes. Alle skriptene henter innstillinger fra `project_config.py` hvor blant annet `PROJECT_ROOT`, `PROGRESS_FILE` og `PROMPT_CONFIG` er definert.


## Eksempel av prompting i task_processing.py:
```
What is task number {task_number}?
Write only all text related directly to that one task from the raw text: {text}
```
```
How many points can you get for this task? Only reply with the number of points, nothing else: {text}
```
```
What is the topic of this task? Categorize as brief as possible, use minimal words. Only respond with the topic, nothing else: {text}
```
```
Remove all text related to Inspera and exam administration, keep only what is necessary for solving the task: {text}
```
```
Translate this task text from norwegian nynorsk or english to norwegian bokmål, do not change anything else: {text}
```
```
Answer 1 if this is a valid task that could be in an exam and that can be logically solved, otherwise 0: {text}
```
---

## Bruk av KI-verktøy

AI (ChatGPT) har vært brukt hyppig i alle faser av prosjektet, men **ingen kode i det ferdige prosjektet er direkte skrevet av KI**.
Verktøyene er brukt til:
- Forståelse av prosjektet
- Brainstorming og problemløsning
- Forklaringer på konsepter i C++
- Kodekritikk og testing av metoder
- Tips til forbedring og forenkling av implementasjon
- Formattering og utseende av readme.md

---

## Inkluderte biblioteker og headers i C++

```cpp
AnimationWindow.h
ProgressBar.h
string
chrono
thread
widgets/TextBox.h
widgets/Button.h
App.h
iostream
windows.h
map
```

## Inkluderte biblioteker i Python

```python
numpy
pandas
regex
torch
tqdm
transformers
requests
scipy
matplotlib
PyMuPDF
pdf2image
PyPDF2
Pillow
pytesseract
google-cloud-vision
protobuf
openai
contextvars
pathlib
sys
copy
collections
```

## Andre ressurser

```
Google Vision API
DeepSeek API
ChatGPT Pro
Visual Studio Code
```