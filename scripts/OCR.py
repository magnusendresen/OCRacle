import os
import fitz  # For handling PDF files
from google.cloud import vision
from tkinter import Tk, filedialog
from PIL import Image
import io
from tqdm import tqdm
import regex as re

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
        pix = page.get_pixmap(dpi=200)  # Increase DPI for better OCR accuracy
        images.append(pix.tobytes("png"))  # Save directly as PNG byte array
    return images

import re

import re

import re

def normalize_ocr_result(text):
    """
    Normalize OCR results for processing into KaTeX math expressions.
    - Removes extraneous whitespace.
    - Converts special symbols to LaTeX-compatible equivalents.
    - Ensures proper formatting of math components.

    Args:
        text (str): The raw OCR output from Google Vision.

    Returns:
        str: The normalized text.
    """
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
    # For instance, math ranges like "1 to n" -> "1 \dots n"
    text = re.sub(r'(\d+)\s*to\s*(\w+)', r'\1 \\dots \2', text, flags=re.IGNORECASE)

    # Ensure spaces are preserved around operators
    text = re.sub(r'(?<!\\)([+\-*/^=()])', r' \1 ', text)
    text = re.sub(r'\s+', ' ', text).strip()  # Normalize excess spaces again

    return text


def main():
    # Prompt user to select a PDF file
    root = Tk()
    root.withdraw()  # Hide the root window
    pdf_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
    if not pdf_path:
        print("No file selected.")
        return

    # Convert PDF pages to images
    images = pdf_to_images(pdf_path)

    # Extract text from each image and save to a file
    with open('output.txt', 'w', encoding='utf-8') as output_file:
        for image_content in tqdm(images, desc="Processing pages"):
            text = detect_text(image_content)
            text = normalize_ocr_result(text)
            output_file.write(text + '\n')

    print("Text extraction complete. Check 'output.txt' for the results.")

if __name__ == "__main__":
    main()