"""Utility to identify task boundaries in a PDF.

Steps performed:
1. Iterate over all text and image containers in the PDF.
2. Extract text from each container using direct extraction or Google Vision
   OCR for images.
3. Combine the text with markers ``=== CONTAINER x ===`` so the LLM can refer
   to specific containers by number.
4. Ask DeepSeek, in manageable container batches, which containers denote the
   start or end of tasks.
5. Return the resulting list of container indices (these can later be used to
   draw separating lines in the PDF).
"""

import os
import asyncio
from pathlib import Path
from typing import List, Dict

import fitz  # PyMuPDF
from google.cloud import vision

import prompt_to_text
from project_config import PROMPT_CONFIG

PDF_PATH = "F:\\OCRacle\\pdf\\mast2200.pdf"


json_path = os.getenv("OCRACLE_JSON_PATH")
if not json_path or not os.path.exists(json_path):
    raise FileNotFoundError(f"[ERROR] JSON path not found or invalid: {json_path}")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = json_path


def detect_text(image_content: bytes) -> str:
    """Run Google Vision OCR on the given image bytes."""
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
    if "lines" in block:  # text block
        lines = []
        for line in block.get("lines", []):
            parts = [span.get("text", "") for span in line.get("spans", [])]
            lines.append(" ".join(parts))
        return " ".join(lines).strip()
    if "image" in block or block.get("type") == 1:  # image block
        try:
            clip = fitz.Rect(block["bbox"])
            pix = page.get_pixmap(clip=clip, dpi=300)
            img_bytes = pix.tobytes("png")
            return await asyncio.to_thread(detect_text, img_bytes)
        except Exception as e:
            print(f"[WARNING] Failed to OCR image block: {e}")
    return ""


async def list_pdf_containers(pdf_path: str) -> List[Dict]:
    """Return a list of containers with coordinates and extracted text."""
    containers: List[Dict] = []
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    for page_num in range(total_pages):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]
        print(f"[INFO] Processing page {page_num + 1}/{total_pages} with {len(blocks)} blocks")
        for block in blocks:
            x0, y0, x1, y1 = block["bbox"]
            width = x1 - x0
            height = y1 - y0
            if width < 20 or height < 8:
                continue
            y_coord = round(y0)
            c = {
                "page": page_num + 1,
                "y": y_coord,
            }
            if "lines" in block:
                c["type"] = "text"
            elif "image" in block or block.get("type") == 1:
                c["type"] = "image"
            else:
                continue
            c["text"] = await _extract_block_text(page, block)
            containers.append(c)
    return containers


def build_container_string(containers: List[Dict], start_index: int = 0) -> str:
    """Return a string with container texts marked by their global index."""
    parts = []
    for idx, c in enumerate(containers, start=start_index):
        parts.append(f"\n\n=== CONTAINER {idx} ===\n{c.get('text', '')}")
    return "".join(parts)


async def query_task_markers(containers: List[Dict], chunk_size: int = 50) -> List[int]:
    """Query DeepSeek to find task boundary containers."""
    hits: List[int] = []
    for start in range(0, len(containers), chunk_size):
        end = min(start + chunk_size, len(containers))
        print(f"[INFO] Querying containers {start}-{end-1}")
        chunk_text = build_container_string(containers[start:end], start_index=start)
        prompt = (
            PROMPT_CONFIG
            + f"Which of these [{start}-{end-1}] containers indicate that a new task is starting or ending?\n"
            "Reply only with the container number(s) separated by a comma.\n"
            "Containers are marked with '=== CONTAINER x ===' followed by their text.\n"
            + chunk_text
        )
        resp = await prompt_to_text.async_prompt_to_text(
            prompt, max_tokens=2000, isNum=False, maxLen=1000
        )
        if resp:
            for tok in str(resp).replace("CONTAINER", "").split(","):
                tok = tok.strip()
                if tok.isdigit():
                    hits.append(int(tok))
    return sorted(set(hits))


async def main_async(pdf_path: str):
    containers = await list_pdf_containers(pdf_path)
    print(f"[INFO] Extracted {len(containers)} containers")
    markers = await query_task_markers(containers)
    print("Task marker containers:", markers)


def main(path: str = PDF_PATH):
    asyncio.run(main_async(path))


if __name__ == "__main__":
    main()

