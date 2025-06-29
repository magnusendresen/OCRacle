"""Utility to identify task boundaries in a PDF.

Steps performed:
1. Iterate over all text and image containers in the PDF.
2. Extract text from each container using direct extraction or Google Vision OCR for images.
3. Combine the text with markers ``=== CONTAINER x ===`` so the LLM can refer to specific containers by number.
4. Ask DeepSeek, using the text from all containers at once, which containers
   mark the start of each task and which mark when a solution section begins.
5. Draw separating lines in the PDF at the identified coordinates. Start lines
   are drawn in green while solution-start lines are drawn in red.
6. Save the modified PDF.
"""

import os
import re
import asyncio
from pathlib import Path
from typing import List, Dict, Tuple
import random

import fitz  # PyMuPDF
from google.cloud import vision

import prompt_to_text
from project_config import PROMPT_CONFIG

PDF_PATH = "C:\\Users\\magnu\\Documents\\Documents\\GitHub\\OCRacle\\pdf\\mast.pdf"

# --- Google Vision setup ---
json_path = os.getenv("OCRACLE_JSON_PATH")
if not json_path or not os.path.exists(json_path):
    raise FileNotFoundError(f"[ERROR] JSON path not found or invalid: {json_path}")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = json_path


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
            # print(
            #     f"[INFO] Added container {len(containers) - 1} of type {container['type']}"
            # )
    return containers


def build_container_string(containers: List[Dict]) -> str:
    return "".join(
        f"\n\n=== CONTAINER {idx} ({c.get('type', 'unknown')}) ===\n{c.get('text', '')}"
        for idx, c in enumerate(containers)
    )


async def confirm_task_text(
    containers: List[Dict], ranges: List[Tuple[int, int]]
) -> List[int]:
    """Check the first and last three container ranges for tasks.

    Returns a list of container indices belonging to ranges that do not
    contain a task."""

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
            + "Inneholder denne teksten en oppgave? Svar kun med 1 for ja eller 0 for nei. Tekst:"
            + text
        )
        ans = await prompt_to_text.async_prompt_to_text(
            prompt, max_tokens=5, is_num=True, max_len=5
        )
        keep = int(ans) == 1 if ans is not None else True
        status = "KEEP" if keep else "DROP"
        print(f"[CHECK] Range {idx} -> {status} ({ans})")
        if not keep:
            remove.extend(range(start, end))

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
        "Identify every container number that clearly marks the start of a new task or subtask, "
        "For example phrases beginning with 'Oppgave 1', 'Oppgave 2a' and similar. "
        "In some cases, the beginning of a task may just be indicated by a number. "
        "Look for patterns, e.g. if you think that a container including 4(b) is a marker, a container including 4(a) is also likely a marker. "
        "Be careful to not make markers where the text following text is clearly not a task, even though it may have a number or task phrase. "
        "Respond only with the numbers separated by commas.\n"
        + build_container_string(containers)
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
        "Here is the text: " + build_container_string(containers)
    )

    return await _query_markers(prompt)


async def main_async(pdf_path: str):
    containers = await list_pdf_containers(pdf_path)
    print(f"[INFO] Extracted {len(containers)} containers")

    start_markers = await query_start_markers(containers)
    solution_markers = await query_solution_markers(containers, start_markers)
    print("Start marker containers:", start_markers)
    print("Solution marker containers:", solution_markers)

    if not start_markers and not solution_markers:
        print("[INFO] No markers found; PDF not modified.")
        return

    doc = fitz.open(pdf_path)
    for idx in start_markers:
        if 0 <= idx < len(containers):
            c = containers[idx]
            page = doc[c["page"] - 1]
            y = max(c["y"] - 2, 0)
            rect = page.rect
            page.draw_line(
                fitz.Point(0, y), fitz.Point(rect.width, y), color=(0, 1, 0), width=2
            )

    for idx in solution_markers:
        if 0 <= idx < len(containers):
            c = containers[idx]
            page = doc[c["page"] - 1]
            y = max(c["y"] - 2, 0)
            rect = page.rect
            page.draw_line(
                fitz.Point(0, y), fitz.Point(rect.width, y), color=(1, 0, 0), width=2
            )

    output_path = Path(pdf_path).with_stem(Path(pdf_path).stem + "_lines")
    doc.save(str(output_path))
    doc.close()
    print(f"[SUCCESS] Saved annotated PDF to {output_path}")


def main(path: str = PDF_PATH):
    asyncio.run(main_async(path))


if __name__ == "__main__":
    main()
