#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_images.py
~~~~~~~~~~~~~~~~~
Henter figurer fra en PDF‑eksamen og lagrer dem som PNG‑filer.

Endringer i denne versjonen
---------------------------
* **Ingen etter‑merging av delbilder lenger** – i stedet koples linjer sammen før
  kontur‑deteksjon med morfologisk dilatasjon. Det gjør at figurer som er delt
  opp i flere konturer (slik som kuben du viste) i utgangspunktet registreres
  som én stor kontur.
* Nye konfig‑variabler `DILATE_KERNEL_SIZE` og `DILATE_ITER` for å styre hvor
  mye kantene «blåses opp» før kontur‑søk.
* `MERGE_IOU_THRESHOLD` og `MERGE_GAP_PX` er fjernet.
"""

# ---------------------------------------------------------------------------
# KONFIG – juster verdier etter behov
# ---------------------------------------------------------------------------
TEXT_LEN_LIMIT = 75              # Tegn før et bilde regnes som «tekst‑tungt»
MIN_CONTOUR_AREA = 15_000        # Min. areal for en kontur (px²)
MIN_CONTOUR_HEIGHT = 120         # Min. høyde for en kontur (px)
OVERLAP_IOU_THRESHOLD = 0.3      # Dropp subcrops som overlapper > dette
PIXEL_SIMILARITY_THRESHOLD = 0.5 # Dropp duplikater som ligner mer enn dette
CANNY_LOW, CANNY_HIGH = 50, 150  # Canny‑parametre
DILATE_KERNEL_SIZE = 5           # Kernel‑størrelse for dilatasjon (px)
DILATE_ITER = 2                  # Antall iterasjoner med dilatasjon
ZOOM = 2.0                       # Rasteriseringsoppløsning for PDF‑siden
# ---------------------------------------------------------------------------

import os
import shutil
import fitz  # PyMuPDF
import cv2
import numpy as np
import asyncio
from google.cloud import vision
import prompttotext
import ocrpdf
import sys
from typing import List, Tuple, Dict

# Sørg for UTF‑8‑stdout
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

# Google Vision‑legitimasjon
json_path = os.getenv("OCRACLE_JSON_PATH")
if not json_path or not os.path.exists(json_path):
    raise FileNotFoundError(f"[ERROR] Invalid OCRACLE_JSON_PATH: {json_path}")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = json_path

_nonchalant = (
    "DO AS YOU ARE TOLD AND RESPOND ONLY WITH WHAT IS ASKED FROM YOU. "
    "DO NOT EXPLAIN OR SAY WHAT YOU ARE DOING. "
    "DO NOT WRITE ANY SYMBOLS LIKE - OR \n OR CHANGE LETTER FORMATTING WITH ** AND SIMILAR. "
    "YOU ARE USED IN A TEXT PROCESSING PYTHON PROGRAM SO THE TEXT SHOULD BE PLAIN. "
)

# ---------------------------------------------------------------------------
# Hjelpefunksjoner
# ---------------------------------------------------------------------------

def _bbox_iou(b1: Tuple[int, int, int, int], b2: Tuple[int, int, int, int]) -> float:
    """IoU mellom to bokser (x, y, w, h)."""
    x1, y1, w1, h1 = b1
    x2, y2, w2, h2 = b2
    xa, ya = max(x1, x2), max(y1, y2)
    xb, yb = min(x1 + w1, x2 + w2), min(y1 + h1, y2 + h2)
    inter = max(0, xb - xa) * max(0, yb - ya)
    if inter == 0:
        return 0.0
    union = w1 * h1 + w2 * h2 - inter
    return inter / union

# ---------------------------------------------------------------------------
# Hoved‑funksjon
# ---------------------------------------------------------------------------

async def extract_images(
    pdf_path: str,
    subject: str,
    version: str,
    total_tasks: List[str],
    output_folder: str | None = None,
):
    """Ekstraherer figurer fra *pdf_path* og lagrer dem som PNG‑filer."""

    if output_folder is None:
        output_folder = os.path.join("img", f"{subject}_{version}_images")
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(output_folder, exist_ok=True)

    doc = fitz.open(pdf_path)
    client = vision.ImageAnnotatorClient()

    last_tasks: List[str] = ["0"]
    counts: Dict[str, int] = {}

    print(f"[INFO] Starter prosessering av '{pdf_path}' → {doc.page_count} sider\n")

    # ---------- side‑sløyfe ----------
    for page_index, page in enumerate(doc, start=1):
        print(f"[INFO] Side {page_index}/{doc.page_count}")

        pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM))
        arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
        page_bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR if pix.alpha else cv2.COLOR_RGB2BGR)

        # ---- oppgavenummer ----
        _, buf = cv2.imencode(".png", page_bgr)
        resp = client.text_detection(image=vision.Image(content=buf.tobytes()))
        if resp.error.message:
            raise RuntimeError(resp.error.message)
        page_text = resp.text_annotations[0].description.replace("\n", " ") if resp.text_annotations else ""
        prompt = (
            _nonchalant +
            f"Hvilket av disse oppgavenumrene {', '.join(total_tasks)} er i denne teksten? "
            "Svar KUN med oppgavenummeret (og bokstav) nøyaktig slik det står skrevet fra denne listen. "
            "Hvis uklart, svar 0. "
            "Her kommer teksten: " + page_text
        )
        res = await prompttotext.async_prompt_to_text(prompt, max_tokens=50, isNum=False, maxLen=200)
        tasks = [ln.strip() for ln in str(res).splitlines() if ln.strip() and (ln.strip() in total_tasks or ln.strip()=="0")] or ["0"]
        if tasks == ["0"]:
            tasks = last_tasks
        last_tasks = tasks
        page_task = tasks[0]

        # ---- bilde‑sløyfe ----
        for img_idx, img_info in enumerate(page.get_images(full=True), start=1):
            rects = page.get_image_rects(img_info[0])
            if not rects:
                continue
            r = max(rects, key=lambda rt: rt.width * rt.height)
            x0, y0, x1, y1 = (int(r.x0 * ZOOM), int(r.y0 * ZOOM), int(r.x1 * ZOOM), int(r.y1 * ZOOM))
            crop = page_bgr[y0:y1, x0:x1]
            if crop.size == 0:
                continue

            # ---- figur/tekst‑sjekk ----
            _, crop_buf = cv2.imencode(".png", crop)
            img_text = ocrpdf.detect_text(crop_buf.tobytes())
            verify_prompt = (
                _nonchalant +
                "Does this text include put-together sentences? Respond 0 if yes, 1 if no. "
                "Text: " + img_text
            )
            v_raw = await prompttotext.async_prompt_to_text(verify_prompt, max_tokens=50, isNum=True, maxLen=2)
            try:
                img_verify = int(str(v_raw).strip())
            except ValueError:
                img_verify = 0
            print(f"    · Image {img_idx}: verify={img_verify}, len(text)={len(img_text)}")

            task_num = page_task
            counts[task_num] = counts.get(task_num, 0) + 1
            seq = f"{counts[task_num]:02d}"

            # ---- lagre direkte hvis kort tekst / verify==1 ----
            if img_verify == 1 and len(img_text) <= TEXT_LEN_LIMIT:
                fname = f"{subject}_{version}_{task_num}_{seq}.png"
                cv2.imwrite(os.path.join(output_folder, fname), crop)
                print(f"      · Lagret uten sub‑cropping: {fname}\n")
                continue

            # ---- Sub‑cropping med dilatasjon ----
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, CANNY_LOW, CANNY_HIGH)

            # Koble sammen nærgående kanter
            kernel = np.ones((DILATE_KERNEL_SIZE, DILATE_KERNEL_SIZE), np.uint8)
            edges = cv2.dilate(edges, kernel, iterations=DILATE_ITER)

            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            boxes = []
            for c in contours:
                x, y, w, h = cv2.boundingRect(c)
                if w * h < MIN_CONTOUR_AREA or h < MIN_CONTOUR_HEIGHT:
                    continue
                boxes.append((x, y, w, h))

            if not boxes:
                # ingen subkonturer funnet – dropp bildet helt
                counts[task_num] -= 1  # rull tilbake sekvensteller så nummereringen holder seg
                print("      · Ingen konturer – droppet")
                continue

            # Fjern overlappende bokser (kun én per område)
            filtered_boxes = []
            for b in sorted(boxes, key=lambda b: b[2]*b[3], reverse=True):
                if any(_bbox_iou(b, fb) > OVERLAP_IOU_THRESHOLD for fb in filtered_boxes):
                    continue
                filtered_boxes.append(b)

            print(f"      · {len(boxes)} konturer → {len(filtered_boxes)} etter filtrering")

            # Lagre subbilder
            for sb_idx, (x, y, w, h) in enumerate(filtered_boxes, start=1):
                sub = crop[y:y+h, x:x+w]
                fname = f"{subject}_{version}_{task_num}_{seq}_c{sb_idx}.png"
                cv2.imwrite(os.path.join(output_folder, fname), sub)
                print(f"      · Lagret {fname}")
            print()

    # ---------- slutt ----------
    doc.close()
    print("\n[INFO] Ferdig! Sammendrag:")
    for task, cnt in sorted(counts.items(), key=lambda t: (int(''.join(filter(str.isdigit, t[0])) or 0), t[0])):
        print(f"  Oppgave {task}: {cnt} figur(er)")
    print(f"\n[INFO] Alle filer er lagret i: {output_folder}\n")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(
        extract_images(
            pdf_path="mast2200.pdf",
            subject="MAST2200",
            version="S24",
            total_tasks=[str(i) for i in range(1, 13)],
            output_folder=None,
        )
    )
