#!/usr/bin/env python3
import os
import shutil
import fitz    # PyMuPDF
import cv2
import numpy as np

def extract_images_direct(pdf_path, output_folder="MEKT1101H24_images"):
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(output_folder, exist_ok=True)

    doc = fitz.open(pdf_path)
    zoom = 2.0
    matrix = fitz.Matrix(zoom, zoom)

    for pidx, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=matrix)
        arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
        page_bgr = (cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
                    if pix.alpha else cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))

        for img_i, img_info in enumerate(page.get_images(full=True), start=1):
            xref = img_info[0]
            rects = page.get_image_rects(xref)
            if not rects:
                continue

            # Velg største forekomst og konverter til pikselkoordinater
            rect = max(rects, key=lambda r: r.width * r.height)
            x0, y0 = int(rect.x0 * zoom), int(rect.y0 * zoom)
            x1, y1 = int(rect.x1 * zoom), int(rect.y1 * zoom)

            crop = page_bgr[y0:y1, x0:x1]
            if crop.size == 0:
                continue

            name = f"page-{pidx}_img-{img_i}.png"
            path = os.path.join(output_folder, name)
            cv2.imwrite(path, crop)
            print(f"[{pidx},{img_i}] Lagret: {name}")

    doc.close()
    print(f"Ferdig! Bilder lagret i '{output_folder}'.")

def which_task_on_page(pdf_path, page_number):
    

if __name__ == "__main__":
    extract_images_direct("MEKT1101H24.pdf")
