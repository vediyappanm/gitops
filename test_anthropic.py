import os
import requests
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("ANTHROPIC_API_KEY")
print(f"Key: {key[:15]}...{key[-5:]}")
print(f"Length: {len(key)}")

url = "https://api.anthropic.com/v1/messages"
headers = {
    "x-api-key": key,
    "anthropic-version": "2023-06-01",
    "Content-Type": "application/json"
}
payload = {
    "model": "claude-3-5-sonnet-20240620",
    "messages": [{"role": "user", "content": "Hi"}],
    "max_tokens": 10
}

response = requests.post(url, headers=headers, json=payload)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
