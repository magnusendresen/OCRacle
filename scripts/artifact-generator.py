import os
import pandas as pd
import numpy as np
import random
import re

# ---- Setup file path ----
dataset_path = os.path.join(os.path.dirname(__file__), "..", "dataset", "dataset.dsv")
dataset_path = os.path.normpath(dataset_path)  # Cross-platform compatibility

# ---- Function: Load Dataset Without Corrupting Semicolons ----
def load_dataset():
    try:
        df = pd.read_csv(dataset_path, delimiter=";", dtype=str, keep_default_na=False)  # Ensure all data remains string type
        print(f"✅ Loaded dataset with {len(df)} rows.")
        return df
    except Exception as e:
        print(f"❌ Error loading dataset: {e}")
        exit()

# ---- Function: Generate a Random Task Number ----
def generate_random_task_number():
    number = random.randint(1, 20)  # Random number between 1 and 20
    letter = random.choice(["", "a", "b", "c"])  # Optionally add a letter
    return f"{number}{letter}"

# ---- Function: Replace First Task Number in a String ----
def replace_first_task_number(text, new_task_number):
    return re.sub(r"^\d+[a-zA-Z]?", new_task_number, text, count=1)  # Replace only the first occurrence

# ---- Function: Remove Random Letter ----
def remove_random_letter(text, probability):
    text_list = list(text)
    for i in range(len(text_list)):
        if np.random.rand() < probability and len(text_list) > 1:
            rand_index = np.random.randint(len(text_list))
            text_list.pop(rand_index)
    return "".join(text_list)

# ---- Function: Add Random Spaces ----
def add_random_spaces(text, probability):
    text_list = list(text)
    for i in range(len(text_list)):
        if np.random.rand() < probability:
            text_list.insert(i, ' ')
    return "".join(text_list)

# ---- Function: Misinterpret Letters ----
def misinterpret_letters(text, probability):
    similar_characters = {
        '0': 'OQD', '1': 'Il|!7', '2': 'Z5', '3': 'E8', '4': 'AH', '5': 'S2', '6': 'bG',
        '7': 'T1', '8': 'B3', '9': 'gqP', 'a': 'eo', 'b': '6h', 'c': 'ke', 'd': 'cla',
        'e': 'ac', 'f': 'tr', 'g': '9q', 'h': 'nb', 'i': '1jl', 'j': 'iy', 'k': 'cx',
        'l': '1i', 'm': 'nrn', 'n': 'mh', 'o': '0a', 'p': 'q9', 'q': 'pg', 'r': 'nf',
        's': '5z', 't': 'f7', 'u': 'vw', 'v': 'uy', 'w': 'vv', 'x': 'ksk', 'y': 'jv', 'z': '2s'
    }
    
    text_list = list(text)
    for i in range(len(text_list)):
        if text_list[i] in similar_characters and np.random.rand() < probability:
            text_list[i] = random.choice(similar_characters[text_list[i]])
    
    return "".join(text_list)

# ---- Function: Replace Numbers with Random Digits ----
def replace_numbers_with_random(text, probability):
    text_list = list(text)
    for i in range(len(text_list)):
        if text_list[i].isdigit() and np.random.rand() < probability:
            text_list[i] = str(random.randint(1, 9))  # Replace with a random digit 1-9
    return "".join(text_list)

# ---- Function: Simulate OCR Mistakes While Keeping Task Number Intact ----
def simulate_ocr_mistakes(text, probability):
    text = remove_random_letter(text, probability)
    text = add_random_spaces(text, probability)
    text = misinterpret_letters(text, probability)
    text = replace_numbers_with_random(text, probability)
    return text

# ---- Function: Generate Variations of an Entry ----
def generate_variations(row):
    variations = []
    
    for _ in range(5):  # Create 5 variations per original row
        new_row = row.copy()
        new_task_number = generate_random_task_number()  # Generate a new random task number
        
        # Apply OCR mistakes while ensuring the task number is intact
        new_row["INPUT"] = replace_first_task_number(simulate_ocr_mistakes(row["INPUT"], probability=0.01), new_task_number)
        new_row["TEXT"] = replace_first_task_number(simulate_ocr_mistakes(row["TEXT"], probability=0.01), new_task_number)
        new_row["TASK"] = new_task_number  # Ensure TASK column matches the new number
        
        variations.append(new_row)

    return variations

# ---- Load dataset ----
df = load_dataset()
original_row_count = len(df)  # Store the original dataset size

# ---- Generate New Augmented Data ----
new_data = []
for i in range(original_row_count):  # Only process original rows
    new_data.extend(generate_variations(df.iloc[i]))

# Convert to DataFrame and Append to Original
new_df = pd.DataFrame(new_data, columns=df.columns)  # Ensure correct column structure
df = pd.concat([df, new_df], ignore_index=True)  # Append new rows

# ---- Save Back to `dataset.dsv` Without Corrupting Semicolons ----
try:
    df.to_csv(dataset_path, sep=";", index=False, quoting=3, encoding="utf-8")  # Quoting=3 ensures semicolons stay intact
    print(f"✅ Successfully added {len(new_df)} new rows. Total dataset now has {len(df)} rows.")
except Exception as e:
    print(f"❌ Error saving dataset: {e}")
