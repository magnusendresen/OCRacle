import asyncio
import os
import re
from typing import Dict, List, Tuple

import cv2
import fitz
import numpy as np

import prompt_to_text
from project_config import IMG_DIR, PROMPT_CONFIG
from pdf_contents import (
    list_pdf_containers,
    query_start_markers,
    build_container_string,
)

TASK_RE = re.compile(r"(Oppg(?:ave|\xE5ve)?|Task|Problem)\s*(\d+[a-zA-Z]?)")


async def _assign_tasks(containers: List[Dict]) -> Dict[int, str]:
    markers = await query_start_markers(containers)
    if not markers:
        return {}
    markers = sorted(markers)
    ranges: List[Tuple[int, int]] = []
    for i, start in enumerate(markers):
        end = markers[i + 1] if i + 1 < len(markers) else len(containers)
        ranges.append((start, end))
    task_map: Dict[int, str] = {}
    for idx, (start, end) in enumerate(ranges, start=1):
        region_containers = containers[start:end]
        text = build_container_string(region_containers)
        prompt = (
            PROMPT_CONFIG
            + "Which task number is described in the following containers? "
            "Respond with the number only. "
            "Text:" + text
        )
        answer = await prompt_to_text.async_prompt_to_text(
            prompt, max_tokens=20, isNum=False, maxLen=20
        )
        m = TASK_RE.search(str(answer))
        task_num = m.group(2) if m else str(idx)
        for ci in range(start, end):
            task_map[ci] = task_num
    return task_map


async def extract_images_with_tasks(
    pdf_path: str, subject: str, version: str, output_folder: str = None
):
    output_folder = output_folder or str(IMG_DIR)
    containers = await list_pdf_containers(pdf_path)
    task_map = await _assign_tasks(containers)
    doc = fitz.open(pdf_path)
    counts: Dict[str, int] = {}
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
        counts[task_num] = counts.get(task_num, 0) + 1
        seq = f"{counts[task_num]:02d}"
        fname = f"{subject}_{version}_{task_num}_{seq}.png"
        cv2.imwrite(os.path.join(output_folder, fname), img)
        print(f"Saved {fname}")
    doc.close()


async def main_async(pdf_path: str, subject: str = "TEST", version: str = "1"):
    await extract_images_with_tasks(pdf_path, subject, version)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage: python extract_images_with_tasks.py <file.pdf> [subject] [version]"
        )
        sys.exit(1)
    path = sys.argv[1]
    subj = sys.argv[2] if len(sys.argv) > 2 else "TEST"
    ver = sys.argv[3] if len(sys.argv) > 3 else "1"
    asyncio.run(main_async(path, subj, ver))
