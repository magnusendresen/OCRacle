import os
import logging
import tkinter as tk
from tkinter import filedialog
import fitz  # PyMuPDF
from PIL import Image
import pytesseract

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def select_pdf_and_extract_images():
    try:
        # Ask the user to select a PDF file
        pdf_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if not pdf_path:
            logging.warning("No PDF file selected.")
            return

        logging.info(f"Selected PDF file: {pdf_path}")

        # Extract images from the PDF
        extract_images_from_pdf(pdf_path)
    except Exception as e:
        logging.error(f"An error occurred while selecting PDF: {e}")

def extract_images_from_pdf(pdf_path):
    try:
        # Open the PDF file
        doc = fitz.open(pdf_path)
        logging.info(f"Opened PDF file: {pdf_path}")

        # Get the directory of the current script
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Create an output folder in the script directory
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_folder = os.path.join(script_dir, base_name + "_images")
        os.makedirs(output_folder, exist_ok=True)
        logging.info(f"Created output folder: {output_folder}")

        # Create a text file for OCR results in the script directory
        text_filename = f"{base_name}_images.txt"
        text_filepath = os.path.join(output_folder, text_filename)

        with open(text_filepath, "w", encoding="utf-8") as text_file:
            # Iterate through the pages
            image_counter = 1
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                logging.info(f"Processing page {page_num + 1}/{len(doc)}")

                # Extract images from the page
                for img_index, img in enumerate(page.get_images(full=True)):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]

                    # Check image size
                    if len(image_bytes) < 2048:  # 2KB = 2048 bytes
                        logging.info(f"Skipped small image on page {page_num + 1}, image {img_index + 1} (size: {len(image_bytes)} bytes)")
                        continue

                    # Create image filename
                    image_filename = f"{base_name}_{image_counter}.png"
                    image_filepath = os.path.join(output_folder, image_filename)

                    # Write image to file
                    with open(image_filepath, "wb") as img_file:
                        img_file.write(image_bytes)

                    logging.info(f"Extracted: {image_filename}")

                    # Perform OCR on the image
                    image = Image.open(image_filepath)
                    ocr_text = pytesseract.image_to_string(image, lang='eng')

                    # Write OCR text to the text file
                    text_file.write(f"--- Image {image_counter}: {image_filename} ---\n")
                    text_file.write(ocr_text)
                    text_file.write("\n\n")

                    image_counter += 1

        doc.close()
        logging.info("Image extraction and OCR complete!")
    except Exception as e:
        logging.error(f"An error occurred while extracting images: {e}")

if __name__ == "__main__":
    # Create a basic Tk root, hide the main window
    root = tk.Tk()
    root.withdraw()

    select_pdf_and_extract_images()

    # Destroy the hidden root after finishing
    root.destroy()