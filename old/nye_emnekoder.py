import json
import os
from collections import defaultdict
from project_config import *

def splitt_emnekode(kode):
    """Deler opp i bokstavprefiks og tall"""
    for i, c in enumerate(kode):
        if c.isdigit():
            return kode[:i], kode[i:]
    return kode, ""  # fallback

def felles_prefiks(prefikser):
    """Returnerer felles prefiks med X der det varierer"""
    lengde = min(len(p) for p in prefikser)
    resultat = ""
    for i in range(lengde):
        tegn = {p[i] for p in prefikser}
        resultat += tegn.pop() if len(tegn) == 1 else "X"
    return resultat

def main():
    file_path = EXAM_CODES_JSON
    with open(file_path, encoding='utf-8') as f:
        emner = json.load(f)

    # Steg 1: Gruppér på emnenavn
    grupper = defaultdict(list)
    for e in emner:
        grupper[e["Emnenavn"]].append(e)

    resultat = []
    total = len(grupper)
    count = 0

    for navn, gruppe in grupper.items():
        # Steg 2: Del opp i (bokstavprefiks, tall)-grupper
        undergrupper = defaultdict(list)
        for e in gruppe:
            pre, num = splitt_emnekode(e["Emnekode"])
            if num:  # kun hvis det faktisk finnes tall
                undergrupper[num].append(pre)

        for num, prefikser in undergrupper.items():
            ny_prefiks = felles_prefiks(prefikser)
            ny_kode = ny_prefiks + num
            resultat.append({
                "Emnekode": ny_kode,
                "Emnenavn": navn,
                "Temaer": gruppe[0].get("Temaer", [])
            })

        count += 1
        print(f"\rProgresjon: {int(count / total * 100)}%", end="")

    print("\nFullført.")

    output_path = EXAM_CODES_JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(resultat, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
