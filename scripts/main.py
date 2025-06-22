import ocr_pdf
import text_normalization
import task_processing
import object_to_json
from project_config import *

def main():
    """Run the full OCR and task processing workflow."""
    # Step 1: Run OCR PDF to get raw text
    rawtext = ocr_pdf.main()

    # Step 2: Normalize text
    rawtext = text_normalization.normalize_text(rawtext)

    # Step 4: Process tasks using taskseparation
    tasks = task_processing.main(rawtext)

    # Step 5: Write the objects to the json file
    object_to_json.main(tasks)

    # Step 5: Write the tasks to an output file
    # with open('output.txt', 'w', encoding='utf-8') as f:
    #     for task in tasks:
    #         f.write(task + '\n\n')

if __name__ == "__main__":
    main()
