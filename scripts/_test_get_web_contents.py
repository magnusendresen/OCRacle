import requests
from bs4 import BeautifulSoup
from datetime import date

def get_learning_goals(subject_code: str) -> str:
    try:
        subject_code = subject_code.upper()
        if subject_code[-5].upper() == 'X':
            subject_code = subject_code[: -5] + 'T' + subject_code[-4:]
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


print(get_learning_goals("ifyx1000"))
