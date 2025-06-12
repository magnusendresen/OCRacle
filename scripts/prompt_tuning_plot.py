#!/usr/bin/env python3
"""Utility to run prompt tuning and generate an annotated plot."""

import argparse
import json
from pathlib import Path
from difflib import SequenceMatcher
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import prompt_to_text
from project_config import PROMPT_CONFIG


def match_percent(a: str, b: str) -> float:
    """Return percent similarity between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() * 100


def refine_prompt(current_prompt: str, input_text: str, output_text: str, target: str) -> str:
    """Use DeepSeek to suggest a better prompt."""
    instruction = (
        f"{PROMPT_CONFIG} Vi prøver å formattere teksten '{input_text}'. "
        f"Den gjeldende prompten er: '{current_prompt}'. "
        f"Svaret etter denne prompten ble: '{output_text}'. "
        f"Målet er at svaret skal bli: '{target}'. "
        "Gjør ditt beste for å ikke gå for spesifikt, altså å forklare ved å bruke innholdet i akkurat denne oppgaven. "
        "Hold instruksjonene generelle slik at de kan brukes på andre oppgaver. "
        "Oppdater prompten som på nytt skal bli sendt til den samme teksten for å komme nærmere svaret. "
        "Svar kun med selve prompten."
    )
    suggestion = prompt_to_text.prompt_to_text(
        instruction, max_tokens=200, isNum=False, maxLen=1500
    )
    return suggestion if suggestion else current_prompt


def tune_prompt(initial_prompt: str, input_text: str, target: str, iterations: int = 15):
    prompts = [initial_prompt]
    outputs = []
    matches = []
    current_prompt = initial_prompt
    best_prompt = initial_prompt
    best_match = 0.0

    for i in range(iterations):
        print(f"\n--- Iterasjon {i + 1} ---")
        full_prompt = f"{PROMPT_CONFIG}{current_prompt}\n\n{input_text}"
        out = prompt_to_text.prompt_to_text(
            full_prompt, max_tokens=800, isNum=False, maxLen=1500
        )
        out = out or ""
        outputs.append(out)
        match = match_percent(out, target)
        matches.append(match)
        print(f"Match: {match:.2f}%\nOutput: {out}\n")

        if match >= 95:
            print("Oppnådde over 95% match, stopper tidlig.")
            prompts.append(current_prompt)
            break

        if match >= best_match:
            best_match = match
            best_prompt = current_prompt
        else:
            current_prompt = best_prompt
            print("Match sank, går tilbake til beste prompt.")

        current_prompt = refine_prompt(current_prompt, input_text, out, target)
        prompts.append(current_prompt)
        print(f"Prompt etter iterasjon {i + 1}: {current_prompt}")

    return prompts, outputs, matches


def save_results(prompts, outputs, matches, path):
    """Save tuning results as JSON."""
    data = [
        {"iteration": i, "prompt": p, "output": o, "match": m}
        for i, (p, o, m) in enumerate(zip(prompts, outputs, matches), 1)
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def plot_results(matches, out_file):
    """Plot match percentages with annotations."""
    plt.figure(figsize=(8, 4))
    x = list(range(1, len(matches) + 1))
    plt.plot(x, matches, marker="o", linestyle="-", color="tab:blue")
    for xi, yi in zip(x, matches):
        plt.annotate(f"{yi:.1f}%", (xi, yi), textcoords="offset points", xytext=(0, 5), ha="center")
    plt.xlabel("Iterasjon")
    plt.ylabel("Match %")
    plt.title("Prompt tuning")
    plt.ylim(0, 100)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    plt.savefig(out_file)
    print(f"Plot lagret til {out_file}")


def main():
    parser = argparse.ArgumentParser(description="Kjør prompt tuning og lagre plott")
    parser.add_argument("--prompt", default="Formatter oppgaven til html med mathjax.")
    parser.add_argument("--input_text", default="Du skal svare på denne oppgaven i Inspera. Du skal ikke legge ved utregninger på papir. La A = [ 1  2  0  3  8  0  0  0  1 ] Hva er determinanten til matrisen A? det(A) = ______ Avrund svaret til nærmeste heltall.")
    parser.add_argument(
        "--target_text",
        default="<p><em>Du skal svare på denne oppgaven i Inspera. Du skal ikke legge ved utregninger på papir.</em></p><p>La $$A = \\begin{bmatrix} 1 & 2 & 0 \\\\ 3 & 8 & 0 \\\\ 0 & 0 & 1 \\end{bmatrix}.$$</p><p>Hva er determinanten til matrisen <em>A</em>?</p><p>$$\\det(A) = \\boxed{\\phantom{0}}$$</p><p>Avrund svaret til nærmeste heltall.</p>",
    )
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--plot", default="prompt_tuning_plot.png", help="Fil for lagring av plott")
    parser.add_argument("--json", default=None, help="Valgfri fil for å lagre detaljer som JSON")
    args = parser.parse_args()

    prompts, outputs, matches = tune_prompt(
        args.prompt, args.input_text, args.target_text, args.iterations
    )
    plot_results(matches, args.plot)

    if args.json:
        save_results(prompts, outputs, matches, args.json)
        print(f"Resultater lagret til {args.json}")


if __name__ == "__main__":
    main()
