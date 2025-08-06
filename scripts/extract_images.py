import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import uuid

import cv2
import fitz
import numpy as np
import pytesseract
from PIL import Image
import tkinter as tk
from tkinter import messagebox
import re

from project_config import *
from project_config import load_prompt

import prompt_to_text
from utils import log
import shutil
from time import perf_counter
import task_boundaries
import io
from PIL import ImageTk


TEXT_CONTENT_RATIO = 40
MIN_CONTOUR_AREA = 15_000
MIN_CONTOUR_HEIGHT = 120
OVERLAP_IOU_THRESHOLD = 0.3
CANNY_LOW, CANNY_HIGH = 50, 150
DILATE_KERNEL_SIZE = 5
DILATE_ITER = 2

# Expansion and detection parameters
STEP_PIXELS = 1
MAX_EXPANSION_PIXELS = 300

# For detecting edge
TYPE_SAMPLE_COUNT = 6
TYPE_TOLERANCE_RATIO = 0.05
COLOR_CHANGE_LIMIT = 16

# For detecting open area
OPEN_AREA_CONTRAST_THRESHOLD = 1
OPEN_AREA_PIXEL_STREAK = 30


def _bbox_iou(b1, b2):
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


async def _get_text(img: np.ndarray) -> str:
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb)
    return await asyncio.to_thread(pytesseract.image_to_string, pil_img, lang="eng+nor")


def _contrast_value(region: np.ndarray) -> int:
    reshaped = region.reshape(-1, 3)
    unique = np.unique(reshaped, axis=0)
    return 0 if len(unique) <= 1 else len(unique)


def _average_color_value(region: np.ndarray) -> float:
    return np.mean(region.reshape(-1, 3), axis=0).mean()


def _most_common_color(values: List[float]) -> float:
    arr = np.array(values, dtype=int)
    tolerance = max(1, int(255 * TYPE_TOLERANCE_RATIO))
    hist = np.bincount(arr, minlength=256)
    window = np.ones(tolerance * 2 + 1, dtype=int)
    grouped = np.convolve(hist, window, mode="same")
    return float(np.argmax(grouped))


