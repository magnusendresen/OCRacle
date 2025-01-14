import os
import fitz  # For handling PDF files
from google.cloud import vision
from tkinter import Tk, filedialog
from PIL import Image
import io
from tqdm import tqdm
import regex as re
from difflib import SequenceMatcher

# Set Google Cloud Vision API credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'ocracle-8ab6e49a7b54.json'

def detect_text(image_content):
    """Use Google Vision API to extract text from an image."""
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_content)
    response = client.text_detection(image=image)
    texts = response.text_annotations

    if response.error.message:
        raise Exception(f'Error from Vision API: {response.error.message}')

    return texts[0].description if texts else ''

def pdf_to_images(pdf_path):
    """Convert PDF pages to images."""
    doc = fitz.open(pdf_path)
    images = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=150)  # Reduced DPI for faster processing
        images.append(pix.tobytes("png"))  # Save directly as PNG byte array
    return images

def normalize_ocr_result(text):
    # Remove unnecessary whitespace
    text = re.sub(r'\s+', ' ', text.strip())

    # Replace common OCR misinterpretations
    replacements = {
        '−': '-',  # Replace Unicode minus with standard hyphen
        '×': '\\times',  # Replace multiplication symbol with LaTeX command
        '÷': '\\div',  # Replace division symbol with LaTeX command
        '=': ' = ',  # Add spacing around equals for clarity
        '∞': '\\infty',  # Replace infinity symbol
        '∑': '\\sum',  # Replace summation symbol
        '√': '\\sqrt',  # Replace square root symbol
        'π': '\\pi',  # Replace pi symbol
        '^': '**',  # Replace caret with exponentiation for Python
    }
    for symbol, latex in replacements.items():
        text = text.replace(symbol, latex)

    # Handle fractions (e.g., 1/2 -> \frac{1}{2})
    text = re.sub(r'(\d+)\s*/\s*(\d+)', r'\\frac{\1}{\2}', text)

    # Add curly braces around subscripts/superscripts for KaTeX
    text = re.sub(r'_(\w+)', r'_{\1}', text)  # Subscripts
    text = re.sub(r'\^(\w+)', r'^{\1}', text)  # Superscripts

    # Handle specific patterns (optional, based on your use case)
    # For instance, math ranges like "1 to n" -> "1 \\dots n"
    text = re.sub(r'(\d+)\s*to\s*(\w+)', r'\1 \\dots \2', text, flags=re.IGNORECASE)

    # Ensure spaces are preserved around operators
    text = re.sub(r'(?<!\\)([+\-*/^=()])', r' \1 ', text)
    text = re.sub(r'\s+', ' ', text).strip()  # Normalize excess spaces again

    return text

def is_valid_task(text_segment, min_length=60):
    """Determine if a text segment is likely a valid task based on its length."""
    return len(text_segment) > min_length

def is_excluded_page(text, exclusion_keywords, min_match=12):
    """Check if the page should be excluded based on keywords and match count."""
    match_count = sum(1 for keyword in exclusion_keywords if keyword.lower() in text.lower())
    return match_count >= min_match

def is_excluded_task(task, exclusion_keywords, min_match=5):
    """Check if a task should be excluded based on keywords and match count."""
    match_count = sum(1 for keyword in exclusion_keywords if keyword.lower() in task.lower())
    return match_count >= min_match

def extract_tasks(text):
    """
    Extracts tasks from the given text based on the keyword 'Oppgave' and its variations.

    Parameters:
        text (str): The entire content of the document as a string.

    Returns:
        list: A list of valid task sections as strings.
    """
    # Define a regex pattern to match "Oppgave" followed by a space and optional digits or delopgaver like 1(a)
    pattern = re.compile(r"((Oppgave|oppgave|Oppg\u00e5ve|oppg\u00e5ve)\s*\d*|\d+\([a-zA-Z]\)|maks\s*poeng[:\s]*\d+)")

    # Find all matches for the pattern
    matches = [match.start() for match in pattern.finditer(text)]

    # If no tasks are found, return the entire text as a single task
    if not matches:
        return [text] if is_valid_task(text) else []

    # Split the text into tasks using the matched indices
    tasks = []
    for i in range(len(matches)):
        start = matches[i]
        end = matches[i + 1] if i + 1 < len(matches) else len(text)
        task = text[start:end].strip()

        # Only include tasks that start with "Oppgave X" or "maks poeng"
        if re.match(r'(Oppgave|oppgave|Oppg\u00e5ve|oppg\u00e5ve)\s*\d+|maks\s*poeng[:\s]*\d+', task):
            if is_valid_task(task):
                tasks.append(task)

    return tasks

def main():
    # Prompt user to select a PDF file
    root = Tk()
    root.withdraw()  # Hide the root window
    pdf_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
    if not pdf_path:
        print("No file selected.")
        return

    # Keywords for excluding pages and tasks
    exclusion_keywords = [
        "eksamen", "kandidatnummer", "sensur", "hjelpemiddel", 
        "informasjon", "vurdering", "beskjeder", "beskjedar",
        "varslinger", "varslingar", "sensurfrist", "sensurfristar",
        "varsel", "varselar", "sensurvarsel", "sensurvarselar",
        "fagspecifik", "fagspesifikk", "oppgavesettet", "oppg\u00e5vesettet",
        "levering", "leveringar", "poeng", "vektig", "sensurtidspunkt",
        "kalkulator", "tillatne", "h\u00e5ndteikningar", "h\u00e5ndtegninger",
        "kontaktperson", "kontaktinformasjon", "direkte feil", "oppgavefrister",
        "tillatelse", "fritekstfelt", "gir maksimalt", "gje maksimalt",
        "maksimalt", "poeng", "formelark", "formelarket", "formel",
        "inspera", "assessment", "eksamensopp\u00e5ve", "eksamensoppgave"
    ]


    # Convert PDF pages to images
    images = pdf_to_images(pdf_path)

    # Extract text from each image and save to a file
    with open('output.txt', 'w', encoding='utf-8') as output_file:
        for page_num, image_content in enumerate(tqdm(images, desc="Processing pages")):
            text = detect_text(image_content)
            text = normalize_ocr_result(text)
            if is_excluded_page(text, exclusion_keywords):
                print(f"\nPage {page_num + 1} removed.")
                continue

            tasks = extract_tasks(text)
            valid_tasks = []
            for task_num, task in enumerate(tasks, start=1):
                if is_excluded_task(task, exclusion_keywords):
                    print(f"\nTask {task_num} on Page {page_num + 1} removed.")
                elif is_valid_task(task):
                    valid_tasks.append(task)

            for task in valid_tasks:
                output_file.write(task + '\n\n\n')

if __name__ == "__main__":
    main()
