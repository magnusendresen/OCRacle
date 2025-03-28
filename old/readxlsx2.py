import pandas as pd
import os

def load_data(file_path):
    """Reads an Excel file and returns the data as separate input and output arrays."""
    try:
        # Load data from Excel file
        data = pd.read_excel(file_path)
        
        # Assuming the first column is 'inputs' and the second column is 'outputs'
        inputs = data.iloc[:, 0].values
        outputs = data.iloc[:, 1].values
        
        print(f"[INFO] Successfully loaded data from {file_path}")
        return inputs, outputs
    except Exception as e:
        print(f"[ERROR] Failed to load data: {e}")
        return None, None

# Define the path to the file (update with your file path)
file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dataset', 'dataset.xlsx')


# Load data
inputs, outputs = load_data(file_path)

print(outputs[0])


