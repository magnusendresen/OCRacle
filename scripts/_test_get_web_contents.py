import requests
from bs4 import BeautifulSoup
from datetime import date

def get_web_text(url: str) -> None:
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for element in soup(["script", "style"]):
            element.decompose()

        # Iterer over alle divs med id
        for div in soup.find_all("div", id=True):
            text = div.get_text(separator=" ", strip=True)
            if not text:  # hopp over tomme divs
                continue
            print(f"Div id='{div.get('id')}': len={len(text)}")

    except Exception as e:
        print(f"Feil ved henting av {url}: {e}")

def get_web_result_from_subject_code(subject_code):
    subject_code = str(subject_code.upper())
    year = str(date.today().year)
    web_prefix = "https://www.ntnu.no/studier/emner/"
    web_suffix = f"/{year}#tab=omEmnet"

    web_url = web_prefix + subject_code + web_suffix
    return get_web_text(web_url)


get_web_result_from_subject_code("ifyt1000")
