import os
import torch
from transformers import T5Tokenizer, T5ForConditionalGeneration

# ---- Last inn modellen ----
model_path = os.path.join(os.path.dirname(__file__), "t5_finetuned_task")
tokenizer = T5Tokenizer.from_pretrained(model_path)
model = T5ForConditionalGeneration.from_pretrained(model_path)

# Flytt til GPU hvis tilgjengelig
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval()

# ---- Prediksjonsfunksjon ----
def predict_task_number(raw_text):
    """
    Bruker den finjusterte AI-modellen for å forutsi oppgavenummeret.
    """
    inputs = tokenizer(raw_text, return_tensors="pt", truncation=True, padding="max_length", max_length=512)
    inputs = {key: val.to(device) for key, val in inputs.items()}  # Flytt til GPU hvis tilgjengelig

    with torch.no_grad():
        output = model.generate(**inputs, max_length=10)

    predicted_task_number = tokenizer.decode(output[0], skip_special_tokens=True)
    return predicted_task_number

# Skjulte oppgavenummer, vanskelig å tolke
task_texts = [
" 1 ( a ) Figuren viser et fagverk ABCDE. Fagverket er festet til en vegg via et fastlager i punkt A og et glidelager i punkt E. En punktlast på 30 kN virker i punkt C som angitt på figuren. 3m A ய 4m a ) Vis at fagverket er statisk bestemt. Skriv ditt svar her Format ΣΧ B D 4m 30 kN Words: 0 Maks poeng: 3"
]


# Test modellen på disse oppgavene
for text in task_texts:
    predicted_task = predict_task_number(text)
    print(f"Tekst: {text}\nPredikert Oppgavenummer: {predicted_task}\n")
