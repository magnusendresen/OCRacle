import os
import fitz  # For PDF-håndtering
import asyncio
from google.cloud import vision
from tkinter import Tk, filedialog
from tqdm import tqdm

# Sett Google Cloud Vision API credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'ocracle-8ab6e49a7b54.json'

print("\n[GOOGLE] Successfully connected to Google Vision API!\n")

def detect_text(image_content):
    """Bruk Google Vision API for å trekke ut tekst fra et bilde."""
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
    """Konverter PDF-sider til bilder (PNG) for OCR-prosessering."""
    try:
        doc = fitz.open(pdf_path)
        images = []
        total_pages = len(doc)
        
        print(f"[INFO] PDF contains {total_pages} pages. Starting conversion to images...")
        
        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=300)  # Juster DPI etter behov
            images.append(pix.tobytes("png"))
        
        print("[INFO] All pages have been converted to images.\n")
        return images
    except Exception as e:
        print(f"[ERROR] Failed to convert PDF to images: {e}")
        return []

async def async_detect_text(image_content):
    """Asynkron wrapper for detect_text ved hjelp av asyncio.to_thread."""
    return await asyncio.to_thread(detect_text, image_content)

async def main_async():
    """Asynkron hovedfunksjon for å la brukeren velge en PDF-fil, konvertere den til bilder og hente ut tekst asynkront."""
    root = Tk()
    root.withdraw()  # Skjul hovedvinduet
    pdf_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
    
    if not pdf_path:
        print("[INFO] No file selected. Exiting...")
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
