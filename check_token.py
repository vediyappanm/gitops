import os
import requests
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("GITHUB_TOKEN")

if not token:
    print("GITHUB_TOKEN not found in .env")
else:
    headers = {"Authorization": f"token {token}"}
    response = requests.get("https://api.github.com/user", headers=headers)
    if response.status_code == 200:
        scopes = response.headers.get("X-OAuth-Scopes", "Unknown")
        print(f"Token is valid. Scopes: {scopes}")
        if "repo" not in scopes and "public_repo" not in scopes:
            print("WARNING: Token might lack 'repo' scope required for PR creation.")
    else:
        print(f"Failed to verify token: {response.status_code} - {response.text}")
