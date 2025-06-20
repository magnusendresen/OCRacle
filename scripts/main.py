import task_processing
import object_to_json

def main():
    """Run the full OCR and task processing workflow."""
    tasks = task_processing.main()

    # Step 5: Write the objects to the json file
    object_to_json.main(tasks)

    # Step 5: Write the tasks to an output file
    # with open('output.txt', 'w', encoding='utf-8') as f:
    #     for task in tasks:
    #         f.write(task + '\n\n')

if __name__ == "__main__":
    main()
