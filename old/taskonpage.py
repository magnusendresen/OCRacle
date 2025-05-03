import os
import fitz
import asyncio
from google.cloud import vision
from pathlib import Path
import sys
import prompttotext

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

# Load Google Vision credentials
json_path = os.getenv("OCRACLE_JSON_PATH")
if not json_path or not os.path.exists(json_path):
    raise FileNotFoundError(f"[ERROR] Invalid OCRACLE_JSON_PATH: {json_path}")
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = json_path

# Constants
target_pdf = 'MEKT1101H24.pdf'
target_page = 8  # adjust as needed

async def which_task_on_page(pdf_path: str, page_number: int) -> None:
    # Convert page to image
    doc = fitz.open(pdf_path)
    if page_number < 1 or page_number > len(doc):
        print(f"Error: Page {page_number} out of range")
        return
    pix = doc.load_page(page_number - 1).get_pixmap(dpi=300)
    img_bytes = pix.tobytes("png")

    # OCR
    client = vision.ImageAnnotatorClient()
    response = client.text_detection(image=vision.Image(content=img_bytes))
    if response.error.message:
        raise RuntimeError(response.error.message)
    text = response.text_annotations[0].description.replace('\n', ' ') if response.text_annotations else ''

    # Build prompt
    prompt = (
        "DO AS YOU ARE TOLD AND RESPOND ONLY WITH WHAT IS ASKED FROM YOU. "
        "Respond ONLY with the single task number that appears on this page as an integer (e.g., 1, 2, 3). "
        "If there are no task numbers, respond with 0. "
        "If there are multiple tasks, respond with each task number on a new line. "
        "If there are subtasks (e.g. a, b, i, ii, etc.), respond with the main task number only. "
        + text
    )

    # Get task numbers
    result = await prompttotext.async_prompt_to_text(
        prompt,
        max_tokens=50,
        isNum=False,
        maxLen=100
    )
    print(result)

if __name__ == '__main__':
    asyncio.run(which_task_on_page(target_pdf, target_page))
