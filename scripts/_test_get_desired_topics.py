import requests
from bs4 import BeautifulSoup
from datetime import date
from project_config import *


import asyncio
import prompt_to_text
from difflib import SequenceMatcher


def get_learning_goals(subject_code: str) -> str:
    try:
        subject_code = subject_code.upper()
        year = str(date.today().year)
        web_url = f"https://www.ntnu.no/studier/emner/{subject_code}/{year}#tab=omEmnet"

        response = requests.get(web_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        div = soup.find("div", id="learning-goal-toggler")
        if not div:
            return ""
    

        return div.get_text(separator=" ", strip=True)

    except Exception as e:
        return f"Feil ved henting av {subject_code}: {e}"
    

def get_desired_topics_from_text(text: str, prompt: str) -> list[str]:
    """Return topics produced by the current prompt.

    `prompt` contains the instruction segment that will be appended to
    `PROMPT_CONFIG` together with the input text. This allows iterative
    refinement of the instruction while always enforcing `PROMPT_CONFIG`.
    """
    if not text:
        return []

    try:
        response = asyncio.run(
            prompt_to_text.async_prompt_to_text(
                PROMPT_CONFIG + prompt + text,
                max_tokens=1000,
                is_num=False,
                max_len=1000,
            )
        )
        if not response:
            return []
        return [t.strip().upper() for t in response.split(",") if t.strip()]
    except Exception as e:
        return [f"Feil ved behandling av tekst: {e}"]


def refine_prompt(current_prompt: str, input_text: str, output_topics: list[str], desired_topics: list[str]) -> str:
    """Ask the LLM to suggest a better prompt based on current results."""

    instruction = (
        PROMPT_CONFIG
        + "Vi prøver å finne faglige temaer fra teksten. "
        + f"Den gjeldende prompten er: '{current_prompt}'. "
        + f"Svaret ble: '{', '.join(output_topics)}'. "
        + f"Målet er: '{', '.join(desired_topics)}'. "
        + "Oppdater prompten slik at neste forsøk kommer nærmere målet. "
        + "Gjerne gjør drastiske endringer for å forbedre resultatet. "
        + "Du har ikke lov  til å fortelle i prompten nøyaktig hvilke temaer som er ønsket. "
        + "Svar kun med selve prompten."
    )
    suggestion = asyncio.run(
        prompt_to_text.async_prompt_to_text(
            instruction, max_tokens=200, is_num=False, max_len=1500
        )
    )
    return suggestion if suggestion else current_prompt


def tune_topic_prompt(initial_prompt: str, text: str, desired_topics: list[str], iterations: int = 5):
    """Iteratively refine the prompt to maximise topic match percentage."""

    current_prompt = initial_prompt
    best_prompt = initial_prompt
    best_topics: list[str] = []
    best_match = 0.0

    for i in range(iterations):
        actual_topics = get_desired_topics_from_text(text, current_prompt)
        match = check_match_percentage(desired_topics, actual_topics)
        print(f"Iterasjon {i + 1}: match {match:.2f}%")
        print(f"Desired topics: {desired_topics}")
        print(f"Actual topics: {actual_topics}")

        if match > best_match:
            best_match = match
            best_prompt = current_prompt
            best_topics = actual_topics
        else:
            current_prompt = best_prompt

        if match >= 98:
            break

        current_prompt = refine_prompt(current_prompt, text, actual_topics, desired_topics)

    return best_prompt, best_topics, best_match


def main():
    subject_code = "ingt1002"
    learning_goals = get_learning_goals(subject_code)
    desired_topics = [
        "Funksjoner av flere variabler",
        "Taylorrekker",
        "Partielle deriverte",
        "Fourierrekker",
        "Konvolusjon",
        "DFT",
        "IDFT"
    ]

    if learning_goals:
        initial_prompt = (
            "Hva er de FAGLIGE temaene til dette emnet? "
            "Husk at temaene skal være relevante for emnet, og ikke inneholde irrelevante eller generelle temaer. "
            "Utelukkende faglige temaer, og ikke personlige eller urelaterte emner. "
            "Det er som regel ikke så mange som 10 temaer i et emne, så vær presis, selv om det også varierer. "
            "Labarbeid eller faglig kommunikasjon er absolutt ikke temaer. "
            "Del inn temaene fra emnebeskrivelsen i en liste med temaer som er separert med et komma: "
        )
        best_prompt, actual_topics, best_match = tune_topic_prompt(
            initial_prompt, learning_goals, desired_topics
        )
        print(f"LLM found the following topics for {subject_code}: {actual_topics}")
        print(f"Best prompt: {best_prompt}")
        print(f"Match percentage: {best_match}%")
    else:
        print(f"No learning goals found for {subject_code}")

def check_match_percentage(desired_topics: list[str], actual_topics: list[str]) -> float:
    if not desired_topics or not actual_topics:
        return 0.0
    
    desired_topics_upper = [topic.upper() for topic in desired_topics]
    actual_topics_upper = [topic.upper() for topic in actual_topics]
    def fuzzy_match(a, b, threshold=0.5):
        return SequenceMatcher(None, a, b).ratio() >= threshold

    match_count = 0
    for desired in desired_topics_upper:
        if any(fuzzy_match(desired, actual, threshold=0.5) for actual in actual_topics_upper):
            match_count += 1
    return (match_count / len(desired_topics)) * 100 if desired_topics else 0.0

if __name__ == "__main__":
    main()
