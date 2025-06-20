import os
import fitz  # For PDF-håndtering
import asyncio
from google.cloud import vision
from tqdm import tqdm
import sys
from pathlib import Path
from project_config import *
import json

# Sørg for UTF-8 utskrift i terminalen
sys.stdout.reconfigure(encoding='utf-8')

# Hent sti til Google API-nøkkelfilen fra miljøvariabel
json_path = os.getenv("OCRACLE_JSON_PATH")
if not json_path or not os.path.exists(json_path):
    raise FileNotFoundError(f"[ERROR] JSON path not found or invalid: {json_path}")

# Sett Google Cloud Vision API credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = json_path
print(f"\n[GOOGLE] Successfully connected to Google Vision API using:\n{json_path}\n")

# Definer sti for progress.json and empty file at startup
with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
    json.dump({}, f)

def _read_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _write_progress(data: dict) -> None:
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[ERROR] Could not write progress file: {e}")


def update_progress_line1(value: str = "1"):
    """Update key 1 in progress.json with the given value."""
    data = _read_progress()
    data["1"] = value
    _write_progress(data)
    print(f"[STATUS] | Updated key 1 of {PROGRESS_FILE} with '{value}'")

def update_progress_line2(value: str) -> None:
    """Update key 2 in progress.json with the given value."""
    data = _read_progress()
    data["2"] = value
    _write_progress(data)
    print(f"[STATUS] | Updated key 2 of {PROGRESS_FILE} with '{value}'")

# Sett opp Google Vision API-status (linje 1)
update_progress_line1("1")

def detect_text(image_content):
    try:
        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=image_content)
        response = client.text_detection(image=image)
        texts = response.text_annotations

        if response.error.message:
            raise Exception(f"[ERROR] Vision API returned an error: {response.error.message}")

        extracted_text = texts[0].description.replace('\n', ' ') if texts else ''
        if extracted_text:
            print(f"[INFO] Text detected: {len(extracted_text.split())} words")
        else:
            print("[WARNING] No text detected on this page.")

        return extracted_text
    except Exception as e:
        print(f"[ERROR] Text recognition failed: {e}")
        return ""

def pdf_to_images(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        images = []
        total_pages = len(doc)
        print(f"[INFO] PDF contains {total_pages} pages. Starting conversion to images...")

        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=300)
            images.append(pix.tobytes("png"))

        print("[INFO] All pages have been converted to images.\n")
        return images
    except Exception as e:
        print(f"[ERROR] Failed to convert PDF to images: {e}")
        return []

async def process_image(index, image, ocr_progress):
    """
    Utfører OCR på én side, oppdaterer global progress og skriver status til linje 2.
    """
    result = await asyncio.to_thread(detect_text, image)
    ocr_progress[index] = 1  # Merk at siden er ferdig prosessert
    progress_str = "".join(str(x) for x in ocr_progress)
    update_progress_line2(progress_str)
    return result

async def main_async():
    # Les PDF-sti fra dir.json
    if not DIR_FILE.exists():
        print(f"[ERROR] Could not find dir.json at {DIR_FILE}")
        return ""
    try:
        with open(DIR_FILE, "r", encoding="utf-8") as f:
            dir_data = json.load(f)
    except Exception as e:
        print(f"[ERROR] Could not read dir.json: {e}")
        return ""

    pdf_path = dir_data.get("exam", "").strip()
    path_obj = Path(pdf_path)
    if not path_obj.is_absolute():
        candidate = PDF_DIR / path_obj
        if candidate.exists():
            path_obj = candidate
    if not path_obj.exists():
        print(f"[ERROR] File does not exist: {path_obj}")
        return ""
    pdf_path = str(path_obj)

    print(f"\n[INFO] Selected file: {os.path.basename(pdf_path)}\n")

    images = pdf_to_images(pdf_path)
    if not images:
        print("[ERROR] No images could be generated from the PDF. Exiting...")
        return ""

    # Initialiser en liste for OCR-status: 0 = ikke prosessert, 1 = prosessert
    ocr_progress = [0] * len(images)
    update_progress_line2("".join(str(x) for x in ocr_progress))  # Oppdaterer med initial status

    print("[INFO] Starting text extraction from PDF pages...\n")

    tasks = [
        asyncio.create_task(process_image(i, image, ocr_progress))
        for i, image in enumerate(images)
    ]
    results = await asyncio.gather(*tasks)

    # Lag en enkelt tekststreng med tydelig markering av hver side
    all_text = ""
    for idx, page_text in enumerate(results, start=1):
        all_text += f"\n\n=== PAGE {idx} ===\n\n{page_text}"

    print("\n[INFO] Text extraction complete! Returning collected text.\n")
    return all_text


def main():
    return asyncio.run(main_async())