def _expand_direction(
    img: np.ndarray, x0: int, y0: int, x1: int, y1: int, direction: str
) -> Tuple[int, int, int, int]:
    orig = (x0, y0, x1, y1)
    h, w = img.shape[:2]

    # First pass: detect open areas.
    cur = orig
    open_streak = 0
    pre_open = orig
    found_open = False
    for i in range(STEP_PIXELS, MAX_EXPANSION_PIXELS, STEP_PIXELS):
        prev_cur = cur
        if direction == "left":
            nx0 = max(0, orig[0] - i)
            if nx0 == cur[0]:
                break
            band = img[y0:y1, nx0:nx0 + STEP_PIXELS]
            cur = (nx0, y0, x1, y1)
        elif direction == "right":
            nx1 = min(w, orig[2] + i)
            if nx1 == cur[2]:
                break
            band = img[y0:y1, nx1 - STEP_PIXELS:nx1]
            cur = (x0, y0, nx1, y1)
        elif direction == "top":
            ny0 = max(0, orig[1] - i)
            if ny0 == cur[1]:
                break
            band = img[ny0:ny0 + STEP_PIXELS, x0:x1]
            cur = (x0, ny0, x1, y1)
        else:  # bottom
            ny1 = min(h, orig[3] + i)
            if ny1 == cur[3]:
                break
            band = img[ny1 - STEP_PIXELS:ny1, x0:x1]
            cur = (x0, y0, x1, ny1)

        contrast = _contrast_value(band)
        if contrast < OPEN_AREA_CONTRAST_THRESHOLD:
            if open_streak == 0:
                pre_open = prev_cur
            open_streak += STEP_PIXELS
            if open_streak >= OPEN_AREA_PIXEL_STREAK:
                cur = pre_open
                found_open = True
                break
        else:
            open_streak = 0

    if not found_open:
        # Second pass: detect color changes across the full range.
        cur = orig
        color_samples: List[float] = []
        prev_type: Optional[float] = None
        for i in range(STEP_PIXELS, MAX_EXPANSION_PIXELS, STEP_PIXELS):
            prev_cur = cur
            if direction == "left":
                nx0 = max(0, orig[0] - i)
                if nx0 == cur[0]:
                    break
                band = img[y0:y1, nx0:nx0 + STEP_PIXELS]
                cur = (nx0, y0, x1, y1)
            elif direction == "right":
                nx1 = min(w, orig[2] + i)
                if nx1 == cur[2]:
                    break
                band = img[y0:y1, nx1 - STEP_PIXELS:nx1]
                cur = (x0, y0, nx1, y1)
            elif direction == "top":
                ny0 = max(0, orig[1] - i)
                if ny0 == cur[1]:
                    break
                band = img[ny0:ny0 + STEP_PIXELS, x0:x1]
                cur = (x0, ny0, x1, y1)
            else:  # bottom
                ny1 = min(h, orig[3] + i)
                if ny1 == cur[3]:
                    break
                band = img[ny1 - STEP_PIXELS:ny1, x0:x1]
                cur = (x0, y0, x1, ny1)

            avg_color = _average_color_value(band)
            color_samples.append(avg_color)
            if len(color_samples) > TYPE_SAMPLE_COUNT:
                color_samples.pop(0)
            if len(color_samples) == TYPE_SAMPLE_COUNT:
                type_value = _most_common_color(color_samples)
                if prev_type is not None and abs(type_value - prev_type) > COLOR_CHANGE_LIMIT:
                    cur = prev_cur
                    break
                prev_type = type_value

    ret = cur
    log_dir = Path("img/log")
    log_dir.mkdir(parents=True, exist_ok=True)
    annotated = img.copy()
    cv2.rectangle(annotated, (orig[0], orig[1]), (orig[2], orig[3]), (0, 255, 0), 2)
    cv2.rectangle(annotated, (ret[0], ret[1]), (ret[2], ret[3]), (255, 0, 255), 2)
    # cv2.imwrite(str(log_dir / f"expand_{direction}_{uuid.uuid4().hex}.png"), annotated)
    return ret


def _expand_bbox(
    img: np.ndarray,
    bbox: Tuple[int, int, int, int],
    task_num: Optional[str] = None,
) -> Tuple[int, int, int, int]:
    x, y, w, h = bbox
    x0, y0, x1, y1 = x, y, x + w, y + h
    ox0, oy0, ox1, oy1 = x0, y0, x1, y1
    x0, y0, x1, y1 = _expand_direction(img, x0, y0, x1, y1, "left")
    x0, y0, x1, y1 = _expand_direction(img, x0, y0, x1, y1, "right")
    x0, y0, x1, y1 = _expand_direction(img, x0, y0, x1, y1, "top")
    x0, y0, x1, y1 = _expand_direction(img, x0, y0, x1, y1, "bottom")
    if task_num is not None:
        log(
            f"Image for task {task_num} expanded: {ox0 - x0}px left, {x1 - ox1}px right, {oy0 - y0}px up, {y1 - oy1}px down"
        )
    return x0, y0, x1 - x0, y1 - y0


def _detect_crops(
    img: np.ndarray, task_num: Optional[str] = None
) -> List[Tuple[np.ndarray, Tuple[int, int, int, int]]]:
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
    results = []
    for x, y, w, h in filtered:
        x, y, w, h = _expand_bbox(img, (x, y, w, h), task_num)
        results.append((img[y:y + h, x:x + w], (x, y, w, h)))
    return results


def _log_crops(
    original: np.ndarray,
    results: List[Tuple[Tuple[int, int, int, int], bool]],
    name: str,
    level: int = 0,
) -> None:
    """Save a copy of the image with crop annotations.

    Only the root invocation (``level == 0``) performs logging.
    """
    if level > 0:
        return
    log_dir = Path("img/log")
    log_dir.mkdir(parents=True, exist_ok=True)
    annotated = original.copy()
    for (x, y, w, h), success in results:
        # Draw candidate in blue first
        cv2.rectangle(annotated, (x, y), (x + w, y + h), (255, 0, 0), 2)
        color = (0, 255, 0) if success else (0, 0, 255)
        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
    cv2.imwrite(str(log_dir / f"{name}_debug.png"), annotated)


