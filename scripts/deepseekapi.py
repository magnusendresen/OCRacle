import os
import time
import threading
import tkinter as tk
from queue import Queue
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

print("[DEEPSEEK] Successfully connected to DeepSeekAPI!\n")


class PopupWindow:
    """Popup GUI that updates dynamically with task content."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Task Output")

        self.text_widget = tk.Text(self.root, wrap=tk.WORD, height=10, width=50)
        self.text_widget.pack(padx=10, pady=10)
        self.text_widget.config(state=tk.DISABLED)

        self.queue = Queue()  # Thread-safe queue for updates
        self.root.after(100, self.process_queue)  # Periodically check queue

    def process_queue(self):
        """Check the queue for updates and update GUI if needed."""
        while not self.queue.empty():
            new_text = self.queue.get()
            self.update_text(new_text)
        self.root.after(100, self.process_queue)  # Re-run after 100ms

    def update_text(self, new_text):
        """Update the popup window text."""
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.delete("1.0", tk.END)
        self.text_widget.insert(tk.END, new_text)
        self.text_widget.config(state=tk.DISABLED)

    def run(self):
        """Run the Tkinter main loop (must be in the main thread)."""
        self.root.mainloop()


def prompt_to_text(prompt, max_retries=3, max_tokens=1000):
    """Sends a request, displays token usage, and calculates cost."""
    global total_cost
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

                # Calculate cost
                request_cost = (input_tokens * usd_per_1m_input_tokens + output_tokens * usd_per_1m_output_tokens) / 1e6
                total_cost += request_cost

                print(f"[DEEPSEEK] Input Tokens: {input_tokens}, Output Tokens: {output_tokens}, Total Tokens: {total_tokens}")
                print(f"[DEEPSEEK] Cost: {request_cost:.4f} USD, Total Cost: {total_cost:.4f} USD\n")

                return result_text
            
            print(f"[ERROR] Invalid response (attempt {attempt+1}/{max_retries}). Retrying...")
        except Exception as e:
            print(f"[ERROR] Request failed: {e} (attempt {attempt+1}/{max_retries})")
            time.sleep(2)
    
    return ""  # Return empty response if all attempts fail


def task_processing_thread(text, popup):
    """Thread function to process tasks and update the popup."""
    global total_cost

    nonchalant = "Do not explain what you are doing, just do it."

    while True:
        print("[DEEPSEEK] Counting the number of tasks in the text:")
        response = prompt_to_text(f"{nonchalant} How many tasks are in this text? Answer with a single number only: {text}")
        if len(response) > 2:
            print("[ERROR] Invalid integer, retrying...")
            continue
        else:
            amount = int(response)
            break
            

    print(f"[DEEPSEEK] Number of tasks found: {amount}\n")

    tasks = []

    task = ""

    for i in range(amount):
        num = i+1

        print(f"[DEEPSEEK] Processing task {num}:")
        while True:
            task = text

            response = prompt_to_text(f"{nonchalant} What is task {num}? Write all text related to the task directly from the raw text, do not solve the task. {task}")
            task = response

            response = prompt_to_text(f"{nonchalant} Remove all text related to Inspera and exam administration, keep only what is necessary for solving the task: {task}")
            task = response

            response = prompt_to_text(f"{nonchalant} Translate the task to Norwegian Bokmål: {task}")
            task = response

            # Valider oppgaven

            while True:
                response = prompt_to_text(f"{nonchalant} MAKE SURE YOU ONLY RESPOND WITH 0 OR 1!!! Answer 1 if this is a valid task, otherwise 0: {task}")
                if response not in ["0", "1"]:
                    print("[ERROR] Invalid response, retrying...")
                    continue
                else:
                    break
            if response == "0":
                print("[WARNING] Task was not approved, retrying...")
                continue
            elif response == "1":
                tasks.append(task)
                break
        tasks.append(task)

    print(f"[DEEPSEEK] Final total cost: {total_cost:.4f} USD")


def main(text):
    """Main function that starts the GUI and task processing."""
    popup = PopupWindow()

    # Start task processing in a separate thread
    threading.Thread(target=task_processing_thread, args=(text, popup), daemon=True).start()

    # Run the Tkinter mainloop in the main thread
    popup.run()