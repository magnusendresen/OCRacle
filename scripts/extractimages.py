#!/usr/bin/env python3
import os
import shutil
import fitz    # PyMuPDF
import cv2
import numpy as np
import asyncio
from google.cloud import vision
import prompttotext
import sys
from typing import List

# Sørg for UTF-8-output
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# Last inn Google Vision credentials
json_path = os.getenv("OCRACLE_JSON_PATH")
if not json_path or not os.path.exists(json_path):
    raise FileNotFoundError(f"[ERROR] Invalid OCRACLE_JSON_PATH: {json_path}")
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = json_path

async def extract_images(
    pdf_path: str,
    subject: str,
    version: str,
    total_tasks: List[str],
    output_folder: str = None
):
    """
    Ekstraher bilder fra PDF og navngi dem basert på emnekode (subject), versjon og oppgavenummer (string).

    Args:
        pdf_path: Path til PDF-filen.
        subject: Emnekode, f.eks. 'MEKT1101H24'.
        version: Versjonskode, f.eks. 'H24'.
        total_tasks: Liste med alle oppgavenummer som kan forekomme, f.eks. ['1', '1a', '2b'].
        output_folder: Mappe der filer lagres. Default: 'img/<subject>_<version>_images'.
    """
    # Standard output_folder basert på subject og version
    if output_folder is None:
        base = f"{subject}_{version}_images"
        output_folder = os.path.join("img", base)

    # Rydd opp gammel mappe
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(output_folder, exist_ok=True)

    # Åpne PDF og sett opp OCR-klient
    doc = fitz.open(pdf_path)
    client = vision.ImageAnnotatorClient()
    zoom = 2.0
    matrix = fitz.Matrix(zoom, zoom)

    last_tasks = ['0']
    counts = {}

    for page_index, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=matrix)
        arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
        page_bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR) if pix.alpha else cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

        # OCR
        _, buf = cv2.imencode('.png', page_bgr)
        response = client.text_detection(image=vision.Image(content=buf.tobytes()))
        if response.error.message:
            raise RuntimeError(response.error.message)
        text = response.text_annotations[0].description.replace('\n', ' ') if response.text_annotations else ''

        # Prompt som ber om streng-oppgavenummer fra total_tasks
        options = ", ".join(total_tasks)
        prompt = (
            "DO AS YOU ARE TOLD AND RESPOND ONLY WITH WHAT IS ASKED FROM YOU. "
            f"Hvilket av disse oppgavenummerne er på siden? {options}. "
            "Respond ONLY with the task number from this list that appears on this page as a string. "
            "Hvis det er uklart eller ingen stemmer, respond med 0. "
            + text
        )
        try:
            result = await prompttotext.async_prompt_to_text(
                prompt,
                max_tokens=50,
                isNum=False,
                maxLen=200
            )
        except Exception as e:
            print(f"Warning: OCR-prompt feilet på side {page_index}: {e}")
            result = ''

        # Håndter resultat som strenger
        if not isinstance(result, str) or not result.strip():
            tasks = ['0']
        else:
            lines = [line.strip() for line in result.splitlines()]
            tasks = [line for line in lines if line in total_tasks or line == '0']
            tasks = tasks or ['0']

        # Fallback til forrige hvis ingen funnet, eller bruk resultat
        if tasks == ['0']:
            tasks = last_tasks
        last_tasks = tasks

        # Velg det første task-nummeret fra prompt som gjelder for hele siden
        page_task = tasks[0]

        # Ekstraher og navngi bilder per task (string)
        for img_idx, img_info in enumerate(page.get_images(full=True), start=1):
            rects = page.get_image_rects(img_info[0])
            if not rects:
                continue
            rect = max(rects, key=lambda r: r.width * r.height)
            x0, y0, x1, y1 = (int(rect.x0 * zoom), int(rect.y0 * zoom),
                              int(rect.x1 * zoom), int(rect.y1 * zoom))
            crop = page_bgr[y0:y1, x0:x1]
            if crop.size == 0:
                continue

            # Brug page_task fra prompt for filnavn
            task_num = page_task
            counts.setdefault(task_num, 0)
            counts[task_num] += 1
            seq = f"{counts[task_num]:02d}"

            filename = f"{subject}_{version}_{task_num}_{seq}.png"
            path = os.path.join(output_folder, filename)
            cv2.imwrite(path, crop)
            print(f"Lagret: {filename}")

    doc.close()
    print(f"Ferdig! Filer lagret i '{output_folder}'.")
