import os
import fitz  # PyMuPDF
import asyncio
from google.cloud import vision
from pathlib import Path
import sys
import prompt_to_text
import difflib
from project_config import *

sys.stdout.reconfigure(encoding='utf-8')

json_path = os.getenv("OCRACLE_JSON_PATH")
if not json_path or not os.path.exists(json_path):
    raise FileNotFoundError(f"[ERROR] JSON path not found or invalid: {json_path}")
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = json_path


def detect_text(image_content):
    try:
        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=image_content)
        response = client.text_detection(image=image)
        texts = response.text_annotations

        if response.error.message:
            raise Exception(f"[ERROR] Vision API error: {response.error.message}")

        return texts[0].description.replace('\n', ' ') if texts else ''
    except Exception as e:
        print(f"[ERROR] OCR failed for an image: {e}")
        return ''

def pdf_to_images(pdf_path):
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
        PROMPT_CONFIG +
        "The provided text is extracted from a multi-page document, with each page clearly marked as === PAGE x ===. "
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

async def main_async(input_path, output_path):
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

def main(argv):
    if len(argv) < 2:
        print("Usage: python draw_task_lines.py <input.pdf> [output.pdf]")
        return

    input_path = Path(argv[1])
    output_path = Path(argv[2]) if len(argv) > 2 else input_path.with_stem(input_path.stem + "_tasks")

    asyncio.run(main_async(str(input_path), str(output_path)))

if __name__ == "__main__":
    main(sys.argv)