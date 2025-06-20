import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import fitz
import numpy as np
import pytesseract
from PIL import Image

from project_config import IMG_DIR, PROGRESS_FILE
import task_boundaries

TEXT_LEN_LIMIT = 75
MIN_CONTOUR_AREA = 15000
MIN_CONTOUR_HEIGHT = 120
OVERLAP_IOU_THRESHOLD = 0.3
CANNY_LOW, CANNY_HIGH = 50, 150
DILATE_KERNEL_SIZE = 5
DILATE_ITER = 2


def write_progress(updates: Dict[int, str]) -> None:
    try:
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}
        for idx, text in updates.items():
            data[str(idx + 1)] = text
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[ERROR] Could not update progress file: {e}")


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


def _get_text(img: np.ndarray) -> str:
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb)
    return pytesseract.image_to_string(pil_img, lang="eng+nor")


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
        else:
            print(f"[ERROR] Could not encode image for {path}")

    return _save


async def _process_image(img: np.ndarray, task_num: str, save_func, attempt: int = 0):
    text = await asyncio.to_thread(_get_text, img)
    if len(text) <= TEXT_LEN_LIMIT:
        save_func(img, task_num)
        return
    if attempt >= 2:
        return
    subs = _detect_crops(img)
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
    containers = await task_boundaries.list_pdf_containers(pdf_path)
    boundaries = task_boundaries.load_boundaries(Path(__file__).parent / "temp")
    if boundaries:
        ranges, assigned, _ = boundaries
        task_map: Dict[int, str] = {}
        for idx, (start, end) in enumerate(ranges, start=1):
            task_num = assigned[idx - 1] if idx - 1 < len(assigned) else str(idx)
            for ci in range(start, end):
                task_map[ci] = task_num
    else:
        task_map, ranges, assigned = await task_boundaries._assign_tasks(containers, expected_tasks)
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
