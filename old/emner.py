import asyncio
import json
import sys
import prompttotext
from pathlib import Path

# Sett denne til True for å fjerne eksisterende temaer før nye legges til
fjern_temaer = True

JSON_PATH = Path("ntnu_emner.json")

ocrtext = " Kopi av Fremside Kopi av Eksamen IMAx2012 og IMAx2022 Institutt for matematiske fag Eksamensoppgave i IMAA2012, IMAA2022, IMAG2012, IMAG2022, IMAT2012 og IMAT2022 Eksamensdato: 10.05.2024 Eksamenstid (fra-til): 09:00 - 13:00 Hjelpemiddelkode/Tillatte hjelpemidler: Hjelpemiddelkode C. Godkjent kalkulator. Ingen håndskevne eler trykte hjelpemidler, formelark er lagt ved eksamen som en pdf-fil. Faglig kontakt under eksamen: Tlf.: Stine Marie Berge (93478689) Faglig kontakt møter i eksamenslokalet: Nei ANNEN INFORMASJON: Skaff deg overblikk over oppgavesettet før du begynner på besvarelsen din. Les oppgavene nøye, gjør dine egne antagelser og presiser i besvarelsen hvilke forutsetninger du har lagt til grunn i tolkning/avgrensing av oppgaven. Faglig kontaktperson kontaktes kun dersom det er direkte feil e ler mangler i oppgavesettet. Henvend deg til en eksamensvakt hvis du mistenker feil og mangler. Noter spørsmålet ditt på forhånd. Håndtegninger: I oppgave [2, 7] er det lagt opp til å besvare på ark. Andre oppgaver skal besvares direkte i Inspera. Nederst i oppgaven finner du en sjusifret kode. Fy l inn denne koden øverst til venstre på arkene du ønsker å levere. Det anbefales å gjøre dette underveis i eksamen. Dersom du behøver tilgang til kodene etter at eksamenstiden har utløpt, må du klikke «Vis besvarelse». Vekting av oppgavene: er gitt for hver oppgave. Det blir ikke gitt minus-poeng for feil eler manglende svar. Maksimal poengsum er 100 poeng på hele eksamen. Varslinger: Hvis det oppstår behov for å gi beskjeder til kandidatene underveis i eksamen (f.eks. ved feil i oppgavesettet), vil dette bli gjort via varslinger i Inspera. Et varsel vil dukke opp som en dialogboks på skjermen. Du kan finne igjen varselet ved å klikke på bjela øverst til høyre. Trekk fra/avbrutt eksamen: Blir du syk under eksamen, eler av andre grunner ønsker å levere blankt/avbryte eksamen, gå til “hamburgermenyen” i øvre høyre hjørne og velg «Lever blankt». Dette kan ikke angres selv om prøven fremdeles er åpen. Tilgang til besvarelse: Etter eksamen finner du besvarelsen din i arkivet i Inspera. Merk at det kan ta én virkedag før eventuele håndtegninger vil være tilgjengelige i arkivet. 1/14 1 Kopi av Oppgave 1: Partiell derivasjon Kopi av Eksamen IMAx2012 og IMAx2022 Oppgave 1 (10 Poeng) Denne oppgaven skal besvares i Inspera. Du skal ikke legge ved utregninger på papir. a) Gitt funksjonen . Finn verdiene til de partie lderiverte i punktet . b) Gitt funksjonen . . . Finn verdiene til de partie lderiverte i punktet . Angi svarene med desimaler. . . Maks poeng: 10 2 Kopi av Oppgave 2, kritiske punkt Oppgave 2 (10 Poeng) Denne oppgaven skal besvares på papir (med sjusifret kode) som skannes inn. La a) . Finn de kritiske punktene til funksjonen . b) Klassifiser de kritiske punktene til funksjonen . Med andre ord, avgjør om de kritiske punktene er sadelpunkter, lokale maksimumspunkter, lokale minimumspunkter, eler ingen av delene. Maks poeng: 10 2/14 3 Kopi av Oppgave 3: Retningsderivert Kopi av Eksamen IMAx2012 og IMAx2022 Oppgave 3 (10 Poeng) Denne oppgaven skal besvares i Inspera. Du skal ikke legge ved utregninger på papir. Vi har funksjonsuttrykket a) Finn gradienten i punktet b) . Vi starter i punktet , og beveger oss i retningen Finn den retningsderiverte. c) . . Figuren under viser nivåkurver for funksjonen . I tilegg viser figuren en tangentlinje til nivåkurven i et valgt punkt. Hvilken retning vil gradientvektoren ha i punktet? Alternativ 1: Gradientvektoren i punktet vil være parallell med tangentlinjen. Alternativ 2: Gradientvektoren i punktet vil stå vinkelrett på tangentlinjen. Alternativ 3: Retningen til gradientvektoren i punktet er verken parallell eller vinkelrett på tangentlinjen. Svar: Alternativ (skriv enten 1, 2, eler 3 i svarfeltet). Maks poeng: 10 3/14 4 Kopi av Oppgave 4: Graf-forståelse Kopi av Eksamen IMAx2012 og IMAx2022 Oppgave 4 (10 Poeng) Denne oppgaven skal besvares i Inspera. Du skal ikke legge ved utregninger på papir. Hvilken funksjon hører sammen med hvilken graf? 4/14 Kopi av Eksamen IMAx2012 og IMAx2022 5/14 Kopi av Eksamen IMAx2012 og IMAx2022 Skriv bare én av bokstavene A, B, C, D, E i hvert felt under. Funksjonen Funksjonen og figuren og figuren hører sammen. hører sammen. Funksjonen og figuren hører sammen. Funksjonen Funksjonen og figuren og figuren hører sammen. hører sammen. Maks poeng: 10 6/14 5 Kopi av Oppgave 5: Taylor 1D Kopi av Eksamen IMAx2012 og IMAx2022 Oppgave 5 (10 Poeng) Denne oppgaven skal besvares i Inspera. Du skal ikke legge ved utregninger på papir. La a) . Finn verdiene til i punktet . Angi svaret korrekt avrundet til 3 desimaler. b) . . Lag det 2. ordens taylorpolynomet om punktet for funksjonen . Bruk polynomet til å finne en tilnærming til verdien . Angi svaret korrekt avrundet til 3 desimaler. . Maks poeng: 10 7/14 6 Kopi av Oppgave 6: Fourierrekke Kopi av Eksamen IMAx2012 og IMAx2022 Oppgave 6 (8 Poeng) Denne oppgaven skal besvares i Inspera. Du skal ikke legge ved utregninger på papir. La . a) Hva er sant om funksjonen funksjonen ? Velg ett alternativ La Funksjonen er verken jevn eler odde. Funksjonen er ikke periodisk. Funksjonen er jevn. Funksjonen er odde. b) Hva er ? Velg ett alternativ 1/2 1-1-1/2 c) Hva er ? være fourierrekken til . 8/14 Velg ett alternativ Kopi av Eksamen IMAx2012 og IMAx2022 1-2 0 2-1 d) Hva er ? Hint: Bruk variabelbytte Velg ett alternativ 0-1 1 . Maks poeng: 8 9/14 7 Kopi av Oppgave 7, jevn og odd fourierrekke Kopi av Eksamen IMAx2012 og IMAx2022 Oppgave 7 (8 Poeng) Denne oppgaven skal besvares på papir (med sjusifret kode) som skannes inn. La a) for . Vi skal finne sinus- og cosinusrekken (også kalt den odde- og jevne fourierrekken) av funksjonen . Hva er perioden ? b) La være den jevne fourierrekken (også kalt cosinusrekken) til . Finn fourierkoffisientene og når Hint: Hva er den jevne utvidelsen av ? c) La være den odde fourierrekken (også kalt sinusrekken) til funksjonen . Finn fourierkoffisienten . Maks poeng: 8 10/14 8 Kopi av Oppgave 8: PDE Kopi av Eksamen IMAx2012 og IMAx2022 Oppgave 8 (8 Poeng) Denne oppgaven skal besvares i Inspera. Du skal ikke legge ved utregninger på papir. Funksjonen a) Da har vi at fourierkoeffisientene til er som følger: , , , , , . b) La er periodisk med periode . være løsningen til initialverdiproblemet for bølgeligningen Da er Hint: Finn først ut hva løsningen er. . Maks poeng: 8 11/14 9 Kopi av Oppgave 9: Fouriertransformasjon Kopi av Eksamen IMAx2012 og IMAx2022 Oppgave 9 (6 Poeng) Denne oppgaven skal besvares i Inspera. Du skal ikke legge ved utregninger på papir. a) La være fouriertransformasjonen til Da er + b) La . . Finn verdien avrundet til 3 desimaler. c) La . Berekn + . Angi svaret korrekt og finn + . Maks poeng: 6 10 Kopi av Oppgave 10: Konvolusjon Oppgave 10 (6 Poeng) Denne oppgaven skal besvares i Inspera. Du skal ikke legge ved utregninger på papir. Enhets-sprang funksjonen (eler Heaviside funksjonen) er La være konvolusjonen av enhets-sprang funksjonen med seg selv. Hva er og ? Maks poeng: 6 12/14 11 Kopi av Oppgave 11: DFT Kopi av Eksamen IMAx2012 og IMAx2022 Oppgave 11 (6 Poeng) Denne oppgaven skal besvares i Inspera. Du skal ikke legge ved utregninger på papir. Du er gitt følgende kode: Sampling rate er det engelske navnet på prøvefrekvensen også kalt prøveraten. a) Hva er prøveavstanden? Det vil si avstanden melom prøvene i koden over. Velg ett alternativ b) 0.2 1 5 0.5 Hva skjer i linje 10 i koden? Velg ett alternativ c) Ale frekvensene som er mindre 0.5 blir satt til 0. Ale frekvensene som er melom -0.5 og 0.5 blir satt til 0. Ale frekvensene som er over 0.5 eler mindre en -0.5 blir satt til 0. Ale frekvensene som er over 0.5 blir satt til 0. Du har et lydsignal, men ønsker å fjerne støy som blei produsert av en liten vifte som stod på når lyden ble tatt opp. Du ønsker å beholde frekvenser melom 70Hz og 3000Hz, men å fjerne viftestøyen på 6000Hz. Hvilket filter kan du bruke? 13/14 Velg ett alternativ: Kopi av Eksamen IMAx2012 og IMAx2022 Lavpassfilter Høypassfilter Ingen av delene 12 Kopi av Oppgave 12: IDFT Oppgave 12 (8 Poeng) Maks poeng: 6 Denne oppgaven skal besvares i Inspera. Du skal ikke legge ved utregninger på papir. Vi skal finne invers diskrete fouriertransformasjonen (IDFT) av sekvensen Her er , , og . Angi svaret korrekt avrundet til 3 desimaler. + , + + + . , , Maks poeng: 8 14/14"

