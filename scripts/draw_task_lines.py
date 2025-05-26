import fitz  # PyMuPDF
import sys
import re
from pathlib import Path


TASK_PATTERN = re.compile(r"(Oppg(ave|\xE5ve)?\s*\d+[a-zA-Z]?|Task\s*\d+[a-zA-Z]?|Problem\s*\d+[a-zA-Z]?)", re.IGNORECASE)


def find_headings(page):
    """Return list of Y positions for task headings on the given page."""
    headings = []
    try:
        text_dict = page.get_text("dict")
    except Exception:
        return headings

    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            line_text = "".join(span.get("text", "") for span in line.get("spans", []))
            if TASK_PATTERN.search(line_text):
                y = line["bbox"][1]
                headings.append(y)
                break
    return headings


def insert_task_lines(doc):
    """Draw green lines between detected tasks."""
    heading_positions = []
    for page_no in range(len(doc)):
        page = doc[page_no]
        ys = find_headings(page)
        for y in ys:
            heading_positions.append((page_no, y))

    heading_positions.sort(key=lambda x: (x[0], x[1]))

    for (page_no, y) in heading_positions[1:]:  # skip first
        page = doc[page_no]
        line_y = max(y - 5, 0)
        rect = page.rect
        p1 = fitz.Point(0, line_y)
        p2 = fitz.Point(rect.width, line_y)
        page.draw_line(p1, p2, color=(0, 1, 0), width=2)


def main(argv):
    if len(argv) < 2:
        print("Usage: python draw_task_lines.py <input.pdf> [output.pdf]")
        return
    in_path = Path(argv[1])
    out_path = Path(argv[2]) if len(argv) > 2 else in_path.with_stem(in_path.stem + "_tasks")

    doc = fitz.open(str(in_path))
    insert_task_lines(doc)
    doc.save(str(out_path))
    print(f"Saved output to {out_path}")


if __name__ == "__main__":
    main(sys.argv)
