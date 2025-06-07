# ----- STEPS -----
# 1. Make a list of all containers in the PDF.
# 2. For each container, store its position, and store the text inside it (directly if its a text container, or by OCR if it's an image).
# 3. Place all the text from the containers into a single string, very clearly marking the start of each container with a comment like "=== CONTAINER x ===" where x is the container number.
# 4. Prompt the LLM with this string to identify task markers, which is the coordinate of the container that starts a task or subtask, or ends a task - always before the potential løsningsforslag.
# 5. Draw the lines in the PDF at the identified coordinates.
# 6. Save the modified PDF.

pdf_dir = "F:\OCRacle\pdf\mast2200.pdf"

import fitz  # PyMuPDF
import asyncio
from pathlib import Path

# List containers in a PDF, only y-coordinate (rounded), type, page, and container number
async def list_pdf_containers(pdf_path):
    containers = []
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                y_coord = round(block["bbox"][1])  # y0 (top) coordinate, rounded
                if "lines" in block:  # Text block
                    containers.append({
                        "type": "text",
                        "page": page_num + 1,
                        "y": y_coord
                    })
                elif "image" in block:  # Image block
                    containers.append({
                        "type": "image",
                        "page": page_num + 1,
                        "y": y_coord
                    })
        return containers
    except Exception as e:
        print(f"[ERROR] Failed to list PDF containers: {e}")
        return []
    
if __name__ == "__main__":

    containers = asyncio.run(list_pdf_containers(pdf_dir))
    for idx, container in enumerate(containers):
        print(f"CONTAINER {idx}: type={container['type']}, page={container['page']}, y={container['y']}")
