#!/usr/bin/env python3
"""Utility to run prompt tuning and generate annotated plots.

Supports running multiple tasks concurrently to speed up testing of new
formatting prompts.
"""

import argparse
import json
import asyncio
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
        "Ikke forklar for ting som kun gjelder denne oppgaven, som f.eks.:"
        " \"bruk $$ for matrisen og determinanten\", "
        " \"erstatt understrek med\", "
        " \"etter matrisen\","
        " \"skriv determinanten som\". "
        "Svar kun med selve prompten."
    )
    suggestion = prompt_to_text.prompt_to_text(
        instruction, max_tokens=200, is_num=False, max_len=1500
    )
    return suggestion if suggestion else current_prompt


async def async_refine_prompt(current_prompt: str, input_text: str, output_text: str, target: str) -> str:
    """Asynchronous wrapper for refine_prompt."""
    instruction = (
        f"{PROMPT_CONFIG} Vi prøver å formattere teksten '{input_text}'. "
        f"Den gjeldende prompten er: '{current_prompt}'. "
        f"Svaret etter denne prompten ble: '{output_text}'. "
        f"Målet er at svaret skal bli: '{target}'. "
        "Gjør ditt beste for å ikke gå for spesifikt, altså å forklare ved å bruke innholdet i akkurat denne oppgaven. "
        "Hold instruksjonene generelle slik at de kan brukes på andre oppgaver. "
        "Oppdater prompten som på nytt skal bli sendt til den samme teksten for å komme nærmere svaret. "
        "Ikke forklar for ting som kun gjelder denne oppgaven, som f.eks.:"
        " \"bruk $$ for matrisen og determinanten\", "
        " \"erstatt understrek med\", "
        " \"etter matrisen\","
        " \"skriv determinanten som\". "
        "Svar kun med selve prompten."
    )
    suggestion = await prompt_to_text.async_prompt_to_text(
        instruction, max_tokens=200, is_num=False, max_len=1500
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
        full_prompt = (
            f"{PROMPT_CONFIG}{current_prompt}\n\n"
            "Format the following text according to the instructions above. "
            "Do not include the instructions themselves in the response:\n"
            f"{input_text}"
        )
        out = prompt_to_text.prompt_to_text(
            full_prompt, max_tokens=800, is_num=False, max_len=1500
        )
        out = out or ""
        outputs.append(out)
        match = match_percent(out, target)
        matches.append(match)
        print(f"Match: {match:.2f}%\nOutput: {out}\n")

        if match >= 98:
            print("Oppnådde over 98% match, stopper tidlig.")
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


async def tune_prompts(tasks, iterations: int = 15):
    """Tune multiple prompts asynchronously.

    Args:
        tasks: list of dicts with keys 'prompt', 'input_text', 'target_text'
        iterations: number of tuning iterations

    Returns:
        tuple of lists (prompts_list, outputs_list, matches_list)
    """
    n = len(tasks)
    prompts_list = [[t["prompt"]] for t in tasks]
    outputs_list = [[] for _ in tasks]
    matches_list = [[] for _ in tasks]
    current_prompts = [t["prompt"] for t in tasks]
    best_prompts = current_prompts[:]
    best_matches = [0.0] * n

    for i in range(iterations):
        print(f"\n--- Iterasjon {i + 1} ---")
        full_prompts = [
            f"{PROMPT_CONFIG}{cp}\n\n"
            "Format the following text according to the instructions above. "
            "Do not include the instructions themselves in the response:\n"
            f"{t['input_text']}"
            for cp, t in zip(current_prompts, tasks)
        ]
        outs = await asyncio.gather(
            *[
                prompt_to_text.async_prompt_to_text(fp, max_tokens=800, is_num=False, max_len=1500)
                for fp in full_prompts
            ]
        )

        for idx, out in enumerate(outs):
            out = out or ""
            outputs_list[idx].append(out)
            match = match_percent(out, tasks[idx]["target_text"])
            matches_list[idx].append(match)
            print(f"Oppgave {idx + 1} match: {match:.2f}%")

            if match >= 98:
                continue

            if match >= best_matches[idx]:
                best_matches[idx] = match
                best_prompts[idx] = current_prompts[idx]
            else:
                current_prompts[idx] = best_prompts[idx]
                print("Match sank, går tilbake til beste prompt.")

        refined = await asyncio.gather(
            *[
                async_refine_prompt(cp, t["input_text"], o, t["target_text"])
                if m[-1] < 98 else asyncio.sleep(0, result=cp)
                for cp, t, o, m in zip(current_prompts, tasks, outs, matches_list)
            ]
        )

        for idx, new_p in enumerate(refined):
            current_prompts[idx] = new_p
            prompts_list[idx].append(new_p)
            print(f"Prompt {idx + 1} etter iterasjon {i + 1}: {new_p}")

    return prompts_list, outputs_list, matches_list


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


def plot_multiple_results(matches_list, out_file, labels=None):
    """Plot match curves for multiple tasks in one window."""
    plt.figure(figsize=(8, 4))
    if labels is None:
        labels = [f"Task {i+1}" for i in range(len(matches_list))]
    for matches, label in zip(matches_list, labels):
        x = list(range(1, len(matches) + 1))
        plt.plot(x, matches, marker="o", linestyle="-", label=label)
        for xi, yi in zip(x, matches):
            plt.annotate(f"{yi:.1f}%", (xi, yi), textcoords="offset points", xytext=(0, 5), ha="center")
    plt.xlabel("Iterasjon")
    plt.ylabel("Match %")
    plt.title("Prompt tuning")
    plt.ylim(0, 100)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_file)
    print(f"Plot lagret til {out_file}")


