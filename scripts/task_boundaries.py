"""Utilities for detecting task boundaries in a PDF.

This module isolates the logic for scanning a PDF file and determining
which text/image containers belong to each task. The heavy lifting is
still done via Google Vision to read text from image blocks.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Dict, List, Tuple, Optional

import fitz
from google.cloud import vision

import prompt_to_text
from project_config import PROMPT_CONFIG


json_path = os.getenv("OCRACLE_JSON_PATH")
if not json_path or not os.path.exists(json_path):
    raise FileNotFoundError(f"[ERROR] JSON path not found or invalid: {json_path}")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = json_path


TASK_PATTERN = re.compile(r"(Oppg(?:ave|\xE5ve)?|Task|Problem)\s*(\d+[a-zA-Z]?)", re.IGNORECASE)


def detect_text(image_content: bytes) -> str:
    """Run Google Vision OCR on the given image content."""
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
    """Return a list of text/image containers extracted from the PDF."""
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


async def _query_markers(prompt: str) -> List[int]:
    resp = await prompt_to_text.async_prompt_to_text(prompt, max_tokens=2000, is_num=False, max_len=1000)
    return sorted(set(int(tok) for tok in re.findall(r"\d+", str(resp)))) if resp else []


async def query_start_markers(containers: List[Dict]) -> List[int]:
    prompt = (
        PROMPT_CONFIG
        + f"Below is the text from a PDF split into containers numbered 0-{len(containers) - 1}. "
        "Identify the number of every container that clearly marks the start of a new TASK. "
        "Respond only with the numbers separated by commas. "
        "Here is the text: "
        + build_container_string_with_identifier(containers)
    )
    markers = await _query_markers(prompt)

    def _is_summary(text: str) -> bool:
        t = text.lower()
        return "maks poeng" in t and "oppgavetype" in t

    return [idx for idx in markers if not _is_summary(containers[idx].get("text", ""))]


async def confirm_task_text(containers: List[Dict], ranges: List[Tuple[int, int]]) -> List[int]:
    if not ranges:
        return []

    check_indices = list(range(min(3, len(ranges))))
    tail_start = max(len(ranges) - 3, 3)
    if tail_start < len(ranges):
        check_indices.extend(range(tail_start, len(ranges)))

    remove: List[int] = []
    for idx in check_indices:
        start, end = ranges[idx]
        text = "\n\n".join(c.get("text", "") for c in containers[start:end])
        prompt = (
            PROMPT_CONFIG
            + "MAKE SURE YOU ONLY RESPOND WITH 0 OR 1!!! "
            + "Does this text very clearly include a task, or is it unrelated to a task - e.g. exam administration information? "
            + "If the text includes a task, respond with 1, otherwise 0. "
            + "Here is the text:" + text
        )
        ans = await prompt_to_text.async_prompt_to_text(prompt, max_tokens=5, is_num=False, max_len=2)
        if str(ans).strip() == "0":
            remove.extend(range(start, end))
    return sorted(set(remove))


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


async def detect_task_boundaries(pdf_path: str, expected_tasks: Optional[List[str]] = None):
    """Return containers and task ranges detected in the given PDF."""
    containers = await list_pdf_containers(pdf_path)
    task_map, ranges, assigned = await _assign_tasks(containers, expected_tasks)
    to_remove = await confirm_task_text(containers, ranges)
    if to_remove:
        containers = [c for i, c in enumerate(containers) if i not in to_remove]
        task_map, ranges, assigned = await _assign_tasks(containers, expected_tasks)
    return containers, ranges, assigned


