import os
import fitz  # For handling PDF files
from google.cloud import vision
from tkinter import Tk, filedialog
from tqdm import tqdm

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

    return texts[0].description.replace('\n', ' ') if texts else ''

def pdf_to_images(pdf_path):
    """Convert PDF pages to images."""
    doc = fitz.open(pdf_path)
    images = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=150)  # Adjust DPI as needed
        images.append(pix.tobytes("png"))  # Save directly as PNG byte array
    return images

def main():
    # Prompt user to select a PDF file
    root = Tk()
    root.withdraw()  # Hide the root window
    pdf_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
    if not pdf_path:
        print("No file selected.")
        return ""

    # Convert PDF pages to images
    images = pdf_to_images(pdf_path)

    # Extract text from each image and combine into a single string
    all_text = ""
    for image_content in tqdm(images, desc="Processing pages"):
        text = detect_text(image_content)
        all_text += f"{text} "

    return all_text
