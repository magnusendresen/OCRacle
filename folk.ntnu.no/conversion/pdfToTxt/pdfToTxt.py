import os
import pytesseract
from PIL import Image
from tkinter import Tk
from tkinter.filedialog import askopenfilename
from pdf2image import convert_from_path
import re

def pdf_to_images(pdf_path):
    print("Converting PDF to images...")
    try:
        images = convert_from_path(pdf_path)
        print(f"Converted {len(images)} pages to images.")
        return images
    except Exception as e:
        print(f"Error during PDF to image conversion: {e}")
        return None

def save_images(images, output_dir, base_name):
    print("Saving images...")
    counter = 1
    for image in images:
        image_path = os.path.join(output_dir, f"{base_name}_{counter}.png")
        image.save(image_path, "PNG")
        print(f"Saved image: {image_path}")
        counter += 1

def numerical_sort(value):
    parts = re.split(r'(\d+)', value)
    return [int(part) if part.isdigit() else part for part in parts]

def images_to_txt(output_dir, output_file_name):
    print("Converting images to text...")
    output_file_path = os.path.join(output_dir, output_file_name)

    with open(output_file_path, "w", encoding="utf-8") as output_file:
        image_files = sorted([f for f in os.listdir(output_dir) if f.endswith(".png")], key=numerical_sort)
        for i, image_file in enumerate(image_files):
            image_path = os.path.join(output_dir, image_file)
            print(f"Processing image: {image_path}")
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img)
            
            # Write the text to the combined output file with page separator
            output_file.write(f"--- Page {i + 1} ---\n")
            output_file.write(text)
            output_file.write("\n\n")
    print(f"Text extraction complete. Output saved to {output_file_path}")

def delete_images(output_dir):
    print("Deleting images...")
    for image_path in os.listdir(output_dir):
        if image_path.endswith(".png"):
            os.remove(os.path.join(output_dir, image_path))
            print(f"Deleted image: {image_path}")

if __name__ == "__main__":
    Tk().withdraw()  # Prevents the Tkinter window from appearing
    pdf_path = askopenfilename(filetypes=[("PDF files", "*.pdf")])
    if not pdf_path:
        print("No PDF file selected. Exiting.")
        exit()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    print(f"Selected PDF: {pdf_path}")
    images = pdf_to_images(pdf_path)
    if images is None or len(images) == 0:
        print("Error converting PDF to images or no images found. Exiting.")
        exit()
    
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    save_images(images, script_dir, base_name)
    output_file_name = f"{base_name}.txt"
    images_to_txt(script_dir, output_file_name)
    delete_images(script_dir)
    print("Process completed successfully.")