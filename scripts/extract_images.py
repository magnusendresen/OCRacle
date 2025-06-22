import asyncio
import os
import re
import difflib
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pytesseract
from PIL import Image

import cv2
import fitz
import numpy as np
from google.cloud import vision

import prompt_to_text
from project_config import IMG_DIR, PROMPT_CONFIG, PROGRESS_FILE
import json
import time

json_path = os.getenv("OCRACLE_JSON_PATH")
if not json_path or not os.path.exists(json_path):
    raise FileNotFoundError(f"[ERROR] JSON path not found or invalid: {json_path}")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = json_path

TASK_RE = re.compile(r"(Oppg(?:ave|\xE5ve)?|Task|Problem)\s*(\d+[a-zA-Z]?)")

TEXT_LEN_LIMIT = 75
MIN_CONTOUR_AREA = 15_000
MIN_CONTOUR_HEIGHT = 120
OVERLAP_IOU_THRESHOLD = 0.3
CANNY_LOW, CANNY_HIGH = 50, 150
DILATE_KERNEL_SIZE = 5
DILATE_ITER = 2


def detect_text(image_content: bytes) -> str:
    try:
        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=image_content)
        response = client.text_detection(image=image)
        if response.error.message:
            raise Exception(response.error.message)
        texts = response.text_annotations
        return texts[0].description.replace("\n", " ") if texts else ""
    except Exception as e:
        print(f"[ERROR] OCR failed: {e}")
        return ""


async def _extract_block_text(page, block) -> str:
    if "lines" in block:
        lines = []
        for line in block["lines"]:
            parts = [span.get("text", "") for span in line.get("spans", [])]
            lines.append(" ".join(parts))
        return " ".join(lines).strip()
    elif "image" in block or block.get("type") == 1:
        try:
            clip = fitz.Rect(block["bbox"])
            pix = page.get_pixmap(clip=clip, dpi=300)
            img_bytes = pix.tobytes("png")
            return await asyncio.to_thread(detect_text, img_bytes)
        except Exception as e:
            print(f"[WARNING] Failed to OCR image block: {e}")
    return ""


async def list_pdf_containers(pdf_path: str) -> List[Dict]:
    containers = []
    doc = fitz.open(pdf_path)
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]
        print(
            f"[INFO] Processing page {page_num + 1}/{len(doc)} with {len(blocks)} blocks"
        )
        for block in blocks:
            x0, y0, x1, y1 = block["bbox"]
            if (x1 - x0) < 20 or (y1 - y0) < 8:
                continue
            container = {
                "page": page_num + 1,
                "y": round(y0),
                "bbox": (x0, y0, x1, y1),
                "type": (
                    "text"
                    if "lines" in block
                    else (
                        "image"
                        if "image" in block or block.get("type") == 1
                        else "unknown"
                    )
                ),
            }
            if container["type"] == "unknown":
                continue
            container["text"] = await _extract_block_text(page, block)
            containers.append(container)
    return containers


def build_container_string_with_identifier(containers: List[Dict]) -> str:
    return "".join(
        f"\n\n=== CONTAINER {idx} ({c.get('type', 'unknown')}) ===\n{c.get('text', '')}"
        for idx, c in enumerate(containers)
    )

def build_container_string(containers: List[Dict]) -> str:
    return "\n\n".join(c.get("text", "") for c in containers)




async def confirm_task_text(
    containers: List[Dict], ranges: List[Tuple[int, int]]
) -> List[int]:
    if not ranges:
        return []

    check_indices = list(range(min(3, len(ranges))))
    tail_start = max(len(ranges) - 3, 3)
    if tail_start < len(ranges):
        check_indices.extend(range(tail_start, len(ranges)))

    remove: List[int] = []
    for idx in check_indices:
        start, end = ranges[idx]
        text = build_container_string(containers[start:end])
        """
        print(f"\n\n\n Batch {idx}:\n{text}\n\n\n")
        time.sleep(15)
        """
        prompt = (
            PROMPT_CONFIG
            + "MAKE SURE YOU ONLY RESPOND WITH 0 OR 1!!! "
            + "Does this text very clearly include a task, or is it unrelated to a task - e.g. exam administration information? "
            + "Just because the text includes a number or the word 'task' (in any language) does not mean it is a task. "
            + "Tasks may be short or long, but you should be able to identify them by their content. "
            + "If the text includes a lot of text that is not related to a task, such as exam instructions, it is likely not a task. "
            + "If it includes a task, respond with with 1, if not respond with 0. "
            + "Do not reply with multiple numbers, only a single 1 or 0. "
            + "Here is the text:"
            + text
        )
        
        ans = await prompt_to_text.async_prompt_to_text(
            prompt, max_tokens=5, is_num=False, max_len=2
        )
        print("\n\n\n [KEEP/DROP] " + ans + "\n\n\n")


        if str(ans).strip() == "0":
            print(f"[CHECK] Range {idx} -> DROP ({ans})")
            remove.extend(range(start, end))
        else:
            print(f"[CHECK] Range {idx} -> KEEP ({ans})")

    return sorted(set(remove))


async def _query_markers(prompt: str) -> List[int]:
    resp = await prompt_to_text.async_prompt_to_text(
        prompt, max_tokens=2000, is_num=False, max_len=1000
    )
    return (
        sorted(set(int(tok) for tok in re.findall(r"\d+", str(resp)))) if resp else []
    )


