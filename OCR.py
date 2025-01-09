import os
import fitz  # PyMuPDF
from google.cloud import vision
from tkinter import Tk, filedialog
from PIL import Image
import io
from tqdm import tqdm

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'ocracle-8ab6e49a7b54.json'

def detect_text(image_content):
    """Detects text in the image content."""
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_content)
    response = client.text_detection(image=image)
    texts = response.text_annotations

    if response.error.message:
        raise Exception(f'{response.error.message}')

    return texts[0].description if texts else ''

def pdf_to_images(pdf_path):
    """Converts each page of the PDF to an image."""
    doc = fitz.open(pdf_path)
    images = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        images.append(img_byte_arr.getvalue())
    return images

def main():
    # Open file dialog to select PDF
    root = Tk()
    root.withdraw()  # Hide the root window
    pdf_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
    if not pdf_path:
        print("No file selected.")
        return

    # Convert PDF to images
    images = pdf_to_images(pdf_path)

    # Extract text from each image and write to a text file
    with open('output.txt', 'w', encoding='utf-8') as output_file:
        for image_content in tqdm(images, desc="Processing pages"):
            text = detect_text(image_content)
            output_file.write(text + '\n')

    print("Text extraction complete. Check 'output.txt' for results.")

if __name__ == "__main__":
    main()