import os
from openai import OpenAI  # Using OpenAI SDK for DeepSeek

# Retrieve API key once
api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise ValueError("API key not found in environment variables.")

# Initialize DeepSeek client
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# Cost estimation
USD_PER_1M_INPUT_TOKENS = 0.27
USD_PER_1M_OUTPUT_TOKENS = 1.10

MODEL_NAME = "deepseek-chat"

def prompt_to_text(prompt, max_retries=3, max_tokens=1000):
    """Sends a request to DeepSeek API and retrieves the response efficiently."""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens
            )
            
            if not response.choices:
                continue  # Retry if response is empty

            # Token usage statistics
            usage = response.usage
            input_tokens, output_tokens, total_tokens = usage.prompt_tokens, usage.completion_tokens, usage.total_tokens
            
            # Cost Calculation
            request_cost = (input_tokens * USD_PER_1M_INPUT_TOKENS + output_tokens * USD_PER_1M_OUTPUT_TOKENS) / 1e6

            # Logging (optional)
            print(f"[DEEPSEEK] Tokens - Input: {input_tokens}, Output: {output_tokens}, "
                  f"Total: {total_tokens}, Cost: {request_cost:.4f} USD")

            return response.choices[0].message.content, total_tokens

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[ERROR] Request failed ({attempt+1}/{max_retries}), retrying... {e}")
            else:
                print(f"[ERROR] Final attempt failed: {e}")

    return "", 0  # Return empty response if all attempts fail

# Example Usage
result, _ = prompt_to_text("Hvor mange kriger tror do arc trooper fives har vært it?")
print(result)
