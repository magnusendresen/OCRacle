import os
import pytesseract
from PIL import Image

def allImagesToTextFileOCR():
    # Leser inn alle bilder i mappen treningsdata
    try:
        files = os.listdir("treningsdata")
    except FileNotFoundError:
        print("Directory 'treningsdata' not found.")
        return

    # Går gjennom alle filene i mappen
    for file in files:
        try:
            # Åpner bildet
            img = Image.open("treningsdata/" + file)
            # Konverterer bildet til tekst
            text = pytesseract.image_to_string(img)
            # Skriver teksten til en ny fil med samme navn som bildet, men med .txt utvidelse
            text_file_path = os.path.join("treningsdata", os.path.splitext(file)[0] + ".txt")
            with open(text_file_path, "w") as f:
                f.write(text)
        except Exception as e:
            print(f"Error processing file {file}: {e}")

# Call the function to execute the OCR process
allImagesToTextFileOCR()