def main():
    parser = argparse.ArgumentParser(description="Kjør prompt tuning og lagre plott")
    parser.add_argument("--prompt", default=(
        "Format this exam task as a valid HTML string for use in a JavaScript variable. "
            "Here are a couple rules to follow: "
            "- Use <p>...</p> for all text paragraphs. "
            "- Use <h3>a)</h3>, <h3>b)</h3> etc for subtask labels if present. "
            "- Use MathJax-compatible LaTeX. "
            "- Wrap display math in $$...$$. "
            "- Wrap inline math in $...$. "
            "- Use a single backslash for LaTeX commands (e.g., \\frac, \\sqrt). "
            "- Do not use \\( ... \\) or \\[ ... \\]. "
            "- Do not double-escape backslashes. "
            "- Do not explain, summarize, or add anything outside the HTML. "
            "- Output must be usable directly inside const oppgaveTekst = `<the content here>`. "
            "- Do not add any other text or explanation. "
            "- Do not add any HTML tags outside the <p>...</p> and <h3>...</h3> tags. "
            "- Make sure that e.g. infty, omega, theta, etc. are properly formatted. "
            "- Do not write the result as you would write in a programming box, but as you would write it as clean text. "
            "- Do not include ```html or const oppgaveTekst = `` or similar. "
            "- You are allowed to make som assumptions about OCR artifacts in the text, such as \\sqrt{\\sqrt{\\sqrt most likely being an error for a single square root. "
            "- Be sure to include spaces and newlines where appropriate, the formatting is supposed to look proper.  "

            "For multiple choice tasks with text or image alternatives, also follow these rules: "
            "- Present the alternatives as an ordered list using <ol><li>. "
            "- Prefix each alternative with the corresponding letter label inside <b> tags (A, B, C, ...). "
            "- If an alternative contains an image, use <img src='PATH' alt=''> within the <li> element. "
            "- Keep the statement of the task itself outside the list in normal <p> tags. "

            "For regular tasks that require proving, calculating or explaining, also follow these rules: "
            "- Keep paragraphs short and use multiple <p> elements rather than a single long block. "
            "- Introduce each subtask with its label using <h3>a)</h3>, <h3>b)</h3> and so on. "
    ))
    parser.add_argument("--input_text", default="Du skal svare på denne oppgaven i Inspera. Du skal ikke legge ved utregninger på papir. La A = [ 1  2  0  3  8  0  0  0  1 ] Hva er determinanten til matrisen A? det(A) = ______ Avrund svaret til nærmeste heltall.")
    parser.add_argument(
        "--target_text",
        default="<p><em>Du skal svare på denne oppgaven i Inspera. Du skal ikke legge ved utregninger på papir.</em></p><p>La $$A = \\begin{bmatrix} 1 & 2 & 0 \\\\ 3 & 8 & 0 \\\\ 0 & 0 & 1 \\end{bmatrix}.$$</p><p>Hva er determinanten til matrisen <em>A</em>?</p><p>$$\\det(A) = \\boxed{\\phantom{0}}$$</p><p>Avrund svaret til nærmeste heltall.</p>",
    )
    parser.add_argument("--iterations", type=int, default=8)
    parser.add_argument("--plot", default="prompt_tuning_plot.png", help="Fil for lagring av plott")
    parser.add_argument("--json", default=None, help="Valgfri fil for å lagre detaljer som JSON")
    parser.add_argument("--tasks_file", type=Path, default=None, help="JSON-fil med flere oppgaver")
    args = parser.parse_args()

    if args.tasks_file and args.tasks_file.exists():
        tasks_data = json.loads(args.tasks_file.read_text(encoding="utf-8"))
        if isinstance(tasks_data, dict):
            tasks_iter = tasks_data.get("tasks", [])
        else:
            tasks_iter = tasks_data
        tasks = [
            {
                "prompt": t.get("prompt", args.prompt),
                "input_text": t["input_text"],
                "target_text": t["target_text"],
            }
            for t in tasks_iter[:3]
        ]
    else:
        tasks = [
            {
                "prompt": args.prompt,
                "input_text": args.input_text,
                "target_text": args.target_text,
            }
        ]

    if len(tasks) == 1:
        prompts, outputs, matches = tune_prompt(
            tasks[0]["prompt"], tasks[0]["input_text"], tasks[0]["target_text"], args.iterations
        )
        plot_results(matches, args.plot)
        if args.json:
            save_results(prompts, outputs, matches, args.json)
            print(f"Resultater lagret til {args.json}")
    else:
        prompts_list, outputs_list, matches_list = asyncio.run(tune_prompts(tasks, args.iterations))
        labels = [f"Oppgave {i+1}" for i in range(len(tasks))]
        plot_multiple_results(matches_list, args.plot, labels=labels)
        if args.json:
            data = {
                f"task_{i+1}": [
                    {"iteration": j, "prompt": p, "output": o, "match": m}
                    for j, (p, o, m) in enumerate(zip(pr, ou, ma), 1)
                ]
                for i, (pr, ou, ma) in enumerate(zip(prompts_list, outputs_list, matches_list))
            }
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Resultater lagret til {args.json}")


if __name__ == "__main__":
    main()
