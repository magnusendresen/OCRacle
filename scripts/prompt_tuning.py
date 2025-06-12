import argparse
from difflib import SequenceMatcher
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import prompt_to_text
from project_config import PROMPT_CONFIG


def match_percent(a: str, b: str) -> float:
    """Return percent similarity between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() * 100


def refine_prompt(current_prompt: str, input_text: str, output_text: str, target: str) -> str:
    """Use DeepSeek to suggest a better prompt."""
    instruction = (
        f"{PROMPT_CONFIG}Vi prøver å løse teksten '{input_text}'. "
        f"Den gjeldende prompten er: '{current_prompt}'. "
        f"Svaret etter forrige denne prompten ble: '{output_text}'. "
        f"Målet er at svaret skal bli: '{target}'. "
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
        current_prompt = refine_prompt(current_prompt, input_text, out, target)
        prompts.append(current_prompt)

    plt.figure()
    plt.plot(range(1, iterations + 1), matches, marker="o")
    plt.xlabel("Iterasjon")
    plt.ylabel("Match %")
    plt.title("Prompt tuning")
    plt.ylim(0, 100)
    plt.grid(True)
    plot_path = "prompt_tuning_plot.png"
    plt.savefig(plot_path)
    print(f"Plot lagret til {plot_path}")

    return prompts, outputs, matches


def main():
    parser = argparse.ArgumentParser(description="Automatisk prompttuning")
    parser.add_argument("--prompt", default="Løs denne oppgaven")
    parser.add_argument("--input_text", default="x**2 + 8x + 16 = 0")
    parser.add_argument(
        "--target_text",
        default=(
            "Vi benytter abc-formelen, som brukes til å løse andregradsligninger på formen ax^2 + bx + c = 0. "
            "Her setter vi a=1, b=8 og c=16. "
            "Formelen er: x = (-b ± sqrt(b^2 - 4ac)) / (2a). "
            "Vi regner først ut diskriminanten: D = b^2 - 4ac = 8^2 - 4*1*16 = 64 - 64 = 0. "
            "Siden diskriminanten er 0, finnes det én løsning: x = -b / (2a) = -8 / 2 = -4. "
            "Løsningen på ligningen er altså x = -4."
        ),
    )
    parser.add_argument("--iterations", type=int, default=10)
    args = parser.parse_args()

    tune_prompt(args.prompt, args.input_text, args.target_text, args.iterations)


if __name__ == "__main__":
    main()
