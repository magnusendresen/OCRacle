#!/usr/bin/env python3
"""
Return a comma-separated string of all unique 'Temaer' for fuzzy-matching emnekoder.
If none are found, return the default full topic list.
"""

import json
import difflib
from pathlib import Path

def get_topics(emnekode: str) -> str:
    """
    Return comma-separated unique 'Temaer' for matching emnekoder, or default list if none found.
    """
    json_path = Path(__file__).resolve().parent / "ntnu_emner.json"


    with json_path.open('r', encoding='utf-8') as f:
        data = json.load(f)


    all_codes = [entry.get("Emnekode", "").upper() for entry in data]
    matches = difflib.get_close_matches(emnekode.upper(), all_codes, n=len(all_codes), cutoff=0.6)

    unike_temaer = set()

    for entry in data:
        if entry.get("Emnekode", "").upper() in matches:
            temaer = entry.get("Temaer", [])
            unike_temaer.update(map(str.strip, temaer))

    if not unike_temaer:
        return (
            "Partiell Derivasjon, Kritiske Punkt, Retningsderivert, Graf-Forståelse, Taylor 1D, "
            "Fourierrekke, Jevn og Odd Fourierrekke, PDE, Fouriertransformasjon, Konvolusjon, DFT, IDFT, "
            "Fagverk, Opplagerkrefter, Nullstaver, Strekk og Trykk i Fagverk, Arealtyngdepunkt, "
            "Arealmoment og Steiner, Statisk Bestemthet i Ramme, Reaksjonskrefter i Ramme, "
            "Normalkraftdiagram, Skjærkraftdiagram, Momentdiagram, Bøyespenning i Tverrsnitt, "
            "Tverrsnittdimensjonering, Deformasjonsmønster, Forskyvning og Rotasjon i Punkt, "
            "Pythonkodeanalyse for Nedbøyning"
        )

    return ", ".join(sorted(unike_temaer))


if __name__ == '__main__':
    # 🔧 Endre dette til ønsket emnekode-streng
    input_str = "IMAX20X2"

    resultat = hent_temaer(input_str)
    print(resultat)
