# OCRacle – prosessering og sortering av eksamensoppgaver, for bedre eksamensøving

Programmet er et brukergrensesnitt laget i C++ for et allerede påbegynt prosjekt skrevet i Python. Kommunikasjonen mellom språkene skjer enkelt via skriving og lesing av tekstfiler, ettersom den nødvendige informasjonen som deles er minimal. C++ styrer alt visuelt med AnimationWindow, mens all behandling av PDF og tekst gjøres i Python ved bruk av Google Vision og DeepSeek API.

I `dir.txt` skrives banen til PDF-filen valgt i AnimationWindow-vinduet, som deretter leses av Python-programmet.  
I `progress.txt` skrives følgende informasjon fra Python, som oppdaterer GUI-et i AnimationWindow hver gang C++ oppdager en endring i filen:
- Status på tilkobling til API-ene Google Vision og DeepSeek  
- Fremdrift for OCR (optical character recognition) og AI-behandling  
- Eksamensinformasjon (emnekode, versjon, antall oppgaver)

---

## C++-delen

### Klassen `App` arver fra `AnimationWindow` og har følgende funksjoner:
- `pdfHandling()` – viser et popup-vindu for valg av PDF-fil
- `calculateProgress()` – overvåker `progress.txt` og oppdaterer GUI og progress-variabler
- `startTimer()` og `stopTimer()` – viser hvor lenge prosesseringen har kjørt
- Statiske GUI-variabler og pekere til elementene som vises i vinduet

### Klassen `ProgressBar`:
- Har funksjonen `setCount()` som tegner fremdrift
- Har en `progress`-variabel som kontrollerer fremdriften

---

## Python-skriptene

- `ocrpdf.py` – bruker Google Vision API til å lese PDF som bilder og hente tekst
- `textnormalization.py` – renser opp unødvendige symboler etter OCR
- `cachetask.py` – brukt under utvikling for å teste DeepSeek uten ny OCR
- `prompttotext.py` – sender prompts til DeepSeek og henter svar
- `taskprocessing.py` – styrer hele prompt-prosessen og bygger oppgaveobjekter
- `objecttojson.py` – lagrer oppgaveobjektene til `tasks.json`

# Eksempel av prompting i taskprocessing.py:
```
What is task number {task_number}?
Write only all text related directly to that one task from the raw text.
Include how many maximum points you can get. Do not solve the task: {text}
```
```
How many points can you get for this task? Only reply with the number of points, nothing else: {text}
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

AI har vært brukt hyppig i alle faser av prosjektet, men **ingen kode i det ferdige prosjektet er direkte skrevet av KI**.  
Verktøyene er brukt til:
- Forståelse av prosjektet og spesifikasjoner
- Brainstorming og problemløsning
- Forklaringer på konsepter i C++
- Kodekritikk og testmetoder
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
atomic