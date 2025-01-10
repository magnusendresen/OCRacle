from transformers import T5Tokenizer, T5ForConditionalGeneration, AdamW
from torch.utils.data import Dataset, DataLoader

model_name = "t5-small"
tokenizer = T5Tokenizer.from_pretrained(model_name)
model = T5ForConditionalGeneration.from_pretrained(model_name)

class MathDataset(Dataset):
    def __init__(self, inputs, outputs, tokenizer, max_len=128):
        self.inputs = inputs
        self.outputs = outputs
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.inputs)

    def __getitem__(self, idx):
        input_text = self.inputs[idx]
        output_text = self.outputs[idx]

        input_enc = self.tokenizer(
            input_text, max_length=self.max_len, padding="max_length", truncation=True, return_tensors="pt"
        )
        output_enc = self.tokenizer(
            output_text, max_length=self.max_len, padding="max_length", truncation=True, return_tensors="pt"
        )

        return {
            "input_ids": input_enc["input_ids"].squeeze(),
            "attention_mask": input_enc["attention_mask"].squeeze(),
            "labels": output_enc["input_ids"].squeeze(),
        }

# Create dataset and dataloader
inputs = ["f(x) = −3x^2 + 5x − 7", "The limit as x → ∞ is 1/2."]
outputs = ["f(x) = -3x^{2} + 5x - 7", "\\lim_{x \\to \\infty} \\frac{1}{2}"]
dataset = MathDataset(inputs, outputs, tokenizer)
dataloader = DataLoader(dataset, batch_size=2)

# Fine-tuning loop
optimizer = AdamW(model.parameters(), lr=5e-5)
model.train()

for epoch in range(3):  # Train for 3 epochs
    for batch in dataloader:
        optimizer.zero_grad()
        outputs = model(
            input_ids=batch["input_ids"],
            attention_mask=batch["attention_mask"],
            labels=batch["labels"],
        )
        loss = outputs.loss
        loss.backward()
        optimizer.step()
        print(f"Loss: {loss.item()}")

