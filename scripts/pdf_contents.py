"""Utility to identify task boundaries in a PDF.

Steps performed:
1. Iterate over all text and image containers in the PDF.
2. Extract text from each container using direct extraction or Google Vision OCR for images.
3. Combine the text with markers ``=== CONTAINER x ===`` so the LLM can refer to specific containers by number.
4. Ask DeepSeek, using the text from all containers at once, which containers denote the start or end of tasks.
5. Draw separating lines in the PDF at the identified coordinates.
6. Save the modified PDF.
"""

import os
import re
import asyncio
from pathlib import Path
from typing import List, Dict

import fitz  # PyMuPDF
from google.cloud import vision

import prompt_to_text
from project_config import PROMPT_CONFIG

PDF_PATH = "F:\\OCRacle\\pdf\\mast2200.pdf"

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
        print(f"[INFO] Processing page {page_num + 1}/{len(doc)} with {len(blocks)} blocks")
        for block in blocks:
            x0, y0, x1, y1 = block["bbox"]
            if (x1 - x0) < 20 or (y1 - y0) < 8:
                continue
            container = {
                "page": page_num + 1,
                "y": round(y0),
                "type": "text" if "lines" in block else "image" if "image" in block or block.get("type") == 1 else "unknown"
            }
            if container["type"] == "unknown":
                continue
            container["text"] = await _extract_block_text(page, block)
            containers.append(container)
    return containers


def build_container_string(containers: List[Dict]) -> str:
    return "".join(
        f"\n\n=== CONTAINER {idx} ===\n{c.get('text', '')}"
        for idx, c in enumerate(containers)
    )


async def query_task_markers(containers: List[Dict]) -> List[int]:
    prompt = (
        PROMPT_CONFIG
        + f"Below is the text from a PDF split into containers numbered 0-{len(containers) - 1}. "
        "Many containers mark where a new task begins or an old one ends. "
        "Identify every container number that clearly starts or finishes a task, such as 'Oppgave 1' or concluding text. "
        "Respond only with the numbers separated by commas.\n"
        + build_container_string(containers)
    )
    resp = await prompt_to_text.async_prompt_to_text(prompt, max_tokens=2000, isNum=False, maxLen=1000)
    return sorted(set(int(tok) for tok in re.findall(r"\d+", str(resp)))) if resp else []


async def main_async(pdf_path: str):
    containers = await list_pdf_containers(pdf_path)
    print(f"[INFO] Extracted {len(containers)} containers")

    markers = await query_task_markers(containers)
    print("Task marker containers:", markers)

    if not markers:
        print("[INFO] No markers found; PDF not modified.")
        return

    doc = fitz.open(pdf_path)
    for idx in markers:
        if 0 <= idx < len(containers):
            c = containers[idx]
            page = doc[c["page"] - 1]
            y = max(c["y"] - 2, 0)
            rect = page.rect
            page.draw_line(fitz.Point(0, y), fitz.Point(rect.width, y), color=(1, 0, 0), width=2)

    output_path = Path(pdf_path).with_stem(Path(pdf_path).stem + "_lines")
    doc.save(str(output_path))
    doc.close()
    print(f"[SUCCESS] Saved annotated PDF to {output_path}")


def main(path: str = PDF_PATH):
    asyncio.run(main_async(path))


if __name__ == "__main__":
    main()
