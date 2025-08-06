import tkinter as tk
from tkinter import filedialog
import cv2
import numpy as np
import asyncio
from extract_images import _process_image  # Sørg for at denne finnes

# Velg bildefiler via dialog
def select_images():
    root = tk.Tk()
    root.withdraw()
    file_paths = filedialog.askopenfilenames(
        title="Velg bilder",
        filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff;*.tif")]
    )
    root.destroy()  # Viktig for å rydde opp i Tk GUI
    return file_paths

# Dummy funksjon for lagring
def dummy_save_func(img, task_num):
    print(f"[DUMMY SAVE] Task {task_num} - bilde behandlet")
    return True

# Last inn og behandle bilder
async def main():
    file_paths = select_images()

    for i, path in enumerate(file_paths):
        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if img is None:
            print(f"[ADVARSEL] Kunne ikke lese bildet: {path}")
            continue

        # Konverter til BGR hvis bildet har alfa-kanal
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)

        task_num = str(i + 1)
        await _process_image(img, task_num, dummy_save_func)

# Start async event loop
if __name__ == "__main__":
    asyncio.run(main())
