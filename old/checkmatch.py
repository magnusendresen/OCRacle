inp = input("Mønster (bruk X som jokertegn): ").strip().upper()

ref = [
    "IMAT2022",
    "IMAT2012",
    "IFYT1000"
]

matches = [
    emne
    for emne in ref
    if len(emne) == len(inp)
    and all(ci == ce or ci == "X" for ci, ce in zip(inp, emne))
]

print("Matchende emner:", ", ".join(matches) if matches else "Ingen")
