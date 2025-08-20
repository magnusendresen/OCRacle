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
    

def get_desired_topics_from_text(text: str) -> list[str]:
    if not text:
        return []
    
    print(f"Processing text for desired topics: {text}")

    try:
        response = asyncio.run(
            prompt_to_text.async_prompt_to_text(
                PROMPT_CONFIG
                + "Hva er de FAGLIGE temaene til dette emnet? "
                + "Husk at temaene skal være relevante for emnet, og ikke inneholde irrelevante eller generelle temaer. "
                + "Utelukkende faglige temaer, og ikke personlige eller urelaterte emner. "
                + "Det er som regel ikke så mange som 10 temaer i et emne, så vær presis, selv om det også varierer. "
                + "Labarbeid eller faglig kommunikasjon er absolutt ikke temaer. "
                + "Del inn temaene fra emnebeskrivelsen i en liste med temaer som er separert med et komma: "
                + text,
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


def main():
    subject_code = "ifyt1000"
    learning_goals = get_learning_goals(subject_code)
    if learning_goals:
        actual_topics = get_desired_topics_from_text(learning_goals)
        print(f"LLM found the following topics for {subject_code}: {actual_topics}")
    else:
        print(f"No learning goals found for {subject_code}")

    desired_topics = ["Mekanikk", "Fluiddynamikk", "Bølgefysikk", "Kinematikk", "Dynamikk", "Rotasjonsmekanikk"]
    print(f"Match percentage: {check_match_percentage(desired_topics, actual_topics)}%")

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