def _make_saver(output_folder: str, subject: str, version: str, counts: Dict[str, int]):
    exam_folder = Path(output_folder) / subject / version
    exam_folder.mkdir(parents=True, exist_ok=True)

    def _save(img: np.ndarray, task_num: str) -> bool:
        task_folder = exam_folder / task_num
        task_folder.mkdir(parents=True, exist_ok=True)
        counts[task_num] = counts.get(task_num, 0) + 1
        seq = counts[task_num]
        fname = f"{subject}_{version}_{task_num}_{seq}.png"
        # Check if an image with the same content (80% similarity) after resizing already exists
        for existing in task_folder.glob("*.png"):
            existing_img = cv2.imread(str(existing))
            if existing_img is not None:
                resized_existing = cv2.resize(existing_img, (img.shape[1], img.shape[0]))
                similarity = cv2.matchTemplate(resized_existing, img, cv2.TM_CCOEFF_NORMED)
                if np.max(similarity) > 0.8:
                    log(f"Skipping duplicate image {fname} in {task_folder}")
                    return False
        path = task_folder / fname
        ok, buf = cv2.imencode(".png", img)
        if ok:
            with open(path, "wb") as f:
                f.write(buf.tobytes())
            return True
        log(f"[ERROR] Could not encode image for {path}")
        return False

    return _save


