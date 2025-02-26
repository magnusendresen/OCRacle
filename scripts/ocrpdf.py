import os
import fitz  # For handling PDF files
from google.cloud import vision
from tkinter import Tk, filedialog
from tqdm import tqdm

# ✅ Sett Google Cloud Vision API credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'ocracle-8ab6e49a7b54.json'

# ✅ Print at programmet har kontakt med Vision API
print("\n[INFO] Successfully made contact with Google Vision API!\n")

def detect_text(image_content):
    """Bruk Google Vision API for å hente ut tekst fra et bilde."""
    try:
        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=image_content)
        response = client.text_detection(image=image)
        texts = response.text_annotations

        if response.error.message:
            raise Exception(f"[ERROR] Vision API returnerte en feil: {response.error.message}")

        extracted_text = texts[0].description.replace('\n', ' ') if texts else ''
        
        if extracted_text:
            print(f"[INFO] Tekst oppdaget: {len(extracted_text.split())} ord")
        else:
            print("[WARNING] Ingen tekst oppdaget på denne siden.")
        
        return extracted_text
    except Exception as e:
        print(f"[ERROR] Feil ved tekstgjenkjenning: {e}")
        return ""

def pdf_to_images(pdf_path):
    """Konverterer PDF-sider til bilder for OCR-prosessering."""
    try:
        doc = fitz.open(pdf_path)
        images = []
        total_pages = len(doc)
        
        print(f"[INFO] PDF-en inneholder {total_pages} sider. Starter konvertering til bilder...")
        
        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=150)  # Juster DPI etter behov
            images.append(pix.tobytes("png"))  # Lagre som PNG byte array
            
        print("[INFO] Alle sider er konvertert til bilder.\n")
        return images
    except Exception as e:
        print(f"[ERROR] Kunne ikke konvertere PDF til bilder: {e}")
        return []

def main():
    """Hovedfunksjon som håndterer filvalg, PDF-konvertering og OCR-prosessering."""
    # ✅ Brukeren velger en PDF-fil
    root = Tk()
    root.withdraw()  # Skjul hovedvinduet
    pdf_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])

    if not pdf_path:
        print("[WARNING] Ingen fil valgt. Avslutter...")
        return ""

    print(f"\n[INFO] Valgt fil: {os.path.basename(pdf_path)}\n")

    # ✅ Konverter PDF til bilder
    images = pdf_to_images(pdf_path)
    if not images:
        print("[ERROR] Ingen bilder kunne genereres fra PDF-en. Avslutter...")
        return ""

    # ✅ Start tekstuttrekk fra bilder
    print("[INFO] Starter tekstuttrekk fra PDF-sidene...\n")
    
    all_text = ""
    for page_num, image_content in enumerate(tqdm(images, desc="Processing pages")):
        print(f"\n[INFO] Behandler side {page_num + 1} av {len(images)}...")
        text = detect_text(image_content)
        all_text += f"{text} "
        print(f"[INFO] Side {page_num + 1} ferdig.\n")

    print("\n[INFO] Tekstuttrekk fullført! Returnerer samlet tekst.\n")
    return all_text
