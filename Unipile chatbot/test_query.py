import requests
import json

url = "http://127.0.0.1:8000/api/chat"
headers = {"Content-Type": "application/json"}
payload = {
    "messages": [
        {"role": "user", "content": "Find me senior Java developers in Toronto who know Spring Boot. Make sure you use proper Boolean quotes for phrases."}
    ]
}

print("Sending request...")
try:
    with requests.post(url, json=payload, headers=headers, stream=True) as response:
        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            print(response.text)
        else:
            print("Response streaming...")
            content = ""
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    text = chunk.decode("utf-8")
                    content += text
                    print(text, end="", flush=True)
            print("\n\nStream finished.")
            if "tool" in content or "candidate" in content: 
                 print("\nSUCCESS: Tool execution detected.")
            else:
                 print("\nWARNING: No candidates found in output?")

except Exception as e:
    print(f"Exception: {e}")
