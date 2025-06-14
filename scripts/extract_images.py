import asyncio
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pytesseract
from PIL import Image

import cv2
import fitz
import numpy as np

import prompt_to_text
from project_config import IMG_DIR, PROMPT_CONFIG, PROGRESS_FILE
from pdf_contents import (
    list_pdf_containers,
    query_start_markers,
    build_container_string,
    confirm_task_text,
)

TASK_RE = re.compile(r"(Oppg(?:ave|\xE5ve)?|Task|Problem)\s*(\d+[a-zA-Z]?)")

TEXT_LEN_LIMIT = 75
MIN_CONTOUR_AREA = 15_000
MIN_CONTOUR_HEIGHT = 120
OVERLAP_IOU_THRESHOLD = 0.3
CANNY_LOW, CANNY_HIGH = 50, 150
DILATE_KERNEL_SIZE = 5
DILATE_ITER = 2


def write_progress(updates: Dict[int, str]) -> None:
    """Write progress updates to the shared progress file."""
    try:
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
        else:
            lines = []

        max_idx = max(updates.keys())
        while len(lines) < max_idx + 1:
            lines.append("\n")

        for idx, text in updates.items():
            lines[idx] = f"{text}\n"

        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)
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


TASK_PATTERN = re.compile(r"(Oppg(?:ave|\xE5ve)?|Task|Problem)\s*(\d+[a-zA-Z]?)", re.IGNORECASE)

def _fallback_markers(containers: List[Dict]) -> List[int]:
    """Return a list of container indices that look like task starts."""
    markers = []
    for idx, c in enumerate(containers):
        if TASK_PATTERN.search(c.get("text", "")):
            markers.append(idx)
    return markers


async def _assign_tasks(
    containers: List[Dict], expected_tasks: Optional[List[str]] = None
) -> Tuple[Dict[int, str], List[Tuple[int, int]], List[str]]:
    """Assign containers to tasks based on detected start markers."""

    markers = await query_start_markers(containers)
    if not markers:
        markers = _fallback_markers(containers)
        if not markers:
            print(
                "[WARNING] Could not detect task markers. Falling back to sequential numbering."
            )
            ranges = [(i, i + 1) for i in range(len(containers))]
            task_map = {i: str(i + 1) for i in range(len(containers))}
            return task_map, ranges, [str(i + 1) for i in range(len(containers))]

    markers = sorted(set([0] + markers))
    ranges: List[Tuple[int, int]] = []
    for i, start in enumerate(markers):
        end = markers[i + 1] if i + 1 < len(markers) else len(containers)
        ranges.append((start, end))

    task_map: Dict[int, str] = {}
    assigned: List[str] = []
    for idx, (start, end) in enumerate(ranges, start=1):
        if expected_tasks and idx - 1 < len(expected_tasks):
            task_num = expected_tasks[idx - 1]
        else:
            first_text = containers[start].get("text", "") if start < len(containers) else ""
            m2 = TASK_PATTERN.search(first_text)
            task_num = m2.group(2) if m2 else str(idx)

        assigned.append(task_num)
        for ci in range(start, end):
            task_map[ci] = task_num

    if expected_tasks and len(expected_tasks) != len(ranges):
        print(
            f"[WARNING] Number of tasks ({len(expected_tasks)}) does not match detected container batches ({len(ranges)})."
        )

    return task_map, ranges, assigned


def _parse_task_num(text: str) -> Optional[int]:
    """Extract a leading integer from a task string if present."""
    if not text:
        return None
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else None


def _infer_shift(
    mismatches: List[int],
    ranges: List[Tuple[int, int]],
    expected_tasks: List[str],
    containers: List[Dict],
) -> Optional[int]:
    """Infer a uniform task index shift to better align detected ranges."""

    # First try to infer shift from sampled mismatches
    diffs = []
    for idx in mismatches:
        start, _ = ranges[idx]
        detected = _parse_task_num(containers[start].get("text", ""))
        expected = _parse_task_num(expected_tasks[idx]) if idx < len(expected_tasks) else None
        if detected is None or expected is None:
            continue
        diffs.append(expected - detected)

    if diffs and len(set(diffs)) == 1:
        return diffs[0]

    # If mismatches didn't reveal a clear offset, try aligning all numbers
    detected_nums = [
        _parse_task_num(containers[start].get("text", "")) for start, _ in ranges
    ]
    expected_nums = [_parse_task_num(t) for t in expected_tasks]

    max_shift = max(len(detected_nums), len(expected_nums))
    best_shift: Optional[int] = None
    best_matches = -1

    for shift in range(-max_shift, max_shift + 1):
        matches = 0
        for idx, d_num in enumerate(detected_nums):
            j = idx - shift
            if 0 <= j < len(expected_nums):
                e_num = expected_nums[j]
                if d_num is not None and e_num is not None and d_num == e_num:
                    matches += 1
        if matches > best_matches:
            best_matches = matches
            best_shift = shift

    if best_shift is not None and best_shift != 0 and best_matches >= 2:
        return best_shift

    return None


def _apply_shift(
    shift: int,
    ranges: List[Tuple[int, int]],
    expected_tasks: List[str],
    containers: List[Dict],
) -> Tuple[Dict[int, str], List[str]]:
    """Rebuild task mapping using a constant shift."""

    new_map: Dict[int, str] = {}
    new_assigned: List[str] = []
    for idx, (start, end) in enumerate(ranges):
        src_idx = idx - shift
        if 0 <= src_idx < len(expected_tasks):
            task_num = expected_tasks[src_idx]
        else:
            first_text = containers[start].get("text", "")
            m2 = TASK_PATTERN.search(first_text)
            task_num = m2.group(2) if m2 else str(idx + 1)

        new_assigned.append(task_num)
        for ci in range(start, end):
            new_map[ci] = task_num

    return new_map, new_assigned


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
    mismatches = await confirm_task_text(containers, ranges, assigned)

    shift = None
    if expected_tasks:
        shift = _infer_shift(mismatches or [], ranges, expected_tasks, containers)

    if shift and shift != 0:
        print(f"[INFO] Detected consistent task offset of {shift}; realigning.")
        task_map, assigned = _apply_shift(shift, ranges, expected_tasks, containers)
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


async def main_async(
    pdf_path: str,
    subject: str = "TEST",
    version: str = "1",
    expected_tasks: Optional[List[str]] = None,
):
    await extract_images_with_tasks(pdf_path, subject, version, expected_tasks=expected_tasks)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python extract_images.py <file.pdf> [subject] [version]")
        sys.exit(1)
    path = sys.argv[1]
    subj = sys.argv[2] if len(sys.argv) > 2 else "TEST"
    ver = sys.argv[3] if len(sys.argv) > 3 else "1"
    asyncio.run(main_async(path, subj, ver))
