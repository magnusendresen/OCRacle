import os
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import T5Tokenizer, T5ForConditionalGeneration, AdamW

# ---- Function to Load and Process Dataset ----
def load_dataset():
    file_path = os.path.join(os.path.dirname(__file__), "..", "dataset", "dataset.dsv")
    file_path = os.path.normpath(file_path)

    try:
        df = pd.read_csv(file_path, delimiter=";", on_bad_lines="skip", low_memory=False)
        if "INPUT" not in df.columns or "TASK" not in df.columns:
            raise ValueError("Dataset must contain 'INPUT' and 'TASK' columns.")
        print(f"Loaded dataset with {len(df)} rows.")
        return df
    except Exception as e:
        print(f"Error reading dataset: {e}")
        exit()

# ---- Function to Preprocess Data ----
def preprocess_data(row, tokenizer):
    try:
        input_text = str(row["INPUT"])
        target_text = str(row["TASK"])
        return {
            "input_text": input_text,  # Store original input for verification
            "target_text": target_text,  # Store original target for verification
            "input_ids": tokenizer(input_text, truncation=True, padding="max_length", max_length=512)["input_ids"],
            "attention_mask": tokenizer(input_text, truncation=True, padding="max_length", max_length=512)["attention_mask"],
            "labels": tokenizer(target_text, truncation=True, padding="max_length", max_length=10)["input_ids"]
        }
    except Exception as e:
        print(f"Error processing row: {e}")
        return None

# ---- Dataset Class ----
class TaskDataset(Dataset):
    def __init__(self, tokenized_data):
        self.data = tokenized_data

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        sample = self.data[idx]
        return {
            "input_text": sample["input_text"],  # Keep original input text
            "target_text": sample["target_text"],  # Keep original target text
            "input_ids": torch.tensor(sample["input_ids"]),
            "attention_mask": torch.tensor(sample["attention_mask"]),
            "labels": torch.tensor(sample["labels"]),
        }

# ---- Main Training Function ----
def main():
    # Load dataset
    df = load_dataset()

    # Initialize tokenizer
    tokenizer = T5Tokenizer.from_pretrained("t5-small")

    # Process dataset
    processed_data = [preprocess_data(row, tokenizer) for _, row in df.iterrows()]
    processed_data = [data for data in processed_data if data is not None]

    # Create dataset and dataloader
    batch_size = 16
    dataset = TaskDataset(processed_data)
    data_loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=2, pin_memory=True)

    # Load Model
    model = T5ForConditionalGeneration.from_pretrained("t5-small")
    optimizer = AdamW(model.parameters(), lr=5e-5)

    # Move model to device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    print("Starting training...")
    epochs = 3
    model.train()

    for epoch in range(epochs):
        total_loss = 0
        for batch_idx, batch in enumerate(data_loader):
            optimizer.zero_grad()
            batch_input_text = batch.pop("input_text")  # Extract original input text
            batch_target_text = batch.pop("target_text")  # Extract original target text
            batch = {key: val.to(device) for key, val in batch.items()}

            # Print example data for verification
            if batch_idx < 5:  # Print only for first 5 batches to avoid spam
                print(f"\n📌 Training Batch {batch_idx + 1}:")
                for i in range(min(len(batch_input_text), 3)):  # Show up to 3 examples per batch
                    print(f"  🔹 Input (first 20 chars): {batch_input_text[i][:20]}")
                    print(f"  🎯 Target: {batch_target_text[i]}")

            outputs = model(**batch)
            loss = outputs.loss
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        print(f"Epoch {epoch + 1}/{epochs} completed. Average Loss: {total_loss / len(data_loader):.4f}")

    # Save model
    output_dir = os.path.join(os.path.dirname(__file__), "t5_finetuned_task")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    print(f"Model saved to {output_dir}")

# ---- Ensure Script Runs Correctly ----
if __name__ == '__main__':
    main()
