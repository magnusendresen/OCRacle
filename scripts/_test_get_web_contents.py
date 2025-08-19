
import requests
from bs4 import BeautifulSoup
from datetime import date


def get_semester(d: date = None) -> tuple[int, int]:
    """
    Returnerer (årstall, semester) hvor semester er:
      1 = vårsemester (jan–jun)
      2 = høstsemester (jul–des)
    Hvis ingen dato oppgis, brukes dagens dato.
    """
    if d is None:
        d = date.today()
    
    year = d.year
    semester = 1 if d.month <= 6 else 2
    return year, semester

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

web_prefix = "https://www.ntnu.no/studier/emner/"
subject = "ingt1002"
web_suffix = "#tab=omEmnet"

web_link = web_prefix + subject.upper() + f"/{get_semester()[0]}" + web_suffix

if len(get_web_text(web_link)) < 2000:
    print(f"{web_link} now has {len(get_web_text(web_link))} symbols.")
    web_suffix = f"/{get_semester()[0]-1}#tab=omEmnet"
    print("Requested suffix.")

web_link = web_prefix + subject.upper() + web_suffix
print(f"{web_link} now has {len(get_web_text(web_link))} symbols.")