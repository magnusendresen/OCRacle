import ocrpdf
import textnormalization
import taskprocessing
import objecttojson

from project_paths import PROJECT_ROOT, IMG_DIR


def main():
    """Run the full OCR and task processing workflow."""
    # Step 1: Run OCR PDF to get raw text
    rawtext = ocrpdf.main()

    # Step 2: Normalize text
    rawtext = textnormalization.normalize_text(rawtext)

    # Step 4: Process tasks using taskseparation
    tasks = taskprocessing.main(rawtext)

    # Step 5: Write the objects to the json file
    objecttojson.main(tasks)

    # Step 5: Write the tasks to an output file
    # with open('output.txt', 'w', encoding='utf-8') as f:
    #     for task in tasks:
    #         f.write(task + '\n\n')


if __name__ == "__main__":
    main()
