import asyncio
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pytesseract
from PIL import Image

import cv2
import fitz
import numpy as np

from task_boundaries import list_pdf_containers, confirm_task_text, _assign_tasks

from project_config import IMG_DIR, PROGRESS_FILE
import json

json_path = os.getenv("OCRACLE_JSON_PATH")
if not json_path or not os.path.exists(json_path):
    raise FileNotFoundError(f"[ERROR] JSON path not found or invalid: {json_path}")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = json_path


TEXT_LEN_LIMIT = 75
MIN_CONTOUR_AREA = 15_000
MIN_CONTOUR_HEIGHT = 120
OVERLAP_IOU_THRESHOLD = 0.3
CANNY_LOW, CANNY_HIGH = 50, 150
DILATE_KERNEL_SIZE = 5
DILATE_ITER = 2






async def _get_text(img: np.ndarray) -> str:
    """OCR the provided image and return the detected text using pytesseract."""
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb)
    return await asyncio.to_thread(pytesseract.image_to_string, pil_img, lang="eng+nor")


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
    """Create a save function that writes images to disk safely."""
    exam_folder = Path(output_folder) / subject / version
    exam_folder.mkdir(parents=True, exist_ok=True)

    def _save(img: np.ndarray, task_num: str):
        task_folder = exam_folder / task_num
        task_folder.mkdir(parents=True, exist_ok=True)
        counts[task_num] = counts.get(task_num, 0) + 1
        seq = counts[task_num]
        fname = f"{subject}_{version}_{task_num}_{seq}.png"
        path = task_folder / fname
        ok, buf = cv2.imencode(".png", img)
        if ok:
            with open(path, "wb") as f:
                f.write(buf.tobytes())
            print(f"Saved {path}")
        else:
            print(f"[ERROR] Could not encode image for {path}")

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
    pdf_path: str,
    subject: str,
    version: str,
    output_folder: Optional[str] = None,
    expected_tasks: Optional[List[str]] = None,
):
    output_folder = output_folder or str(IMG_DIR)
    containers = await list_pdf_containers(pdf_path)
    task_map, ranges, assigned = await _assign_tasks(containers, expected_tasks)
    to_remove = await confirm_task_text(containers, ranges)
    if to_remove:
        containers = [c for i, c in enumerate(containers) if i not in to_remove]
        task_map, ranges, assigned = await _assign_tasks(containers, expected_tasks)
    doc = fitz.open(pdf_path)
    counts: Dict[str, int] = {}
    save = _make_saver(output_folder, subject, version, counts)
    image_progress = ["0"] * len(containers)
    tasks = []

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
        task = asyncio.create_task(_process_image(img, task_num, save))
        tasks.append((task, idx))

    for task, idx in tasks:
        await task
        image_progress[idx] = "1"
        write_progress({7: "".join(image_progress)})

    doc.close()

    return assigned


async def extract_task_images(
    pdf_path: str,
    containers: List[Dict],
    task_range: Tuple[int, int],
    task_num: str,
    subject: str,
    version: str,
    output_folder: Optional[str] = None,
):
    """Extract images for a single task and save them to ``output_folder``."""
    output_folder = output_folder or str(IMG_DIR)
    doc = fitz.open(pdf_path)
    counts: Dict[str, int] = {}
    save = _make_saver(output_folder, subject, version, counts)

    start, end = task_range
    for idx in range(start, end):
        c = containers[idx]
        if c.get("type") != "image":
            continue
        bbox = c.get("bbox")
        if not bbox:
            continue
        page = doc[c["page"] - 1]
        pix = page.get_pixmap(clip=fitz.Rect(bbox), dpi=300)
        arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
        img = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR if pix.alpha else cv2.COLOR_RGB2BGR)
        await _process_image(img, task_num, save)

    doc.close()



async def main_async(
    pdf_path: str,
    subject: str = "TEST",
    version: str = "1",
    expected_tasks: Optional[List[str]] = None,
):
    return await extract_images_with_tasks(pdf_path, subject, version, expected_tasks=expected_tasks)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python extract_images.py <file.pdf> [subject] [version]")
        sys.exit(1)
    path = sys.argv[1]
    subj = sys.argv[2] if len(sys.argv) > 2 else "TEST"
    ver = sys.argv[3] if len(sys.argv) > 3 else "1"
    asyncio.run(main_async(path, subj, ver))
