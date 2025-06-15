import asyncio
from typing import List, Tuple, Dict

import fitz
from PIL import Image

from pdf_contents import list_pdf_containers, query_start_markers
from project_config import IMG_DIR


async def _get_task_ranges(pdf_path: str) -> Tuple[List[Dict], List[Tuple[int, int]]]:
    containers = await list_pdf_containers(pdf_path)
    markers = await query_start_markers(containers)
    markers = sorted(set([0] + markers + [len(containers)]))
    ranges = [(markers[i], markers[i + 1]) for i in range(len(markers) - 1)]
    return containers, ranges


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


def _extract_task_images(doc: fitz.Document, containers: List[Dict], task_range: Tuple[int, int]) -> Image.Image:
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


async def create_task_images(pdf_path: str) -> None:
    temp_dir = IMG_DIR / "temp"
    if temp_dir.exists():
        for f in temp_dir.glob("*.png"):
            f.unlink()
    else:
        temp_dir.mkdir(parents=True)

    containers, ranges = await _get_task_ranges(pdf_path)
    doc = fitz.open(pdf_path)

    for idx, r in enumerate(ranges, start=1):
        img = _extract_task_images(doc, containers, r)
        if img is None:
            continue
        out_path = temp_dir / f"task_{idx}.png"
        img.save(out_path)
        print(f"Saved {out_path}")
    doc.close()


def main(pdf_path: str):
    asyncio.run(create_task_images(pdf_path))


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python generate_task_images.py <file.pdf>")
    else:
        main(sys.argv[1])
