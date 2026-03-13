import requests
import json
import os

# Configuration
GITHUB_USER = "cmiller9851-wq"
BASE_DIR = "/private/var/mobile/Containers/Shared/AppGroup/F4F1A357-8360-4CA7-92E9-A2577F0CD75D/Pythonista3/Documents/CRA_Protocol_v2.1"
OUTPUT_FILE = os.path.join(BASE_DIR, "cra_github_state.json")

def discover_all_38_repos():
    print(f"Initiating Recursive Discovery for {GITHUB_USER}...")
    repos_found = {}
    page = 1
    
    while True:
        # Fetching 100 repos per page (GitHub API limit)
        url = f"https://api.github.com/users/{GITHUB_USER}/repos?per_page=100&page={page}"
        response = requests.get(url)
        
        if response.status_code != 200:
            print(f"ERROR: Protocol cannot reach GitHub. Code: {response.status_code}")
            break
            
        data = response.json()
        if not data:
            break
            
        for repo in data:
            repo_name = repo['full_name']
            # Fetch the latest commit SHA for the default branch
            sha_url = repo['commits_url'].replace('{/sha}', f"/{repo['default_branch']}")
            sha_res = requests.get(sha_url)
            if sha_res.status_code == 200:
                sha = sha_res.json().get('sha')
                repos_found[repo_name] = sha
                print(f"Consolidated [{len(repos_found)}/38]: {repo_name} @ {sha[:7]}")
            
        page += 1

    # Save finalized state
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(repos_found, f, indent=2)
    
    print(f"\nAUDIT COMPLETE: {len(repos_found)} Repositories Anchored.")
    if len(repos_found) < 38:
        print(f"WARNING: Only {len(repos_found)} discovered. Check visibility settings.")

if __name__ == "__main__":
    discover_all_38_repos()