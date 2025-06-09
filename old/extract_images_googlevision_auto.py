import asyncio
import os
import re
from typing import Dict, List, Tuple

import ocr_pdf

import cv2
import fitz
import numpy as np

import prompt_to_text
from project_config import IMG_DIR, PROMPT_CONFIG
from pdf_contents import (
    list_pdf_containers,
    query_start_markers,
    build_container_string,
)

TASK_RE = re.compile(r"(Oppg(?:ave|\xE5ve)?|Task|Problem)\s*(\d+[a-zA-Z]?)")

TEXT_LEN_LIMIT = 75
MIN_CONTOUR_AREA = 15_000
MIN_CONTOUR_HEIGHT = 120
OVERLAP_IOU_THRESHOLD = 0.3
CANNY_LOW, CANNY_HIGH = 50, 150
DILATE_KERNEL_SIZE = 5
DILATE_ITER = 2


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


async def _assign_tasks(containers: List[Dict]) -> Dict[int, str]:
    markers = await query_start_markers(containers)
    if not markers:
        return {}
    markers = sorted(markers)
    ranges: List[Tuple[int, int]] = []
    for i, start in enumerate(markers):
        end = markers[i + 1] if i + 1 < len(markers) else len(containers)
        ranges.append((start, end))
    task_map: Dict[int, str] = {}
    for idx, (start, end) in enumerate(ranges, start=1):
        region_containers = containers[start:end]
        text = build_container_string(region_containers)
        prompt = (
            PROMPT_CONFIG
            + "Which task number is described in the following containers? "
            "Respond with the number only. "
            "Text:" + text
        )
        answer = await prompt_to_text.async_prompt_to_text(
            prompt, max_tokens=20, isNum=False, maxLen=20
        )
        m = TASK_RE.search(str(answer))
        task_num = m.group(2) if m else str(idx)
        for ci in range(start, end):
            task_map[ci] = task_num
    return task_map


async def _get_text(img: np.ndarray) -> str:
    """OCR the provided image and return the detected text."""
    _, buf = cv2.imencode(".png", img)
    return ocr_pdf.detect_text(buf.tobytes())


def _detect_crops(img: np.ndarray) -> List[np.ndarray]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, CANNY_LOW, CANNY_HIGH)
    kernel = np.ones((DILATE_KERNEL_SIZE, DILATE_KERNEL_SIZE), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=DILATE_ITER)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = [cv2.boundingRect(c) for c in contours]
    boxes = [b for b in boxes if b[2] * b[3] >= MIN_CONTOUR_AREA and b[3] >= MIN_CONTOUR_HEIGHT]
    if not boxes:
        return []
    filtered = []
    for b in sorted(boxes, key=lambda b: b[2] * b[3], reverse=True):
        if any(_bbox_iou(b, fb) > OVERLAP_IOU_THRESHOLD for fb in filtered):
            continue
        filtered.append(b)
    return [img[y : y + h, x : x + w] for x, y, w, h in filtered]


def _make_saver(output_folder: str, subject: str, version: str, counts: Dict[str, int]):
    exam_folder = os.path.join(output_folder, subject, version)
    os.makedirs(exam_folder, exist_ok=True)

    def _save(img: np.ndarray, task_num: str):
        task_dir = os.path.join(exam_folder, task_num)
        os.makedirs(task_dir, exist_ok=True)
        counts[task_num] = counts.get(task_num, 0) + 1
        seq = f"{counts[task_num]:02d}"
        fname = f"{seq}.png"
        cv2.imwrite(os.path.join(task_dir, fname), img)
        print(f"Saved {subject}/{version}/{task_num}/{fname}")

    return _save


async def _process_image(
    img: np.ndarray,
    task_num: str,
    save_func,
    attempt: int = 0,
):
    text = await _get_text(img)
    print(f"    · attempt {attempt}: len(text)={len(text)}")

    if len(text) <= TEXT_LEN_LIMIT:
        save_func(img, task_num)
        return

    if attempt >= 2:
        print("      · Dropped due to excessive text after two crops")
        return

    subs = _detect_crops(img)
    if not subs:
        print("      · No contours – dropped")
        return

    print(f"      · {len(subs)} cropped regions")
    for sub in subs:
        await _process_image(sub, task_num, save_func, attempt + 1)


async def extract_images_with_tasks(
    pdf_path: str, subject: str, version: str, output_folder: str = None
):
    output_folder = output_folder or str(IMG_DIR)
    containers = await list_pdf_containers(pdf_path)
    task_map = await _assign_tasks(containers)
    doc = fitz.open(pdf_path)
    counts: Dict[str, int] = {}
    save = _make_saver(output_folder, subject, version, counts)

    for idx, c in enumerate(containers):
        if c.get("type") != "image":
            continue
        bbox = c.get("bbox")
        if not bbox:
            continue
        page = doc[c["page"] - 1]
        pix = page.get_pixmap(clip=fitz.Rect(bbox), dpi=300)
        arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
        img = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR if pix.alpha else cv2.COLOR_RGB2BGR)
        task_num = task_map.get(idx, "0")
        await _process_image(img, task_num, save)
    doc.close()


async def main_async(pdf_path: str, subject: str = "TEST", version: str = "1"):
    await extract_images_with_tasks(pdf_path, subject, version)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage: python extract_images_with_tasks.py <file.pdf> [subject] [version]"
        )
        sys.exit(1)
    path = sys.argv[1]
    subj = sys.argv[2] if len(sys.argv) > 2 else "TEST"
    ver = sys.argv[3] if len(sys.argv) > 3 else "1"
    asyncio.run(main_async(path, subj, ver))
