import os
import logging
from tkinter import Tk, filedialog
from pdf2image import convert_from_path
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import fitz  # PyMuPDF

# Konfigurer logging for å spore kjøringen av programmet
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def remove_black_background(image_path, threshold=50):
    img = Image.open(image_path).convert("RGBA")
    datas = img.getdata()

    new_data = []
    for item in datas:
        if item[0] < threshold and item[1] < threshold and item[2] < threshold:
            new_data.append((0, 0, 0, 0))  # Transparent
        else:
            new_data.append(item)

    img.putdata(new_data)
    img.save(image_path, "PNG")  # Overskriver originalbildet
    logging.info(f"Processed image saved to: {image_path}")

def check_black_percentage(image_path, resolution_percentage=5):
    img = Image.open(image_path).convert('RGB')
    width, height = img.size
    new_width = int(width * (resolution_percentage / 100))
    new_height = int(height * (resolution_percentage / 100))

    resized_img = img.resize((new_width, new_height))
    pixels = resized_img.load()

    total_pixels = new_width * new_height
    black_pixel_count = sum(
        1 for y in range(new_height) for x in range(new_width)
        if pixels[x, y] == (0, 0, 0)
    )

    black_percentage = (black_pixel_count / total_pixels) * 100
    logging.info(f"Black level of current image: {black_percentage}%")
    return black_percentage

def preprocess_image_for_ocr(pil_image):
    canvas = Image.new("RGB", pil_image.size, (255, 255, 255))
    canvas.paste(pil_image, (0, 0))
    gray = canvas.convert("L")
    filtered = gray.filter(ImageFilter.MedianFilter())
    enhancer = ImageEnhance.Contrast(filtered)
    contrast_enhanced = enhancer.enhance(1.0)
    return contrast_enhanced

def pdf_to_combined_text(pdf_path, output_dir):
    try:
        doc = fitz.open(pdf_path)
        logging.info(f"Opened PDF file: {pdf_path}")

        page_images = convert_from_path(pdf_path)
        logging.info(f"Converted PDF to {len(page_images)} page images.")

        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        pdf_output_dir = os.path.join(output_dir, base_name)
        os.makedirs(pdf_output_dir, exist_ok=True)
        logging.info(f"Created output directory: {pdf_output_dir}")

        output_file_path = os.path.join(pdf_output_dir, f"{base_name}_combined.txt")

        with open(output_file_path, "w", encoding="utf-8") as output_file:
            temp_page_image_paths = []

            for i, page_image in enumerate(page_images):
                temp_page_path = os.path.join(pdf_output_dir, f"temp_page_{i + 1}.png")
                page_image.save(temp_page_path, "PNG")
                temp_page_image_paths.append(temp_page_path)

                logging.info(f"Processing OCR for page {i + 1}")
                processed_image = preprocess_image_for_ocr(page_image)

                text = pytesseract.image_to_string(
                    processed_image,
                    lang='eng',
                    config='--oem 3 --psm 6'
                )

                output_file.write(f"--- Page {i + 1} ---\n")
                output_file.write(text)
                output_file.write("\n\n")

            image_counter = 1
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                for img_index, img in enumerate(page.get_images(full=True)):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]

                    if len(image_bytes) < 2048:
                        logging.info(f"Skipped small image on page {page_num + 1}, image {img_index + 1}")
                        continue

                    image_filename = f"{base_name}_extracted_{image_counter}.png"
                    image_filepath = os.path.join(pdf_output_dir, image_filename)
                    with open(image_filepath, "wb") as img_file:
                        img_file.write(image_bytes)

                    logging.info(f"Processing OCR for extracted image {image_counter}")

                    black_percentage = check_black_percentage(image_filepath)
                    if black_percentage > 60:
                        logging.info(f"Removing black background from {image_filepath} ({black_percentage:.2f}% black)")
                        remove_black_background(image_filepath)

                    ocr_text = pytesseract.image_to_string(
                        image_filepath,
                        lang='eng',
                        config='--oem 3 --psm 6'
                    )

                    output_file.write(f"--- {image_filepath} ---\n")
                    output_file.write(ocr_text)
                    output_file.write("\n\n")

                    image_counter += 1

            for temp_page_image_path in temp_page_image_paths:
                os.remove(temp_page_image_path)
                logging.info(f"Deleted temporary page image: {temp_page_image_path}")

        logging.info(f"Combined OCR output saved to {output_file_path}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

if __name__ == "__main__":
    Tk().withdraw()
    pdf_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
    if not pdf_path:
        logging.warning("No PDF file selected. Exiting.")
        exit()

    output_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_to_combined_text(pdf_path, output_dir)
    logging.info("Process completed successfully.")
