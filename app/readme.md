# OCRacle - prossesering og sortering av eksamensoppgaver, for bedre eksamensøving

Programmet er et brukersnitt laget i C++ for et allerede påbegynt prosjekt skrevet i Python. Det kommuniseres mellom programmeringsspåkene enkelt ved skriving og lesing av tekstfiler, ettersom nødvendig informasjon delt mellom språkene er minimal. C++ styrer alt visuelt med AnimationWindow, og all behandling av pdf og tekst gjøres i Python ved bruk av Google Vision og DeepSeek API.

I 'dir.txt' skrives directorien til pdf-filen valgt i AnimationWindow interfacen, som deretter leses av python-programmet. 

I 'progress.txt' skrives følgende informasjon fra Python, som oppdaterer interfacen i AnimationWindow hver gang C++ oppdager en endring i fila:
- Vellykket tilkobling til APIen til Google Vision og DeepSeek, 
- Status på OCR (optical character recognition) av PDF og AI-behandling av tekst
- Eksamensinformasjon (emne, utgivelse, antall oppgaver)

Klassen App arver fra animationwindow og har følgende funksjonalitet:
- pdfHandling() for popup-vindu som lar brukeren velge pdf
- calculateProgress() som overvåker progress.txt og oppdaterer GUI og variablene til ProgressBar
- startTimer() og stopTimer() som styrer en timer som viser hvor lenge eksamenssett-prosseseringa har kjørt
- samt. diverse statiske variabler for GUI og pekere til elementene som er lagt til

Klassen ProgressBar styrer progressbarene i vinduet og har følgende funksjonalitet:
- setCount()
- variabelen progress som oppdateres

I Python-delen av prosjektet er følgende skript med:
- ocrpdf.py som bruker Google Vision API til å behandle pdf-en som bilder og lese den til tekst
- textnormalization.py som rydder i merkelige symboler og artifacts som kan oppstå ved OCR
- cachetask.py som ble brukt i utviklingdelen av prosjektet for å slippe å gjøre pdf-behandling, og heller gå direkte på OCR-resultatet med DeepSeek
- prompttotext.py som tar inn en prompt fra DeepSeek og returnerer et svar
- taskprocessing.py som stegvis går gjennom en rekke prompts og tar teksten fra OCR-en og omgjør til objekter
- objecttojson.py som skriver objektene til json-filen tasks.json

Når det kommer til bruk av AI er det hyppig brukt i samtlige deler av prosjektet, det er derimot ingenting av koden i det ferdige prosjektet som er direkte skrevet av AI. Det er utelukkende brukt til følgende:
- Forståelse av prosjektet
- Problemløsning og brainstorming
- Forklaring av konsepter i C++
- Kritikk av kode
- Testing av metoder og kode


Følgende includes er brukt i C++:
- AnimationWindow.h
- ProgressBar.h
- string
- chrono
- thread
- widgets/TextBox.h
- widgets/Button.h
- App.h
- iostream
- windows.h
- map
- atomic
