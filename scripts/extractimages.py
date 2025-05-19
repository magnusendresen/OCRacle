#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_images.py
~~~~~~~~~~~~~~~~~
Henter figurer fra en PDF‑eksamen og lagrer dem som PNG‑filer.

Endringer i denne versjonen
---------------------------
* **Støtte for flere oppgaver pr. side** – prompten ber nå om en kommaseparert
  liste, og alle oppgaver som identifiseres blir brukt ved navngivning.
* **Arv av siste oppgave** – hvis ingen oppgave gjenkjennes på en side, arves
  den *siste* oppgaven fra forrige side (dvs. siste element i forrige liste).
* **Navngivning kopieres for alle oppgaver** – samme figur lagres en gang per
  oppgave på siden slik at alle referanser er dekket.
* Lagt til hjelpefunksjon `_parse_tasks()` for robust tolking av svarstrengen.
* Lagt til `re`‑import og mindre opprydding.
* `page_task` er fjernet; vi itererer nå direkte over `page_tasks`.
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
import re
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
    "DO NOT WRITE ANY SYMBOLS LIKE - OR \\n OR CHANGE LETTER FORMATTING WITH ** AND SIMILAR. "
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


def _parse_tasks(answer: str, allowed: List[str]) -> List[str]:
    """Ekstraherer oppgavenumre fra svarstrengen, returnerer liste eller ["0"]."""
    tokens = re.split(r"[\s,;:/\\]+", answer.strip())
    hits = [t for t in tokens if t in allowed]
    return hits or ["0"]

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

    last_tasks: List[str] = ["0"]  # for arv til uforståelige sider
    counts: Dict[str, int] = {}

    print(f"[INFO] Starter prosessering av '{pdf_path}' → {doc.page_count} sider\n")

    # ---------- side‑sløyfe ----------
    for page_index, page in enumerate(doc, start=1):
        print(f"[INFO] Side {page_index}/{doc.page_count}")

        pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM))
        arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
        page_bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR if pix.alpha else cv2.COLOR_RGB2BGR)

        # ---- oppgavenumre ----
        _, buf = cv2.imencode(".png", page_bgr)
        resp = client.text_detection(image=vision.Image(content=buf.tobytes()))
        if resp.error.message:
            raise RuntimeError(resp.error.message)
        page_text = resp.text_annotations[0].description.replace("\n", " ") if resp.text_annotations else ""
        prompt = (
            _nonchalant +
            f"Hvilke av disse oppgavenumrene {', '.join(total_tasks)} finnes i denne teksten? "
            "Svar med en kommaseparert liste av oppgavenumre (og bokstav) nøyaktig som de står skrevet. "
            "Hvis uklart, svar 0. "
            "Her kommer teksten: " + page_text
        )
        res = await prompttotext.async_prompt_to_text(prompt, max_tokens=50, isNum=False, maxLen=200)
        page_tasks = _parse_tasks(str(res), total_tasks)

        # Arv logikk hvis ingen oppgave funnet
        if page_tasks == ["0"]:
            page_tasks = [last_tasks[-1]]  # sist kjente oppgave
        last_tasks = page_tasks  # oppdater historikk

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
                "Does this text include put‑together sentences? Respond 0 if yes, 1 if no. "
                "Text: " + img_text
            )
            v_raw = await prompttotext.async_prompt_to_text(verify_prompt, max_tokens=50, isNum=True, maxLen=2)
            try:
                img_verify = int(str(v_raw).strip())
            except ValueError:
                img_verify = 0
            print(f"    · Image {img_idx}: verify={img_verify}, len(text)={len(img_text)}")

            # ---- lagre direkte hvis kort tekst / verify==1 ----
            def _save(img, suffix: str = "") -> None:
                for task_num in page_tasks:
                    counts[task_num] = counts.get(task_num, 0) + 1
                    seq = f"{counts[task_num]:02d}"
                    fname = f"{subject}_{version}_{task_num}_{seq}{suffix}.png"
                    cv2.imwrite(os.path.join(output_folder, fname), img)
                    print(f"      · Lagret {fname}")

            if img_verify == 1 and len(img_text) <= TEXT_LEN_LIMIT:
                _save(crop)
                print()
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
                _save(sub, suffix=f"_c{sb_idx}")
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
            total_tasks=[str(i) for i in range(1, 16)],
            output_folder=None,
        )
    )
