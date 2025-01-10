import os
from tkinter import Tk, filedialog

def process_txt_file(file_path):
    try:
        # Mapping of words to replace
        replacements = {
            "eksamen": "exam",
            "oppgave": "task",
            "tema": "topic",
            "tekst": "text",
            "maksPoeng": "points",
            "bilder": "images",
            "kode": "code"
        }

        # Read file content
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        # Replace words
        for old_word, new_word in replacements.items():
            content = content.replace(old_word, new_word)

        # Write updated content back to file
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)

        print(f"[SUCCESS] Updated file: {file_path}")
    except Exception as e:
        print(f"[ERROR] Could not process file {file_path}: {e}")

if __name__ == "__main__":
    try:
        # Hide the root Tkinter window
        Tk().withdraw()

        # Open a dialog to select a folder
        folder_path = filedialog.askdirectory(title="Select Folder")

        if folder_path:
            txt_files = [f for f in os.listdir(folder_path) if f.endswith("_fasit.txt")]
            total_files = len(txt_files)

            if total_files == 0:
                print("[INFO] No '_fasit.txt' files found in the selected folder.")
            else:
                print(f"[INFO] Found {total_files} '_fasit.txt' file(s) in the folder.")

                # Loop through all matching files with progress tracking
                for index, file_name in enumerate(txt_files, start=1):
                    file_path = os.path.join(folder_path, file_name)
                    print(f"[INFO] Processing file {index}/{total_files}: {file_name}")
                    process_txt_file(file_path)

                print("[INFO] Processing completed.")
        else:
            print("[WARNING] No folder selected.")
    except Exception as e:
        print(f"[CRITICAL ERROR] An unexpected error occurred: {e}")
