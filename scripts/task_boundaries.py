"""Utilities for splitting PDFs into logical tasks."""

import asyncio
import io
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from time import perf_counter

import tkinter
from tkinter import messagebox

import fitz
import pytesseract
from PIL import Image

import prompt_to_text
from project_config import PROMPT_CONFIG, load_prompt
from utils import log

CHECKED_TASKS = 5





async def _extract_block_text(page, block) -> str:
    """Return text from a text block or OCR an image block."""

    if "lines" in block:
        lines = []
        for line in block["lines"]:
            parts = [span.get("text", "") for span in line.get("spans", [])]
            lines.append(" ".join(parts))
        return " ".join(lines).strip()

    if "image" in block or block.get("type") == 1:
        try:
            clip = fitz.Rect(block["bbox"])
            pix = page.get_pixmap(clip=clip, dpi=300)
            rgb = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            return await asyncio.to_thread(
                pytesseract.image_to_string, rgb, lang="eng+nor"
            )
        except Exception:
            return ""

    return ""


async def list_pdf_containers(
    pdf_path: str, progress_callback: Optional[Callable[[int], None]] = None
) -> List[Dict]:
    """Return text and image containers for every page in the PDF."""

    containers: List[Dict] = []
    with fitz.open(pdf_path) as doc:
        for page_num, page in enumerate(doc):
            if page_num == 0:
                # Include the entire first page as a separate container
                r = page.rect
                containers.append(
                    {
                        "page": 1,
                        "y": -1,
                        "bbox": (r.x0, r.y0, r.x1, r.y1),
                        "type": "extra",
                        "text": "",
                    }
                )

            for block in page.get_text("dict")["blocks"]:
                x0, y0, x1, y1 = block["bbox"]
                if (x1 - x0) < 20 or (y1 - y0) < 8:
                    continue

                block_type = (
                    "text"
                    if "lines" in block
                    else ("image" if "image" in block or block.get("type") == 1 else "unknown")
                )
                if block_type == "unknown":
                    continue

                text = await _extract_block_text(page, block)
                containers.append(
                    {
                        "page": page_num + 1,
                        "y": round(y0),
                        "bbox": (x0, y0, x1, y1),
                        "type": block_type,
                        "text": text,
                    }
                )

            if progress_callback:
                progress_callback(page_num)

    log(f"Loaded PDF ({Path(pdf_path).name}) -> {len(containers)} containers found")
    return containers


def build_container_string_with_identifier(containers: List[Dict]) -> str:
    page_extents: Dict[int, Tuple[float, float]] = {}
    for c in containers:
        p = c.get("page")
        x0, y0, x1, y1 = c.get("bbox", (0, 0, 0, 0))
        pw, ph = page_extents.get(p, (0.0, 0.0))
        page_extents[p] = (max(pw, x1), max(ph, y1))

    parts: List[str] = []
    for idx, c in enumerate(containers):
        typ = c.get("type", "unknown")
        if typ == "image":
            x0, y0, x1, y1 = c.get("bbox", (0, 0, 0, 0))
            pw, ph = page_extents.get(c.get("page"), (0.0, 0.0))
            if pw > 0 and ph > 0:
                if (x1 - x0) >= pw * 0.95 and (y1 - y0) >= ph * 0.95:
                    typ = "text"
        parts.append(f"\n\n=== CONTAINER {idx} ({typ}) ===\n{c.get('text', '')}")
    return "".join(parts)



def build_container_string(containers: List[Dict]) -> str:
    return "\n\n".join(c.get("text", "") for c in containers)