async def query_start_markers(containers: List[Dict]) -> List[int]:
    prompt = (
        PROMPT_CONFIG
        + f"Below is the text from a PDF split into containers numbered 0-{len(containers) - 1}. "
        "Identify the number of every container that clearly marks the start of a new TASK. "
        "For example phrases beginning with 'Oppgave 1', 'Oppgave 2a' and similar. "
        "In some cases, the beginning of a task may just be indicated by a number. "
        "In other cases, the beginning may not be obvious, so you will have to look at the text as a whole. "
        "Be careful to not make markers where the text following text is clearly not a task, even though it may have a number or task phrase. "
        "Respond only with the numbers separated by commas. "
        "Here is the text: "
        + build_container_string_with_identifier(containers)
    )
    markers = await _query_markers(prompt)

    def _is_summary(text: str) -> bool:
        t = text.lower()
        return "maks poeng" in t and "oppgavetype" in t

    return [idx for idx in markers if not _is_summary(containers[idx].get("text", ""))]


async def query_solution_markers(
    containers: List[Dict], task_markers: List[int]
) -> List[int]:
    start_info = ",".join(str(m) for m in task_markers) if task_markers else "none"
    prompt = (
        PROMPT_CONFIG
        + f"Below is the text from a PDF split into containers numbered 0-{len(containers) - 1}. "
        f"The following container numbers mark the beginning of each task: {start_info}. "
        "Your job is to identify the container numbers that clearly begin a solution section. "
        "Solutions typically appear shortly after the task they solve and often start with phrases like 'Løsning' or 'Løsningsforslag'. "
        "Only mark a container if it unmistakably starts a solution. Be conservative and prefer fewer false positives. "
        "A solution MUST be a complete solution to the task, not just a few sentences that could be part of the task. "
        "Look for the contents of multiple containers as a whole in order to identify solutions that aren't marked with the keywords. "
        "Single containers with short text are unlikely to be solutions, but may be if containers collectively contain a complete solution. "
        "It is possible that there are no solutions in the text whatsoever, in these cases respond with an empty string. "
        "Identify container numbers that clearly begin solution text and respond only with the numbers separated by commas.\n"
        "Here is the text: " + build_container_string_with_identifier(containers)
    )

    return await _query_markers(prompt)


def pdf_to_images(pdf_path: str):
    images = []
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            try:
                pix = doc[page_num].get_pixmap(dpi=300)
                images.append(pix.tobytes("png"))
            except Exception as e:
                print(f"[WARNING] Failed to convert page {page_num} to image: {e}")
                images.append(None)
        return images
    except Exception as e:
        print(f"[ERROR] Failed to open PDF file: {e}")
        return []


async def perform_ocr(images):
    texts = []
    for idx, image in enumerate(images, start=1):
        if image:
            page_text = await asyncio.to_thread(detect_text, image)
        else:
            page_text = ""
        texts.append(page_text)

    all_text = ""
    for idx, page_text in enumerate(texts, start=1):
        all_text += f"\n\n=== PAGE {idx} ===\n\n{page_text}"

    return all_text


async def detect_task_markers(full_text: str):
    prompt = (
        PROMPT_CONFIG
        + "The provided text is extracted from a multi-page document, with each page clearly marked as === PAGE x ===. "
        "Identify distinctive markers or short introductory phrases that reliably signal the start of each new task or subtask. "
        "Provide each marker as the full beginning phrase (5-15 words) separated by commas. Do not include page markers like === PAGE x ===. "
        "If no clear markers exist, respond with an empty string. "
        "Here is the text: " + full_text
    )

    response = await prompt_to_text.async_prompt_to_text(
        prompt, max_tokens=2000, is_num=False, max_len=5000
    )
    markers = [marker.strip() for marker in response.split(',') if marker.strip()]

    unique_markers = list(dict.fromkeys(markers))
    print(f"[INFO] Detected markers: {unique_markers}")
    return unique_markers


async def insert_task_lines(doc, markers):
    if not markers:
        print("[WARNING] No task markers identified. Skipping line drawing.")
        return

    for page_num, page in enumerate(doc, start=1):
        page_text = page.get_text("text")
        for marker in markers:
            match_ratio = difflib.SequenceMatcher(None, marker.lower(), page_text.lower()).ratio()
            if match_ratio > 0.8:
                text_instances = page.search_for(marker)
                if text_instances:
                    y = min(inst.y0 for inst in text_instances)
                    line_y = max(y - 10, 0)
                    rect = page.rect
                    p1 = fitz.Point(0, line_y)
                    p2 = fitz.Point(rect.width, line_y)
                    page.draw_line(p1, p2, color=(0, 1, 0), width=2)
                    print(f"[INFO] Drawing line for marker '{marker}' on page {page_num}.")
                    break


async def annotate_pdf_tasks(input_path: str, output_path: str):
    images = pdf_to_images(input_path)
    if not images:
        print("[ERROR] No images generated from PDF. Exiting.")
        return

    full_text = await perform_ocr(images)
    if not full_text.strip():
        print("[ERROR] OCR produced no usable text. Exiting.")
        return

    doc = fitz.open(input_path)
    markers = await detect_task_markers(full_text)
    await insert_task_lines(doc, markers)
    doc.save(output_path)
    print(f"[SUCCESS] Saved annotated PDF to {output_path}")


def write_progress(updates: Dict[int, str]) -> None:
    """Write progress updates to the shared progress file."""
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
