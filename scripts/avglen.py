str = (
"Dette er en tekststreng som jeg skal bruke for å finne gjennomsnittlig lengde på hvert ord."
"\n Den skal også håndtere flere linjer og spesialtegn, som komma, punktum og-bindestrek."
)
print(f"Avg = {sum(len(word) for word in str.split()) / len(str.split()):.2f}")