async def confirm_task_text(
    containers: List[Dict],
    ranges: List[Tuple[int, int]],
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> List[int]:
    """Ask the model to verify that the detected ranges actually contain tasks."""
    if not ranges:
        if progress_callback:
            progress_callback(1, 1)
        return []

    max_checks = min(CHECKED_TASKS, len(ranges))
    total_expected = max_checks * 2

    def _build_prompt(text: str) -> str:
        return (
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

    remove: List[int] = []
    done = 0

    for idx in range(max_checks):
        start, end = ranges[idx]
        log(f"Checking containers {start}-{end - 1} from start")
        text = build_container_string(containers[start:end])
        prompt = _build_prompt(text)
        ans = await prompt_to_text.async_prompt_to_text(
            prompt, max_tokens=5, is_num=False, max_len=2
        )
        done += 1
        if str(ans).strip() == "0":
            log(f"Containers {start}-{end - 1} invalid")
            remove.extend(range(start, end))
        else:
            log(f"Containers {start}-{end - 1} valid")
            break
        if progress_callback:
            progress_callback(done, total_expected)

    for offset in range(1, max_checks + 1):
        idx = len(ranges) - offset
        if idx < max_checks:
            break
        start, end = ranges[idx]
        log(f"Checking containers {start}-{end - 1} from end")
        text = build_container_string(containers[start:end])
        prompt = _build_prompt(text)
        ans = await prompt_to_text.async_prompt_to_text(
            prompt, max_tokens=5, is_num=False, max_len=2
        )
        done += 1
        if str(ans).strip() == "0":
            log(f"Containers {start}-{end - 1} invalid")
            remove.extend(range(start, end))
        else:
            log(f"Containers {start}-{end - 1} valid")
            break
        if progress_callback:
            progress_callback(done, total_expected)

    if progress_callback:
        progress_callback(done, total_expected)

    return sorted(set(remove))


async def _query_markers(prompt: str) -> List[int]:
    """Send a prompt to the language model and parse the numeric response."""
    resp = await prompt_to_text.async_prompt_to_text(
        prompt, max_tokens=2000, is_num=False, max_len=1000
    )
    return (
        sorted(set(int(tok) for tok in re.findall(r"\d+", str(resp)))) if resp else []
    )


async def query_start_markers(containers: List[Dict]) -> List[int]:
    """Ask the language model for indices that look like task starts."""

    temp_output_file = "temp_output.txt"

    with open(temp_output_file, "w", encoding="utf-8") as f:
        f.write(build_container_string_with_identifier(containers))

    llm_task_amount = await prompt_to_text.async_prompt_to_text(
        PROMPT_CONFIG + load_prompt("get_total_tasks") + build_container_string(containers),
        max_tokens=1000, is_num=True, max_len=3
    )

    log(f"LLM estimated {llm_task_amount} tasks.")

    prompt = (
        PROMPT_CONFIG
        + f"Below is the text from a PDF split into containers numbered 0-{len(containers) - 1} that represent a total of {llm_task_amount} tasks. "
        f"Identify the number of every container that clearly marks the start of a new task. Since there are {llm_task_amount} tasks, there should be a total of {llm_task_amount} markers. "
        "It may not always be consistent to just look for the word 'task' or 'oppgave' or a number in the text, "
        "so be sure to look at the text as a whole to understand where tasks are found. Although a rising number at the start of each container may be a good indicator. "
        "If it seems a container indicates the start of a task, make sure it is not related to the previous task, because then it should not be marked. "
        "Be careful to not make markers where the text following text is clearly not a task, even though it may have a number or task phrase. "
        "If a container ONLY includes the text 'Maks poeng' or similar, and nothing else, it is not a task. "
        "There may be just one container per task, or up to multiple containers per task, depending on how the PDF is structured. "
        "Look for patterns, e.g. if "
        "Respond only with the numbers separated by commas. "
        "Here is the text: "
        + build_container_string_with_identifier(containers)
    )
    markers = await _query_markers(prompt)

    return markers

    # def _is_summary(text: str) -> bool:
    #     t = text.lower()
    #     return "maks poeng" in t and "oppgavetype" in t

    # return [idx for idx in markers if not _is_summary(containers[idx].get("text", ""))]


async def query_final_marker(containers: List[Dict], last_start_idx: int) -> int:
    """Ask for the first container after ``last_start_idx`` that indicates the exam has ended.

    Returns a container index strictly greater than ``last_start_idx``. If none can be
    determined, returns ``len(containers)`` as a safe end boundary.
    """
    prompt = (
        PROMPT_CONFIG
        + f"Below is the text from a PDF split into containers numbered 0-{len(containers) - 1}. "
          "Identify the first container AFTER the last task that clearly indicates the exam is finished "
          "(for example, administrative tail text, solution sheets, grading info, or empty/non-task content). "
          f"The last detected task starts at container {last_start_idx}. "
          f"Respond ONLY with a single container number strictly greater than {last_start_idx}. "
          f"If there is no such container, respond with {len(containers)}. "
          "Here is the text: "
        + build_container_string_with_identifier(containers)
    )
    candidates = await _query_markers(prompt)

    log(f"Final boundary found: {candidates}")
    log(f"Final boundary found: {candidates}")
    log(f"Final boundary found: {candidates}")
    # Choose the smallest candidate that is a valid boundary (> last_start_idx)
    for c in sorted(candidates):
        if c > last_start_idx:
            return min(c, len(containers))
    return len(containers)


async def _assign_tasks(
    containers: List[Dict], expected_tasks: Optional[List[str]] = None
) -> Tuple[Dict[int, str], List[Tuple[int, int]], List[str]]:
    """Assign a task number to each container."""

    start_markers = await query_start_markers(containers)
    if not start_markers:
        root = tkinter.Tk()
        root.withdraw()
        messagebox.showwarning(
            "Ingen oppgaver funnet ved query_start_markers()."
            )
        root.destroy()
        return {}, [], []

    # Determine final end boundary after the last start marker.
    last_start_idx = max(start_markers)
    final_marker = await query_final_marker(containers, last_start_idx)

    # Build full marker list including 0 and the final marker boundary.
    markers = sorted(set([0] + start_markers + [final_marker]))
    # Build ranges as consecutive pairs of markers: (start_i, start_{i+1})
    ranges: List[Tuple[int, int]] = []
    for i in range(len(markers) - 1):
        start = markers[i]
        end = markers[i + 1]
        ranges.append((start, end))

    task_map: Dict[int, str] = {}
    assigned: List[str] = []
    for idx, (start, end) in enumerate(ranges, start=1):
        if expected_tasks and idx - 1 < len(expected_tasks):
            task_num = expected_tasks[idx - 1]
        else:
            task_num = str(idx)
        assigned.append(task_num)
        for ci in range(start, end):
            task_map[ci] = task_num
        log(
            f"Task {task_num}, start marker: {start}, "
            f"end marker: {end}"
        )
    return task_map, ranges, assigned


async def detect_task_boundaries(
    pdf_path: str,
    expected_tasks: Optional[List[str]] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Tuple[List[Dict], Dict[int, str], List[Tuple[int, int]], List[str], Optional[Dict]]:
    """Detect task sections in the given PDF and return cropped ranges."""

    start_time = perf_counter()
    containers_all = await list_pdf_containers(pdf_path, None)
    extra = containers_all[0] if containers_all else None
    containers = containers_all[1:]
    task_map, ranges, assigned = await _assign_tasks(containers, expected_tasks)

    check_steps = min(len(ranges), CHECKED_TASKS) * 2
    total_steps = 1 + check_steps
    completed = 1
    if progress_callback:
        progress_callback(completed, total_steps)

    log("Finding task boundaries")

    def _cb(done, _total):
        nonlocal completed
        completed += 1
        if progress_callback:
            progress_callback(completed, total_steps)

    to_remove = await confirm_task_text(
        containers, ranges, progress_callback=_cb
    )
    if to_remove:
        containers = [c for i, c in enumerate(containers) if i not in to_remove]
        task_map, ranges, assigned = await _assign_tasks(containers, expected_tasks)

    if progress_callback:
        progress_callback(total_steps, total_steps)

    log(f"Tasks detected: {len(ranges)}")
    log(f"detect_task_boundaries finished in {perf_counter() - start_time:.2f}s")
    return containers, task_map, ranges, assigned, extra





def crop_tasks(
    pdf_path: str,
    containers: List[Dict],
    ranges: List[Tuple[int, int]],
    task_numbers: List[str],
    temp_dir: Optional[str] = None,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> List[Tuple[str, bytes]]:
    """Crop page regions for each task and return them as PNG bytes."""

    start_time = perf_counter()
    log(f"Cropping {len(ranges)} task regions")
    output: List[Tuple[str, bytes]] = []

    with fitz.open(pdf_path) as doc:
        for idx, (start, end) in enumerate(ranges):
            task_num = task_numbers[idx] if idx < len(task_numbers) else str(idx + 1)
            pages: Dict[int, List[Tuple[float, float, float, float]]] = {}
            for c in containers[start:end]:
                pages.setdefault(c["page"], []).append(c["bbox"])

            for page_no, boxes in pages.items():
                page = doc[page_no - 1]
                x0, x1 = 0, page.rect.width
                y0 = min(b[1] for b in boxes)
                y1 = max(b[3] for b in boxes)
                rect = fitz.Rect(x0, y0, x1, y1)
                pix = page.get_pixmap(clip=rect, dpi=300)
                img_bytes = pix.tobytes("png")
                output.append((task_num, img_bytes))

                if temp_dir:
                    Path(temp_dir).mkdir(parents=True, exist_ok=True)
                    fname = Path(temp_dir) / f"task_{task_num}_{page_no}.png"
                    with open(fname, "wb") as f:
                        f.write(img_bytes)
                    # log(f"Wrote debug image {fname}")

                if (x1 - x0) < page.rect.width * 0.98:
                    root = tkinter.Tk()
                    root.withdraw()
                    messagebox.showwarning(
                        "Beskjæring av oppgave",
                        f"Advarsel: Oppgave {task_num} på side {page_no} er smalere enn hele siden. "
                        "Sjekk at beskjæringen er riktig.",
                    )
                    root.destroy()

            if progress_callback:
                progress_callback(idx)

    log(f"crop_tasks finished in {perf_counter() - start_time:.2f}s")
    return output


async def validate_containers(
    containers: List[Dict],
    task_map: Dict[int, str],
    ocr_text: str,
    ocr_tasks: Dict[str, str],
    task_numbers: List[str],
) -> Tuple[List[Dict], Dict[int, str], List[str], Dict[str, str]]:
    """Check container consistency against OCR results and filter invalid tasks."""

    log("Checking the text length and the pixel height of the container batches.")

    task_ranges: Dict[str, Tuple[float, float]] = {}
    for idx, c in enumerate(containers):
        task_id = task_map.get(idx)
        if not task_id:
            continue
        y0, y1 = c.get("bbox", (0, 0, 0, 0))[1], c.get("bbox", (0, 0, 0, 0))[3]
        if task_id in task_ranges:
            min_y, max_y = task_ranges[task_id]
            task_ranges[task_id] = (min(min_y, y0), max(max_y, y1))
        else:
            task_ranges[task_id] = (y0, y1)

    invalid_tasks = set()
    for task_num, text in ocr_tasks.items():
        if len(text) < 50:
            log(
                f"Task {task_num} has very short text, does likely not contain a task."
            )
            invalid_tasks.add(task_num)
            continue
        container = task_ranges.get(task_num)
        if container is None:
            log(f"Container for task {task_num} not found, skipping.")
            invalid_tasks.add(task_num)
            continue
        if container[1] - container[0] < 10:
            log(f"Container for task {task_num} is too small, skipping.")
            invalid_tasks.add(task_num)
            continue

    task_numbers = [t for t in task_numbers if t not in invalid_tasks]
    ocr_tasks = {t: ocr_tasks[t] for t in task_numbers if t in ocr_tasks}

    new_containers = []
    new_task_map: Dict[int, str] = {}
    for idx, c in enumerate(containers):
        task_id = task_map.get(idx)
        if task_id in invalid_tasks:
            continue
        new_idx = len(new_containers)
        new_containers.append(c)
        if task_id is not None:
            new_task_map[new_idx] = task_id

    return new_containers, new_task_map, task_numbers, ocr_tasks
