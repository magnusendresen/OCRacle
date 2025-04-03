import os
import fitz  # For PDF-håndtering
import asyncio
from google.cloud import vision
from pathlib import Path
from tqdm import tqdm
import sys

# Sørg for UTF-8 utskrift i terminalen
sys.stdout.reconfigure(encoding='utf-8')

# Hent sti til Google API-nøkkelfilen fra miljøvariabel
json_path = os.getenv("OCRACLE_JSON_PATH")
if not json_path or not os.path.exists(json_path):
    raise FileNotFoundError(f"[ERROR] JSON path not found or invalid: {json_path}")

# Sett Google Cloud Vision API credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = json_path
print(f"\n[GOOGLE] Successfully connected to Google Vision API using:\n{json_path}\n")

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

async def async_detect_text(image_content):
    return await asyncio.to_thread(detect_text, image_content)

async def main_async():
    # Les PDF-sti fra dir.txt
    script_dir = Path(__file__).resolve().parent
    dir_txt = script_dir / "dir.txt"

    if not dir_txt.exists():
        print(f"[ERROR] Could not find dir.txt at {dir_txt}")
        return ""

    pdf_path = dir_txt.read_text(encoding="utf-8").strip()

    if not os.path.exists(pdf_path):
        print(f"[ERROR] File does not exist: {pdf_path}")
        return ""

    print(f"\n[INFO] Selected file: {os.path.basename(pdf_path)}\n")

    images = pdf_to_images(pdf_path)
    if not images:
        print("[ERROR] No images could be generated from the PDF. Exiting...")
        return ""

    print("[INFO] Starting text extraction from PDF pages...\n")

    tasks = [async_detect_text(image) for image in images]
    results = await asyncio.gather(*tasks)

    all_text = " ".join(results)
    print("\n[INFO] Text extraction complete! Returning collected text.\n")
    return all_text

def main():
    return asyncio.run(main_async())
