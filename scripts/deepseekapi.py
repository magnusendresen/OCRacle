import os
import time
from openai import OpenAI  # Using OpenAI SDK for DeepSeek

# Retrieve API key from environment variables
api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise ValueError("API key not found in environment variables.")

# Initialize DeepSeek client
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# Cost estimation for DeepSeek API requests
usd_per_1m_input_tokens = 0.27
usd_per_1m_output_tokens = 1.10

MODEL_NAME = "deepseek-chat"
total_cost = 0  # Variable to accumulate total cost

print("[DEEPSEEK] Successfully connected to API!")

def prompt_to_text(prompt, max_retries=3, max_tokens=1000):
    """Sends a request, displays token usage, and calculates cost."""
    global total_cost  # Ensure the global cost variable is updated
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                stream=False
            )

            if response.choices:
                result_text = response.choices[0].message.content.strip()
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
                total_tokens = response.usage.total_tokens

                # Calculate the cost for this request
                request_cost = (input_tokens * usd_per_1m_input_tokens + output_tokens * usd_per_1m_output_tokens) / 1e6
                total_cost += request_cost  # Accumulate cost

                print(f"[DEEPSEEK] Token usage - Input: {input_tokens}, Output: {output_tokens}, Total: {total_tokens}, "
                f"Cost: {request_cost:.4f} USD, Cumulative Cost: {total_cost:.4f} USD")


                return result_text, total_tokens
            
            print(f"[ERROR] Invalid response (attempt {attempt+1}/{max_retries}). Retrying...")
        except Exception as e:
            print(f"[ERROR] Request failed: {e} (attempt {attempt+1}/{max_retries})")
            time.sleep(2)
    
    return "", 0  # Return empty response if all attempts fail

def main(text):
    """Main function that extracts tasks from a given text."""
    global total_cost  # Ensure total cost is updated

    nonchalant = "Do not explain what you are doing, just do it."

    while True:
        response, tokens_used = prompt_to_text(
            f"{nonchalant} How many tasks are in this text? Answer with a single number only: {text}"
        )
        try:
            amount = int(response)
            if amount > 0:
                break
        except ValueError:
            print("[ERROR] Invalid number returned, retrying...")

    print(f"[DEEPSEEK] Number of tasks found: {amount}")

    tasks = []
    instructions = [
        ("What is task ", "?: Write all text related to the task directly from the raw text, do not solve the task."),
        ("Remove all text related to Inspera and exam administration: ", ""),
        ("Translate the task to Norwegian Bokmål: ", ""),
        ("Write all text above on a single line (no newlines): ", "")
    ]

    for i in range(amount):
        task_valid = False
        while not task_valid:
            task = text
            for prefix, suffix in instructions:
                response, tokens_used = prompt_to_text(nonchalant + prefix + str(i+1) + suffix + task)
                task = response
                if not task:
                    print(f"[ERROR] No response for task {i+1}, retrying...")
                    break

            test = ""
            while test not in ["0", "1"]:
                response, tokens_used = prompt_to_text(
                    f"{nonchalant} MAKE SURE YOU ONLY RESPOND WITH 0 OR 1!!! Answer 1 if this is a valid task, otherwise 0: {task}"
                )
                test = response.strip()

                if test not in ["0", "1"]:
                    print(f"[ERROR] Invalid boolean for task {i+1}, retrying...")

            if test == "0":
                print(f"[WARNING] Task {i+1} was not approved, retrying...")
                continue

            tasks.append(task)
            task_valid = True

    print(f"[DEEPSEEK] Final total cost: {total_cost:.4f} USD")
    return tasks
