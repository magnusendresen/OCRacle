import taskprocessing
import ocrpdf
import prompttotext
import main

import os
import shutil
import fitz
import cv2
import numpy as np
import asyncio
import re
import json
import sys
from typing import List, Tuple, Dict, Optional
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

IMG_DIR = main.PROJECT_ROOT / "img"

progress_file = Path(__file__).resolve().parent / "progress.txt"

def write_progress(updates: Optional[Dict[int, str]] = None):
    try:
        if progress_file.exists():
            with open(progress_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        else:
            lines = []

        if updates is None:
            return

        max_idx = max(updates.keys())
        while len(lines) < max_idx + 1:
            lines.append("\n")

        for idx, text in updates.items():
            lines[idx] = f"{text}\n"

        with open(progress_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

        for idx, text in updates.items():
            print(f"[STATUS] | Wrote '{text}' to line {idx + 1} in {progress_file}")
    except Exception as e:
        print(f"[ERROR] Could not update progress file: {e}")

_nonchalant = (
    "DO AS YOU ARE TOLD AND RESPOND ONLY WITH WHAT IS ASKED FROM YOU. "
    "DO NOT EXPLAIN OR SAY WHAT YOU ARE DOING. "
    "DO NOT WRITE ANY SYMBOLS LIKE - OR \n OR CHANGE LETTER FORMATTING WITH ** AND SIMILAR. "
    "YOU ARE USED IN A TEXT PROCESSING PYTHON PROGRAM SO THE TEXT SHOULD BE PLAIN. "
)

TEXT_LEN_LIMIT = 75
MIN_CONTOUR_AREA = 15_000
MIN_CONTOUR_HEIGHT = 120
OVERLAP_IOU_THRESHOLD = 0.3
CANNY_LOW, CANNY_HIGH = 50, 150
DILATE_KERNEL_SIZE = 5
DILATE_ITER = 2
ZOOM = 2.0

TASK_RE = re.compile(r"(Oppg(?:ave|\xE5ve)?|Task|Problem)\s*(\d+)", re.IGNORECASE)

def _bbox_iou(b1: Tuple[int, int, int, int], b2: Tuple[int, int, int, int]) -> float:
    x1, y1, w1, h1 = b1
    x2, y2, w2, h2 = b2
    xa, ya = max(x1, x2), max(y1, y2)
    xb = min(x1 + w1, x2 + w2)
    yb = min(y1 + h1, y2 + h2)
    inter = max(0, xb - xa) * max(0, yb - ya)
    if inter == 0:
        return 0.0
    union = w1 * h1 + w2 * h2 - inter
    return inter / union

def _find_task_headings(page) -> List[Tuple[float, str]]:
    headings = []
    try:
        text_dict = page.get_text("dict")
    except Exception:
        return headings

    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            line_text = "".join(span.get("text", "") for span in line.get("spans", []))
            m = TASK_RE.search(line_text)
            if m:
                y = line["bbox"][1]
                headings.append((y, m.group(2)))
                break
    return headings

def _build_regions(page, headings: List[Tuple[float, str]], fallback_task: str) -> List[Tuple[float, float, str]]:
    rect_height = page.rect.height
    if not headings:
        return [(0, rect_height, fallback_task)]

    headings = sorted(headings, key=lambda h: h[0])
    regions = []
    prev_y = 0.0
    prev_task = fallback_task
    for y, task_num in headings:
        if y > prev_y:
            regions.append((prev_y, y, prev_task))
        prev_y = y
        prev_task = task_num
    regions.append((prev_y, rect_height, prev_task))
    return regions

def _task_from_y(regions: List[Tuple[float, float, str]], y: float) -> str:
    for start, end, t in regions:
        if start <= y < end:
            return t
    return regions[-1][2]

def _parse_tasks(answer: str, allowed: List[str]) -> List[str]:
    allowed_nums = {re.match(r"(\d+)", t).group(1) for t in allowed if re.match(r"\d+", t)}
    tokens = re.split(r"[\s,;:/\\]+", answer.strip())
    hits = [t for t in tokens if t in allowed]
    return hits or ["0"]

async def extract_images(
    pdf_path: str,
    subject: str,
    version: str,
    total_tasks: List[str],
    full_text: str,
    output_folder: str,
):
    
    doc = fitz.open(pdf_path)
    image_progress = ['0'] * len(doc)
    counts: Dict[str, int] = {}
    last_tasks: List[str] = [total_tasks[0]]
    first_task_match = re.match(r"(\d+)", total_tasks[0])
    first_task = first_task_match.group(1) if first_task_match else total_tasks[0]
    last_tasks: List[str] = [first_task]

    print(f"[INFO] Starter prosessering av '{pdf_path}' → {doc.page_count} sider")

    async def process_page(page_index: int, page):
        print(f"[INFO] Side {page_index}/{doc.page_count}")

        images = page.get_images(full=True)
        if not images:
            print("    · Ingen bilder på siden, hopper over tekstprompt.")
            image_progress[page_index - 1] = '1'
            write_progress({7: ''.join(image_progress)})
            return {}

        prompt = (
            _nonchalant + 
            f"Hvilke oppgave(r) fra denne listen {total_tasks} er på side {page_index} i teksten? "
            "Skriv oppgavene funnet på den siden separert med et komma. "
            "Eksempler på svar (uten anførselstegn): \"1\", \"2, 3\", \"1, 2, 3\", osv. "
            "Skriv kun de oppgavene du er helt sikker på at er på siden. "
            "Se på teksten i sin helhet for å logisk avgjøre hvilke oppgaver som er på siden. "
            "Her er teksten: " + full_text
            )
        res = await prompttotext.async_prompt_to_text(
            prompt, max_tokens=50, isNum=False, maxLen=200
        )
        page_tasks = _parse_tasks(str(res), total_tasks)
        if page_tasks == ["0"]:
            page_tasks = [last_tasks[-1]]
        last_tasks[:] = page_tasks

        headings = _find_task_headings(page)
        regions = _build_regions(page, headings, last_tasks[-1])

        pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM))
        arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
        page_bgr = cv2.cvtColor(
            arr, cv2.COLOR_RGBA2BGR if pix.alpha else cv2.COLOR_RGB2BGR
        )

        def _save(img: np.ndarray, task_num: str):
            counts[task_num] = counts.get(task_num, 0) + 1
            seq = f"{counts[task_num]:02d}"
            task_num_padded = f"{int(task_num):02d}" if task_num.isdigit() else task_num
            fname = f"{subject}_{version}_{task_num_padded}_{seq}.png"
            cv2.imwrite(os.path.join(output_folder, fname), img)
            print(f"      · Lagret {fname}")

        for img_idx, img_info in enumerate(images, start=1):
            rects = page.get_image_rects(img_info[0])
            if not rects:
                continue
            r = max(rects, key=lambda rt: rt.width * rt.height)
            x0, y0, x1, y1 = (
                int(r.x0 * ZOOM), int(r.y0 * ZOOM),
                int(r.x1 * ZOOM), int(r.y1 * ZOOM)
            )
            crop = page_bgr[y0:y1, x0:x1]
            if crop.size == 0:
                continue

            y_center = (y0 + y1) / 2
            task_for_img = _task_from_y(regions, y_center)

            _, crop_buf = cv2.imencode(".png", crop)
            img_text = ocrpdf.detect_text(crop_buf.tobytes())
            verify_prompt = (_nonchalant + "Does this text include put-together sentences? Respond 0 if yes, 1 if no. Text: " + img_text)
            v_raw = await prompttotext.async_prompt_to_text(
                verify_prompt, max_tokens=50, isNum=True, maxLen=2
            )
            try:
                img_verify = int(str(v_raw).strip())
            except ValueError:
                img_verify = 0
            print(f"    · Image {img_idx}: verify={img_verify}, len(text)={len(img_text)}")

            if img_verify == 1 and len(img_text) <= TEXT_LEN_LIMIT:
                for t in page_tasks:
                    _save(crop, t)
            if not (img_verify == 0 and len(img_text) > TEXT_LEN_LIMIT):
                _save(crop, task_for_img)
                print()
                continue

            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, CANNY_LOW, CANNY_HIGH)
            kernel = np.ones((DILATE_KERNEL_SIZE, DILATE_KERNEL_SIZE), np.uint8)
            edges = cv2.dilate(edges, kernel, iterations=DILATE_ITER)
            contours, _ = cv2.findContours(
                edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            boxes = [cv2.boundingRect(c) for c in contours]
            boxes = [b for b in boxes if b[2]*b[3] >= MIN_CONTOUR_AREA and b[3] >= MIN_CONTOUR_HEIGHT]
            if not boxes:
                print("      · Ingen konturer – droppet")
                continue

            filtered = []
            for b in sorted(boxes, key=lambda b: b[2]*b[3], reverse=True):
                if any(_bbox_iou(b, fb) > OVERLAP_IOU_THRESHOLD for fb in filtered):
                    continue
                filtered.append(b)
            print(f"      · {len(boxes)} konturer → {len(filtered)} etter filtrering")

            for sb_idx, (x, y, w, h) in enumerate(filtered, start=1):
                sub = crop[y:y+h, x:x+w]
                _save(sub, task_for_img)
                for t in page_tasks:
                    _save(sub, t)
            print()

        image_progress[page_index - 1] = '1'
        write_progress({7: ''.join(image_progress)})
        return counts

    results = []
    for i, p in enumerate(doc):
        res = await process_page(i + 1, p)
        results.append(res)

    for page_counts in results:
        for k, v in page_counts.items():
            counts[k] = counts.get(k, 0) + v

    doc.close()
    print("\n[INFO] Ferdig! Sammendrag:")
    for task, cnt in sorted(
        counts.items(), key=lambda t: (int(re.sub(r'\D', '', t[0]) or 0), t[0])
    ):
        print(f"  Oppgave {task}: {cnt} figur(er)")

    print(f"\n[INFO] Alle filer er lagret i: {output_folder}\n")