def load_emnekart_from_json(json_path: Path):
    """
    Leser hele JSON-listen og returnerer den og et kart fra kode->navn
    """
    if not json_path.is_file():
        print(f"❌ Feil: JSON-filen '{json_path}' finnes ikke.", file=sys.stderr)
        sys.exit(1)
    try:
        with json_path.open(encoding="utf-8") as jf:
            data = json.load(jf)
    except Exception as e:
        print(f"❌ Kunne ikke lese JSON: {e}", file=sys.stderr)
        sys.exit(1)

    emnekart = {}
    for entry in data:
        kode = entry.get("Emnekode")
        navn = entry.get("Emnenavn")
        if kode and navn:
            emnekart[kode.upper()] = navn
    return data, emnekart

async def test_prompt():
    # Last inn JSON-data og emnekart
    data, emnekart = load_emnekart_from_json(JSON_PATH)

    # Hent emnekoder fra OCR-tekst
    raw_codes = await prompttotext.async_prompt_to_text(
        "DONT EVER EXPLAIN OR SAY WHAT YOU ARE DOING. JUST DO AS YOU ARE TOLD AND RESPOND WITH WHAT IS ASKED FROM YOU. "
        "What are the subject codes for this exam? Respond only with codes separated by commas: " + ocrtext,
        max_tokens=100,
        is_num=False,
        max_len=200
    )

    # Splitt og normaliser
    codes = [c.strip().upper() for c in raw_codes.split(",") if c.strip()]
    print(f"🗂️  Funnet emnekoder: {codes}")

    # Map koder til unike emnenavn
    emnenavnliste = []
    for kode in codes:
        navn = emnekart.get(kode)
        if navn and navn not in emnenavnliste:
            emnenavnliste.append(navn)
    if not emnenavnliste:
        print("❌ Ingen gyldige emnenavn funnet.", file=sys.stderr)
        return
    print(f"📝 Kombinerte emnenavn: {emnenavnliste}")

    # Be modellen om en samlet liste temaer
    emne_str = ", ".join(emnenavnliste)
    prompt = (
        "DONT EVER EXPLAIN OR SAY WHAT YOU ARE DOING. JUST DO AS YOU ARE TOLD AND RESPOND WITH WHAT IS ASKED FROM YOU. "
        "Hva er temaene på hver av oppgavene i dette eksamenssettet? "
        "Svar med en enkel liste separert med tabs eller newlines. "
        ""
        "Bare subtemaene, ikke kategoriseringer. Gi én samlet liste: " + ocrtext
    )

    try:
        result = await prompttotext.async_prompt_to_text(
            prompt,
            max_tokens=2000,
            is_num=False,
            max_len=3000
        )
    except Exception as e:
        print(f"❌ Feil under API-kall: {e}", file=sys.stderr)
        return

    print(f"\n🎯 Funnede temaer:\n{result}")

    # Del opp resultat til liste
    temas = [t.strip() for t in result.replace("\t", "\n").split("\n") if t.strip()]
    print(f"📋 Antall temaer: {len(temas)}")

    # Oppdater alle JSON-oppføringer med matchende koder
    for entry in data:
        kode = entry.get("Emnekode", "").upper()
        if kode in codes:
            # Fjern eksisterende temaer hvis flagget er satt
            if fjern_temaer:
                entry["Temaer"] = []
            current = entry.get("Temaer", [])
            # Legg til alle nye temaer
            current.extend(temas)
            entry["Temaer"] = current

    # Lagre tilbake til JSON
    try:
        with JSON_PATH.open('w', encoding='utf-8') as jf:
            json.dump(data, jf, ensure_ascii=False, indent=4)
        print(f"💾 Oppdatert JSON lagret til {JSON_PATH}")
    except Exception as e:
        print(f"❌ Feil ved skriving av JSON: {e}", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(test_prompt())
