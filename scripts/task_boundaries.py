import asyncio
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import fitz
from PIL import Image

import prompt_to_text
from project_config import PROMPT_CONFIG
from ocr_pdf import detect_text

# Google credentials
json_path = os.getenv("OCRACLE_JSON_PATH")
if not json_path or not os.path.exists(json_path):
    raise FileNotFoundError(f"[ERROR] JSON path not found or invalid: {json_path}")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = json_path


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


async def _query_markers(prompt: str) -> List[int]:
    resp = await prompt_to_text.async_prompt_to_text(
        prompt, max_tokens=2000, is_num=False, max_len=1000
    )
    return (
        sorted(set(int(tok) for tok in __import__('re').findall(r"\d+", str(resp))))
        if resp
        else []
    )


async def query_start_markers(containers: List[Dict]) -> List[int]:
    prompt = (
        PROMPT_CONFIG
        + f"Below is the text from a PDF split into containers numbered 0-{len(containers) - 1}. "
        "Identify the number of every container that clearly marks the start of a new TASK. "
        "For example phrases beginning with 'Oppgave 1', 'Oppgave 2a' and similar. "
        "In some cases, the beginning of a task may just be indicated by a number. "
        "Be careful to not make markers where the following text is clearly not a task. "
        "Respond only with the numbers separated by commas. "
        "Here is the text: "
        + build_container_string_with_identifier(containers)
    )
    return await _query_markers(prompt)


TASK_PATTERN = __import__('re').compile(r"(Oppg(?:ave|\xE5ve)?|Task|Problem)\s*(\d+[a-zA-Z]?)", __import__('re').IGNORECASE)


def _fallback_markers(containers: List[Dict]) -> List[int]:
    markers = []
    for idx, c in enumerate(containers):
        if TASK_PATTERN.search(c.get("text", "")):
            markers.append(idx)
    return markers


async def _assign_tasks(
    containers: List[Dict], expected_tasks: Optional[List[str]] = None
) -> Tuple[Dict[int, str], List[Tuple[int, int]], List[str]]:
    markers = await query_start_markers(containers)
    if not markers:
        markers = _fallback_markers(containers)
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
        prompt = (
            PROMPT_CONFIG
            + "MAKE SURE YOU ONLY RESPOND WITH 0 OR 1!!! "
            + "Does this text very clearly include a task, or is it unrelated to a task - e.g. exam administration information? "
            + "If the text includes a lot of text that is not related to a task, it is likely not a task. "
            + "If it includes a task, respond with 1, if not respond with 0. "
            + "Do not reply with multiple numbers. Here is the text:"
            + text
        )
        ans = await prompt_to_text.async_prompt_to_text(
            prompt, max_tokens=5, is_num=False, max_len=2
        )
        if str(ans).strip() == "0":
            remove.extend(range(start, end))
    return sorted(set(remove))


async def detect_task_boundaries(pdf_path: str, expected_tasks: Optional[List[str]] = None):
    containers = await list_pdf_containers(pdf_path)
    task_map, ranges, assigned = await _assign_tasks(containers, expected_tasks)
    to_remove = await confirm_task_text(containers, ranges)
    if to_remove:
        containers = [c for i, c in enumerate(containers) if i not in to_remove]
        task_map, ranges, assigned = await _assign_tasks(containers, expected_tasks)
    return containers, ranges, assigned


def _merge_page_images(page_images: List[Image.Image]) -> Image.Image:
    if len(page_images) == 1:
        return page_images[0]
    width = max(img.width for img in page_images)
    total_height = sum(img.height for img in page_images)
    merged = Image.new("RGB", (width, total_height), color="white")
    y = 0
    for img in page_images:
        merged.paste(img, (0, y))
        y += img.height
    return merged


def _extract_task_image(doc: fitz.Document, containers: List[Dict], task_range: Tuple[int, int]) -> Optional[Image.Image]:
    page_boxes: Dict[int, List[Tuple[float, float, float, float]]] = {}
    start, end = task_range
    for c in containers[start:end]:
        page = c.get("page", 1) - 1
        bbox = c.get("bbox")
        if bbox:
            page_boxes.setdefault(page, []).append(bbox)
    page_images: List[Image.Image] = []
    for page_idx in sorted(page_boxes.keys()):
        boxes = page_boxes[page_idx]
        x0 = min(b[0] for b in boxes)
        y0 = min(b[1] for b in boxes)
        x1 = max(b[2] for b in boxes)
        y1 = max(b[3] for b in boxes)
        rect = fitz.Rect(x0, y0, x1, y1)
        page = doc[page_idx]
        pix = page.get_pixmap(clip=rect, dpi=300)
        mode = "RGBA" if pix.alpha else "RGB"
        img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
        if mode == "RGBA":
            img = img.convert("RGB")
        page_images.append(img)
    if not page_images:
        return None
    return _merge_page_images(page_images)


def load_boundaries(temp_dir: Path) -> Optional[Tuple[List[Tuple[int, int]], List[str], List[str]]]:
    jpath = temp_dir / "boundaries.json"
    if not jpath.exists():
        return None
    with open(jpath, "r", encoding="utf-8") as f:
        data = json.load(f)
    ranges = [tuple(r) for r in data.get("ranges", [])]
    assigned = [t.get("number") for t in data.get("tasks", [])]
    files = [t.get("file") for t in data.get("tasks", [])]
    return ranges, assigned, files


async def create_task_images(pdf_path: str, temp_dir: Path = Path(__file__).parent / "temp") -> List[Dict]:
    temp_dir.mkdir(parents=True, exist_ok=True)
    for f in temp_dir.glob("task_*.png"):
        f.unlink()
    containers, ranges, assigned = await detect_task_boundaries(pdf_path)
    doc = fitz.open(pdf_path)
    tasks_info = []
    for idx, r in enumerate(ranges, start=1):
        img = _extract_task_image(doc, containers, r)
        fname = f"task_{idx}.png"
        if img:
            img.save(temp_dir / fname)
        tasks_info.append({"number": assigned[idx - 1] if idx - 1 < len(assigned) else str(idx), "file": fname})
    with open(temp_dir / "boundaries.json", "w", encoding="utf-8") as f:
        json.dump({"tasks": tasks_info, "ranges": ranges}, f)
    doc.close()
    return tasks_info

