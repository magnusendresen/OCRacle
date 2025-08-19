
import requests
from bs4 import BeautifulSoup
from datetime import date

def get_web_text(url: str) -> str:
    try:
        # Hent HTML
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # kast exception ved feil
        
        # Parse med BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Fjern script- og style-elementer
        for element in soup(["script", "style"]):
            element.decompose()
        
        # Hent all tekst
        text = soup.get_text(separator="\n")
        
        # Rens opp whitespace
        lines = (line.strip() for line in text.splitlines())
        text = "\n".join(line for line in lines if line)
        
        return text
    
    except Exception as e:
        return f"Feil ved henting av {url}: {e}"

def get_web_result_from_subject_code(subject_code):
    subject_code = str(subject_code.upper())
    year = str(date.today().year)
    web_prefix = "https://www.ntnu.no/studier/emner/"
    web_suffix = f"/{year}#tab=omEmnet"

    web_url = web_prefix + subject_code + web_suffix

    return get_web_text(web_url)


print(len(get_web_result_from_subject_code("ifyt1000")))

