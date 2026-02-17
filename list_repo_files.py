import os
from src.github_client import GitHubClient
from dotenv import load_dotenv

load_dotenv()

client = GitHubClient(os.getenv("GITHUB_TOKEN"))
repo = "vediyappanm/UltraThinking-LLM-Training"

try:
    print(f"Listing root contents of {repo}:")
    contents = client.get_repository_contents(repo, "")
    for item in contents:
        print(f"- {item['path']} ({item['type']})")
        
    print("\nChecking .github/workflows:")
    try:
        wf_contents = client.get_repository_contents(repo, ".github/workflows")
        for wf in wf_contents:
            print(f"- {wf['path']}")
    except Exception as e:
        print(f"Could not list workflows: {e}")
        
except Exception as e:
    print(f"Error: {e}")
