import os
import fitz  # For handling PDF files
from google.cloud import vision
from tkinter import Tk, filedialog
from tqdm import tqdm

# Set Google Cloud Vision API credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'ocracle-8ab6e49a7b54.json'

# Confirm API connection
print("\n[GOOGLE] Successfully connected to Google Vision API!\n")

def detect_text(image_content):
    """Use Google Vision API to extract text from an image."""
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
    """Convert PDF pages to images for OCR processing."""
    try:
        doc = fitz.open(pdf_path)
        images = []
        total_pages = len(doc)
        
        print(f"[INFO] PDF contains {total_pages} pages. Starting conversion to images...")
        
        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=150)  # Adjust DPI as needed
            images.append(pix.tobytes("png"))  # Store as PNG byte array
        
        print("[INFO] All pages have been converted to images.\n")
        return images
    except Exception as e:
        print(f"[ERROR] Failed to convert PDF to images: {e}")
        return []

def main():
    """Main function handling file selection, PDF conversion, and OCR processing."""
    # User selects a PDF file
    root = Tk()
    root.withdraw()  # Hide main window
    pdf_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])

    if not pdf_path:
        print("[INFO] No file selected. Exiting...")
        return ""

    print(f"\n[INFO] Selected file: {os.path.basename(pdf_path)}\n")

    # Convert PDF to images
    images = pdf_to_images(pdf_path)
    if not images:
        print("[ERROR] No images could be generated from the PDF. Exiting...")
        return ""

    # Start text extraction from images
    print("[INFO] Starting text extraction from PDF pages...\n")
    
    all_text = ""
    for page_num, image_content in enumerate(tqdm(images, desc="Processing pages")):
        print(f"\n[INFO] Processing page {page_num + 1} of {len(images)}...")
        text = detect_text(image_content)
        all_text += f"{text} "
        print(f"[INFO] Page {page_num + 1} completed.\n")

    print("\n[INFO] Text extraction complete! Returning collected text.\n")
    return all_text
