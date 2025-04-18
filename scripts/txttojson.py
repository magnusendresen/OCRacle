import json
import sys
from pathlib import Path

def convert_txt_to_json(txt_path: str, json_path: str) -> None:
    """
    Leser en tab-separert .txt-fil med kolonnene
    Emnekode, Emnenavn, Sted (første linje er header),
    og skriver ut en JSON-fil der hver post også har en tom 'Temaer'-liste.
    Printer status underveis og håndterer vanlige feil.
    """
    txt_file = Path(txt_path)
    if not txt_file.is_file():
        print(f"❌ Feil: Filen '{txt_path}' finnes ikke.", file=sys.stderr)
        return

    emner = []
    try:
        with txt_file.open(encoding='utf-8') as f:
            print(f"🛠️ Leser fra {txt_path}…")
            header = f.readline()
            for lineno, line in enumerate(f, start=2):
                raw = line.rstrip('\n')
                if not raw.strip():
                    # tom linje
                    continue
                parts = raw.split('\t')
                if len(parts) < 3:
                    print(f"⚠️  Linje {lineno}: Ugyldig antall felt ({len(parts)}), hopper over.", file=sys.stderr)
                    continue
                emnekode, emnenavn, sted = parts[:3]
                emner.append({
                    "Emnekode": emnekode.strip(),
                    "Emnenavn": emnenavn.strip(),
                    "Sted": sted.strip(),
                    "Temaer": []
                })
            print(f"✅ Ferdig å lese. Antall gyldige emner: {len(emner)}")
    except Exception as e:
        print(f"❌ Kunne ikke lese fra '{txt_path}': {e}", file=sys.stderr)
        return

    # Skriv JSON
    try:
        with open(json_path, 'w', encoding='utf-8') as jf:
            json.dump(emner, jf, ensure_ascii=False, indent=4)
        print(f"💾 JSON lagret til {json_path}")
    except Exception as e:
        print(f"❌ Kunne ikke skrive til '{json_path}': {e}", file=sys.stderr)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Bruk: python script.py <input_txt> <output_json>", file=sys.stderr)
    else:
        _, in_txt, out_json = sys.argv
        convert_txt_to_json(in_txt, out_json)
