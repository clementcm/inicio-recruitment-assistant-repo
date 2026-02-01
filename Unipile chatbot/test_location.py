import os
import requests
from dotenv import load_dotenv
import pathlib
import json

env_path = pathlib.Path(".env")
load_dotenv(dotenv_path=env_path)

def resolve_linkedin_location(location_name: str):
    account_id = os.getenv("LINKEDIN_ACCOUNT_ID")
    base_url = os.getenv("UNIPILE_DSN", "https://api1.unipile.com:13200")
    api_key = os.getenv("UNIPILE_API_KEY")

    print(f"Testing location: {location_name}")
    print(f"Account: {account_id}")

    url = f"{base_url}/api/v1/linkedin/search_parameters"
    
    params = {
        "account_id": account_id,
        "api": "recruiter", 
        "type": "locations",
        "q": location_name
    }

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }

    # Verified Endpoint: /api/v1/linkedin/search/parameters
    print("\n--- Testing search/parameters (Verified) ---")
    url_found = f"{base_url}/api/v1/linkedin/search/parameters"
    
    # Try type=LOCATION and keywords
    params_found = {
        "account_id": account_id,
        "type": "LOCATION", # Try uppercase as per search result, or 'locations'
        "keywords": location_name,
        "api": "linkedin" # Usually standard API works for generic params
    }

    try:
        response = requests.get(url_found, headers=headers, params=params_found)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
             print("SUCCESS!")
             print(json.dumps(response.json(), indent=2))
        else:
             print(response.text)
    except Exception as e:
        print(e)
        
    print("\n--- Testing search/parameters (type=locations lowercase) ---")
    params_found["type"] = "locations"
    try:
        response = requests.get(url_found, headers=headers, params=params_found)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
             print(json.dumps(response.json(), indent=2))
        else:
             print(response.text)
    except Exception as e:
        print(e)

if __name__ == "__main__":
    resolve_linkedin_location("Greater Toronto Area")
    resolve_linkedin_location("GTA")
