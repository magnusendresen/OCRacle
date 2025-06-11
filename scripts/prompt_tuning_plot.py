#!/usr/bin/env python3
"""Utility to run prompt tuning and generate an annotated plot."""

import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from prompt_tuning import tune_prompt


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
    parser.add_argument("--prompt", default="Løs denne oppgaven")
    parser.add_argument("--input_text", default="x**2 + 8x + 16 = 0")
    parser.add_argument(
        "--target_text",
        default="Vi benytter abc-formelen og setter a=1, b=8 og c=16.",
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
