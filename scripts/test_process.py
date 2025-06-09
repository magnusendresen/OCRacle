import asyncio
from pathlib import Path

from project_config import PDF_DIR
from extract_images_with_tasks import main_async

PDF_DIRECTORY = PDF_DIR


async def main():
    pdfs = list(Path(PDF_DIRECTORY).glob("*.pdf"))
    if not pdfs:
        print("No PDF files found in", PDF_DIRECTORY)
        return
    for pdf in pdfs:
        print("Processing", pdf)
        await main_async(str(pdf), subject="TEST", version="v1")


if __name__ == "__main__":
    asyncio.run(main())
