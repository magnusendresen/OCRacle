import asyncio
import io
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Callable
from utils import log
from time import perf_counter

import fitz
import pytesseract
from PIL import Image

import prompt_to_text
from project_config import PROMPT_CONFIG


TASK_PATTERN = re.compile(r"(Oppg(?:ave|\xE5ve)?|Task|Problem)\s*(\d+[a-zA-Z]?)", re.IGNORECASE)


async def _extract_block_text(page, block) -> str:
    """Extract text from a block without using external OCR services."""
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
            rgb = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            return await asyncio.to_thread(pytesseract.image_to_string, rgb, lang="eng+nor")
        except Exception:
            return ""
    return ""


async def list_pdf_containers(
    pdf_path: str,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> List[Dict]:
    """Return text and image containers from the PDF.

    ``progress_callback`` is called with the current page index (0-based) after
    each page has been processed.
    """
    containers = []
    doc = fitz.open(pdf_path)
    for page_num, page in enumerate(doc):
        if page_num == 0:
            # Insert an extra container capturing the whole first page
            r = page.rect
            containers.append({
                "page": 1,
                "y": -1,
                "bbox": (r.x0, r.y0, r.x1, r.y1),
                "type": "extra",
                "text": "",
            })
        blocks = page.get_text("dict")["blocks"]
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
        if progress_callback:
            progress_callback(page_num)
    log(f"Loaded PDF ({Path(pdf_path).name}) -> {len(containers)} containers found")
    return containers


def build_container_string_with_identifier(containers: List[Dict]) -> str:
    return "".join(
        f"\n\n=== CONTAINER {idx} ({c.get('type', 'unknown')}) ===\n{c.get('text', '')}"
        for idx, c in enumerate(containers)
    )


def build_container_string(containers: List[Dict]) -> str:
    return "\n\n".join(c.get("text", "") for c in containers)


async def confirm_task_text(
    containers: List[Dict],
    ranges: List[Tuple[int, int]],
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> List[int]:
    if not ranges:
        if progress_callback:
            progress_callback(1, 1)
        return []

    check_indices = list(range(min(3, len(ranges))))
    tail_start = max(len(ranges) - 3, 3)
    if tail_start < len(ranges):
        check_indices.extend(range(tail_start, len(ranges)))

    remove: List[int] = []
    for done, idx in enumerate(check_indices, start=1):
        start, end = ranges[idx]
        text = build_container_string(containers[start:end])
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
        if str(ans).strip() == "0":
            remove.extend(range(start, end))
        if progress_callback:
            progress_callback(done, len(check_indices))
    return sorted(set(remove))


async def _query_markers(prompt: str) -> List[int]:
    resp = await prompt_to_text.async_prompt_to_text(prompt, max_tokens=2000, is_num=False, max_len=1000)
    return sorted(set(int(tok) for tok in re.findall(r"\d+", str(resp)))) if resp else []


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


async def _assign_tasks(containers: List[Dict], expected_tasks: Optional[List[str]] = None) -> Tuple[Dict[int, str], List[Tuple[int, int]], List[str]]:
    markers = await query_start_markers(containers)
    if not markers:
        markers = [idx for idx, c in enumerate(containers) if TASK_PATTERN.search(c.get("text", ""))]
        if not markers:
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
    return task_map, ranges, assigned


async def detect_task_boundaries(
    pdf_path: str,
    expected_tasks: Optional[List[str]] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Tuple[List[Dict], Dict[int, str], List[Tuple[int, int]], List[str], Optional[Dict]]:
    start_time = perf_counter()
    containers_all = await list_pdf_containers(pdf_path, None)
    extra = containers_all[0] if containers_all else None
    containers = containers_all[1:]
    task_map, ranges, assigned = await _assign_tasks(containers, expected_tasks)

    check_indices = list(range(min(3, len(ranges))))
    tail_start = max(len(ranges) - 3, 3)
    if tail_start < len(ranges):
        check_indices.extend(range(tail_start, len(ranges)))
    total_steps = 1 + len(check_indices)
    completed = 1
    if progress_callback:
        progress_callback(completed, total_steps)

    log("Finding task boundaries")

    def _cb(done, _total):
        nonlocal completed
        completed += 1
        if progress_callback:
            progress_callback(completed, total_steps)

    to_remove = await confirm_task_text(containers, ranges, progress_callback=_cb)
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
    """Crop image regions for each task and return them as bytes.

    Each returned tuple contains the task number and the PNG bytes for a page
    segment. If ``temp_dir`` is provided the images are also written to disk for
    debugging purposes.
    """
    start_time = perf_counter()
    log(f"Cropping {len(ranges)} task regions")
    output: List[Tuple[str, bytes]] = []
    doc = fitz.open(pdf_path)
    for idx, (start, end) in enumerate(ranges):
        task_num = task_numbers[idx] if idx < len(task_numbers) else str(idx + 1)
        pages: Dict[int, List[Tuple[float, float, float, float]]] = {}
        for c in containers[start:end]:
            p = c["page"]
            pages.setdefault(p, [])
            pages[p].append(c["bbox"])
        for page_no, boxes in pages.items():
            x0 = min(b[0] for b in boxes)
            y0 = min(b[1] for b in boxes)
            x1 = max(b[2] for b in boxes)
            y1 = max(b[3] for b in boxes)
            rect = fitz.Rect(x0, y0, x1, y1)
            pix = doc[page_no - 1].get_pixmap(clip=rect, dpi=300)
            img_bytes = pix.tobytes("png")
            output.append((task_num, img_bytes))
            if temp_dir:
                Path(temp_dir).mkdir(parents=True, exist_ok=True)
                fname = Path(temp_dir) / f"task_{task_num}_{page_no}.png"
                with open(fname, "wb") as f:
                    f.write(img_bytes)
                # Uncomment for debugging
                # log(f"Wrote debug image {fname}")
        if progress_callback:
            progress_callback(idx)
    doc.close()
    log(f"crop_tasks finished in {perf_counter() - start_time:.2f}s")
    return output

