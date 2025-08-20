import requests
from bs4 import BeautifulSoup
from datetime import date
from project_config import *


import prompt_to_text


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
    

def get_desired_topics_from_text(text: str) -> str:
    if not text:
        return ""

    # Use the prompt_to_text module to process the text and extract topics
    try:
        response = (
            prompt_to_text.async_prompt_to_text(
                PROMPT_CONFIG + "Del inn temaene fra denne teksten i en liste med temaer som er separert med et komma: " + text,
                max_tokens=1000,
                is_num=False,
                max_len=1000,
            )
        ).strip().upper()
        return response
    except Exception as e:
        return f"Feil ved behandling av tekst: {e}"


def main():
    subject_code = "tdt4102"
    learning_goals = get_learning_goals(subject_code)
    if learning_goals:
        desired_topics = get_desired_topics_from_text(learning_goals)
        print(f"Desired topics for {subject_code}: {desired_topics}")
    else:
        print(f"No learning goals found for {subject_code}")

if __name__ == "__main__":
    main()