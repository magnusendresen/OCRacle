import os
from openai import OpenAI

# Hent API-nøkkel
api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise ValueError("API key not found in environment variables.")

# Initialiser DeepSeek-klient
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

MODEL_NAME = "deepseek-chat"

def prompt_to_text(prompt, max_retries=3, max_tokens=1000):
    """Raskt API-kall til DeepSeek."""
    for _ in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens
            )
            if response.choices:
                return response.choices[0].message.content.strip()
        except:
            pass  # Ignorer feil og prøv igjen

    return ""  # Returnerer tomt svar hvis alle forsøk feiler

# Eksempelbruk
print(prompt_to_text("Tell me about Star Wars in two sentences!"))
