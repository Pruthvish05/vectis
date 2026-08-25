import json
import threading
import tkinter as tk
import urllib.request


def send_request():
  prompt = prompt_box.get("1.0", tk.END).strip()
  if not prompt:
    return

  send_btn.config(state=tk.DISABLED, text="Processing...")
  output_box.delete("1.0", tk.END)
  output_box.insert(tk.END, "Sending request through Vectis proxy...\n")

  def worker():
    url = "http://localhost:8080/chat/completions"
    payload = {
        "model": "llama3.2",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )

    try:
      with urllib.request.urlopen(req) as response:
        res_data = response.read().decode("utf-8")
        try:
          res_json = json.loads(res_data)
          content = res_json["choices"][0]["message"]["content"]
        except Exception:
          content = res_data

        root.after(0, update_output, content)
    except Exception as e:
      root.after(0, update_output, f"Error connecting to proxy: {str(e)}")

  threading.Thread(target=worker, daemon=True).start()


def update_output(text):
  output_box.delete("1.0", tk.END)
  output_box.insert(tk.END, text)
  send_btn.config(state=tk.NORMAL, text="Send Prompt")


# --- GUI Layout ---
root = tk.Tk()
root.title("Vectis Firewall Prototype")
root.geometry("520x450")

# Input Section
tk.Label(
    root, text="Input Prompt (Contains PII):", font=("Arial", 10, "bold")
).pack(anchor="w", padx=10, pady=(10, 2))
prompt_box = tk.Text(root, height=5)
prompt_box.pack(fill="x", padx=10, pady=2)
prompt_box.insert(
    "1.0",
    "Please send a formal notice to john.doe@acme-corp.org and call"
    " 555-123-4567 about their invoice.",
)

# Button
send_btn = tk.Button(
    root, text="Send Prompt", command=send_request, bg="#e1e1e1"
)
send_btn.pack(fill="x", padx=10, pady=10)

# Output Section
tk.Label(
    root, text="Unmasked Output from Vectis:", font=("Arial", 10, "bold")
).pack(anchor="w", padx=10, pady=(5, 2))
output_box = tk.Text(root, height=12)
output_box.pack(fill="both", expand=True, padx=10, pady=(2, 10))

root.mainloop()