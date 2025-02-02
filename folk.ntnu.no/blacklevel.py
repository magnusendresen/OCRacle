from PIL import Image
import random
from tkinter import Tk, filedialog

def check_color_in_image(image_path, target_color, resolution_percentage):
    # Åpne bildet
    img = Image.open(image_path)
    img = img.convert('RGB')
    
    # Finn ny oppløsning basert på prosent
    width, height = img.size
    new_width = int(width * (resolution_percentage / 100))
    new_height = int(height * (resolution_percentage / 100))

    # Skaler bildet
    resized_img = img.resize((new_width, new_height))
    pixels = resized_img.load()

    # Gå gjennom pikslene
    total_pixels = new_width * new_height
    matching_pixels = []
    black_pixel_count = 0

    for y in range(new_height):
        for x in range(new_width):
            if pixels[x, y] == target_color:
                matching_pixels.append((x, y))
            if pixels[x, y] == (0, 0, 0):
                black_pixel_count += 1

    black_percentage = (black_pixel_count / total_pixels) * 100
    return matching_pixels, black_percentage

def select_image():
    # Åpne en filvelger for å velge bildefilen
    root = Tk()
    root.withdraw()  # Skjul hovedvinduet
    file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg;*.jpeg;*.png;*.bmp;*.tiff")])
    return file_path

# Eksempel på bruk:
# Velg bildefil
image_path = select_image()
if not image_path:
    print("Ingen fil ble valgt. Avslutter.")
    exit()

# Målfarge (som RGB-verdi)
target_color = (255, 0, 0)  # Rød som eksempel

# Prosentsats for oppløsning
resolution_percentage = 5  # 5% av original størrelse

# Sjekk pikslene
matching_pixels, black_percentage = check_color_in_image(image_path, target_color, resolution_percentage)
print(f"Fant {len(matching_pixels)} piksler som matcher fargen {target_color} i {resolution_percentage}% oppløsning.")
print(f"{black_percentage:.2f}% av de sjekkede pikslene er svarte.")
