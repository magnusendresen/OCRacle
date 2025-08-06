import asyncio
from pathlib import Path
from typing import Dict, List, Optional

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
        # Check if an image with the same content (80% similarity) after resizing already exists
        for existing in task_folder.glob("*.png"):
            existing_img = cv2.imread(str(existing))
            if existing_img is not None:
                resized_existing = cv2.resize(existing_img, (img.shape[1], img.shape[0]))
                similarity = cv2.matchTemplate(resized_existing, img, cv2.TM_CCOEFF_NORMED)
                if np.max(similarity) > 0.8:
                    log(f"Skipping duplicate image {fname} in {task_folder}")
                    return
        path = task_folder / fname
        ok, buf = cv2.imencode(".png", img)
        if ok:
            with open(path, "wb") as f:
                f.write(buf.tobytes())
            # Uncomment for debugging
            # log(f"Saved {path}")
        else:
            log(f"[ERROR] Could not encode image for {path}")

    return _save


async def _process_image(img: np.ndarray, task_num: str, save_func, attempt: int = 0):
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
    small_size_bool = img.shape[0] < 200 or img.shape[1] < 200
    large_size_bool = img.shape[0] > 2500 or img.shape[1] > 2500
    color_bool = len(np.unique(img[::max(1,img.shape[0]//100),::max(1,img.shape[1]//100)], axis=0)) < 10

    code_bool = int(await prompt_to_text.async_prompt_to_text(
        "ONLY RESPOND WITH A 1 OR 0. NOTHING ELSE!!!! "
        "Does this text contain code? Answer with a 1 if it does, or a 0 if it does not. "
        "Just because comparison operators are used (e.g. x=0, kx<mg, kx=mg, kx>mg), does not mean it necessarily has code, and it is probably just normal text. "
        "Here is the text: " + text,
        max_tokens=1000,
        is_num=False,
        max_len=2,
    ))

    should_attempt_crop = (avg_bool and (len_bool or ratio_bool)) or admin_bool or large_size_bool
    should_skip_image = (small_size_bool or color_bool or code_bool) or attempt >= 5

    if not should_attempt_crop and not should_skip_image:
        log(f"Saving image for task {task_num}.")
        save_func(img, task_num)
        return

    if should_skip_image:
        log(f"Skipping image for task {task_num} due to {'small size' if small_size_bool else 'color' if color_bool else 'code' if code_bool else 'attempt limit reached'}.")
        return

    subs = _detect_crops(img)
    if not subs:
        log(f"Skipping image for task {task_num} due to no crops detected.")
        return

    for sub in subs:
        log(f"Cropping image for task {task_num} due to {'text contents' if avg_bool and (len_bool or ratio_bool) else 'admin text' if admin_bool else 'large size'}.")
        await _process_image(sub, task_num, save_func, attempt + 1)


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
        task = asyncio.create_task(_process_image(img, task_num, save))
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