async def _process_image(
    img: np.ndarray,
    task_num: str,
    save_func,
    attempt: int = 0,
    img_name: Optional[str] = None,
) -> bool:
    if img_name is None:
        img_name = uuid.uuid4().hex
    text = await _get_text(img)
    ratio = len(text) / (text.count("\n") + 1)

    words = re.findall(r'\b[a-zA-ZæøåÆØÅ0-9]+\b', text)
    words = [re.sub(r'(.)\1{2,}', r'\1', w) for w in words]
    avg_word_len = sum(len(word) for word in words) / len(words) if words else 0

    # Heuristikker
    len_max = 250
    ratio_max = 20
    avg_word_len_max = 3

    len_bool = len(text) > len_max
    ratio_bool = ratio > ratio_max
    avg_bool = avg_word_len > avg_word_len_max
    admin_bool = any(word in text.lower() for word in ["format", "words:", "maks poeng:"])
    small_size_bool = img.shape[0] + img.shape[1] < 750 or img.shape[0] < 280 or img.shape[1] < 280
    large_size_bool = img.shape[0] > 2800 or img.shape[1] > 2800
    color_bool = len(np.unique(img[::max(1,img.shape[0]//100),::max(1,img.shape[1]//100)], axis=0)) < 10

    code_bool = int(await prompt_to_text.async_prompt_to_text(
        "ONLY RESPOND WITH A 1 OR 0. NOTHING ELSE!!!! "
        "Does this text contain code? Answer with a 1 if it does, or a 0 if it does not. "
        "Just because comparison operators are used (e.g. x=0, kx<mg, kx=mg, kx>mg), does not mean it necessarily has code, and it is probably just normal text. "
        "It needs to have actual cohesive programming for it to be code. "
        "Here is the text: " + text,
        max_tokens=1000,
        is_num=False,
        max_len=2,
    ))

    should_attempt_crop = (avg_bool and (len_bool or ratio_bool)) or admin_bool or large_size_bool
    should_skip_image = (small_size_bool or color_bool or code_bool) or attempt >= 5

    if not should_attempt_crop and not should_skip_image:
        log(f"Saving image for task {task_num}.")
        success = save_func(img, task_num)
        if attempt == 0:  # Only log for the root invocation
            _log_crops(
                img,
                [((0, 0, img.shape[1], img.shape[0]), success)],
                img_name,
                level=attempt,
            )
        return success

    if should_skip_image:
        log(
            f"Skipping image for task {task_num} due to {'small size' if small_size_bool else 'color' if color_bool else 'code' if code_bool else 'attempt limit reached'}."
        )
        return False

    subs = _detect_crops(img, task_num)
    if not subs:
        log(f"Skipping image for task {task_num} due to no crops detected.")
        return False

    results: List[Tuple[Tuple[int, int, int, int], bool]] = []
    for i, (sub, bbox) in enumerate(subs):
        log(
            f"Cropping image for task {task_num} due to {'text contents' if avg_bool and (len_bool or ratio_bool) else 'admin text' if admin_bool else 'large size'}."
        )
        success = await _process_image(
            sub, task_num, save_func, attempt + 1, f"{img_name}_{i}"
        )
        results.append((bbox, success))
    if attempt == 0:  # Only log for the root invocation
        _log_crops(img, results, img_name, level=attempt)
    return any(success for _, success in results)


"""
def popup_img():
    root = tk.Tk()
    root.withdraw()
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)

    # Resize image to fit in a max 600x600 window, keeping aspect ratio
    max_size = 800
    w, h = pil_img.size
    scale = min(max_size / w, max_size / h, 1.0)
    new_size = (int(w * scale), int(h * scale))
    pil_img_resized = pil_img.resize(new_size, Image.Resampling.LANCZOS)

    img_tk = ImageTk.PhotoImage(pil_img_resized)
    top = tk.Toplevel(root)
    top.title(f"Image Ratio Warning - Task {task_num}")
    label = tk.Label(top, text=keep)
    label.pack()
    img_label = tk.Label(top, image=img_tk)
    img_label.image = img_tk  # Keep reference
    img_label.pack()
    ok_btn = tk.Button(top, text="OK", command=top.destroy)
    ok_btn.pack()

    def on_enter(event):
        top.destroy()

    top.bind("<Return>", on_enter)  # Bind Enter key to close window

    # Set window size to fit image and center on screen
    top.update_idletasks()
    win_w = top.winfo_width()
    win_h = top.winfo_height()
    screen_w = top.winfo_screenwidth()
    screen_h = top.winfo_screenheight()
    x = (screen_w // 2) - (win_w // 2)
    y = (screen_h // 2) - (win_h // 2)
    top.geometry(f"+{x}+{y}")
    root.wait_window(top)
    root.destroy()
"""
async def extract_figures(
    pdf_path: str,
    containers: List[Dict],
    task_map: Dict[int, str],
    subject: str,
    version: str,
    output_folder: Optional[str] = None,
) -> None:
    start_time = perf_counter()
    num_imgs = sum(1 for c in containers if c.get("type") == "image")
    log(f"Figures extracted: {num_imgs}")
    output_folder = output_folder or str(IMG_DIR)
    exam_folder = Path(output_folder) / subject / version
    if exam_folder.exists():
        shutil.rmtree(exam_folder)
        log(f"Rydder tidligere bilder i {exam_folder}")
    log_dir = Path("img/log")
    if log_dir.exists():
        shutil.rmtree(log_dir)
        log(f"Tømmer logg-mappen {log_dir}")
    doc = fitz.open(pdf_path)
    counts: Dict[str, int] = {}
    save = _make_saver(output_folder, subject, version, counts)
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
        task = asyncio.create_task(
            _process_image(img, task_num, save, img_name=f"{idx}")
        )
        tasks.append(task)
    await asyncio.gather(*tasks)
    doc.close()
    log(f"Figure extraction complete in {perf_counter() - start_time:.2f}s")


async def main_async(
    pdf_path: str,
    subject: str = "TEST",
    version: str = "1",
    expected_tasks: Optional[List[str]] = None,
) -> List[str]:
    """Compatibility wrapper used by legacy tests."""
    log("extract_images.main_async")
    containers, task_map, ranges, assigned, _ = await task_boundaries.detect_task_boundaries(
        pdf_path, expected_tasks
    )
    await extract_figures(pdf_path, containers, task_map, subject, version)
    return assigned

