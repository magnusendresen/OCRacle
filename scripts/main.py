import ocrpdf
import cachetask
import textnormalization
import taskprocessing

# Step 1: Run OCR PDF to get raw text
rawtext = ocrpdf.main()

# Step 2: Normalize text
rawtext = textnormalization.normalize_text(rawtext)

# Step 3: Use cachetask to handle caching and selection of tasks
rawtext = cachetask.main(rawtext)

# Step 4: Process tasks using taskseparation
tasks = taskprocessing.main(rawtext)
# tasks = taskseparation.main(rawtext)

# Step 5: Write the tasks to an output file
# with open('output.txt', 'w', encoding='utf-8') as f:
#     for task in tasks:
#         f.write(task + '\n\n')