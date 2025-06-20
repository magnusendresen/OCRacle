import os
import fitz  # For PDF-håndtering
import asyncio
from google.cloud import vision
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

