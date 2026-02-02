import os
import requests
import json
from typing import Dict, Any, Optional

def fetch_unipile_spec() -> Dict[str, Any]:
    """
    Fetches the Unipile LinkedIn Recruiter Search API specification.
    Returns the markdown documentation from Unipile's developer docs.
    """
    spec_url = "https://developer.unipile.com/reference/linkedincontroller_search.md"
    
    try:
        response = requests.get(spec_url, timeout=10)
        response.raise_for_status()
        return {
            "success": True,
            "spec": response.text,
            "message": "API specification fetched successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to fetch API spec: {str(e)}",
            "message": "Using cached knowledge of Unipile API structure"
        }


def resolve_linkedin_location(
    location_name: str,
    account_id: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resolves a location name (e.g. "Paris") to a LinkedIn Location ID/GeoUrn.
    """
    account_id = account_id or os.getenv("LINKEDIN_ACCOUNT_ID")
    base_url = base_url or os.getenv("UNIPILE_DSN", "https://api1.unipile.com:13200")
    api_key = api_key or os.getenv("UNIPILE_API_KEY")

    # Handle custom aliases (e.g. GTA -> Greater Toronto Area)
    if location_name and "GTA" in location_name.upper():
         location_name = "Greater Toronto Area"

    if not all([account_id, base_url, api_key]):
        return {"error": "Missing configuration."}

    url = f"{base_url}/api/v1/linkedin/search/parameters"
    
    params = {
        "account_id": account_id,
        "api": "linkedin", # Use standard API context for parameter search
        "type": "LOCATION",
        "keywords": location_name
    }

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Return top 3 matches
        # API returns { items: [...] }
        items = data.get("items", [])
        return {"matches": items[:3]}

    except Exception as e:
        return {"error": f"Location resolution failed: {str(e)}"}

def search_linkedin(
    params: Dict[str, Any], 
    account_id: Optional[str] = None, 
    base_url: Optional[str] = None, 
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes a LinkedIn search via Unipile API.
    
    Args:
        params: The search parameters dictionary (constructed by the LLM).
        account_id: The LinkedIn account ID to use (overrides env var).
        base_url: The Unipile DSN (overrides env var).
        api_key: The Unipile API Key (overrides env var).
        
    Returns:
        JSON response from Unipile or error dictionary.
    """
    # Load defaults from env if not provided
    account_id = account_id or os.getenv("LINKEDIN_ACCOUNT_ID")
    base_url = base_url or os.getenv("UNIPILE_DSN", "https://api1.unipile.com:13200")
    api_key = api_key or os.getenv("UNIPILE_API_KEY")

    if not all([account_id, base_url, api_key]):
        return {"error": "Missing configuration. Please set LINKEDIN_ACCOUNT_ID, UNIPILE_DSN, and UNIPILE_API_KEY in .env"}

    # Construct URL
    url = f"{base_url}/api/v1/linkedin/search"
    
    # Query Parameters
    query_params = {
        "account_id": account_id,
        "limit": min(params.get("limit", 20), 50),  # Allow up to 50, default 20
    }
    
    # Clean params to remove limit from body if it was put there inadvertently
    body_params = params.copy()
    if "limit" in body_params:
        del body_params["limit"]
        
    # Enforce 'recruiter' API and 'people' category as requested by user
    body_params["api"] = "recruiter"
    body_params["category"] = "people"

    # Default Location: Toronto, Ontario (ID 100025096)
    # If 'location' is not in params, or is empty, we add it.
    if "location" not in body_params or not body_params["location"]:
        body_params["location"] = [{
            "id": "100025096", # Toronto, Ontario
            "priority": "MUST_HAVE"
        }]

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, params=query_params, json=body_params)
        response.raise_for_status()
        data = response.json()
        
        # Optimize Token Usage: Filter to essential fields only
        # Unipile Recruiter API structure usually has 'items' or 'matches'
        candidates = []
        raw_items = data.get("items", data.get("matches", []))
        
        if not isinstance(raw_items, list):
             # If struct is unknown, fallback to specific keys to avoid dumping everything
             return {"info": "Search completed", "count": data.get("count", 0), "message": "Raw data too large to display debug."}

        candidates = []
        for item in raw_items:
            # Extract basic info
            profile = item.get("profile", item)
            
            # Helper to clean lists of dicts
            def clean_list(lst, keys):
                if not isinstance(lst, list): return []
                cleaned = []
                for x in lst:
                    new_item = {k: x.get(k) for k in keys if x.get(k)}
                    # Flatten dates if possible
                    if "date" in x:
                         start = x["date"].get("start", {})
                         end = x["date"].get("end", {})
                         new_item["date_range"] = f"{start.get('year', '')}-{end.get('year', 'Present')}"
                    cleaned.append(new_item)
                return cleaned

            candidate = {
                "name": profile.get("name", "Unknown"),
                "headline": profile.get("headline", ""),
                "location": profile.get("location", ""),
                "public_identifier": profile.get("public_identifier", ""),
                "summary": profile.get("summary", ""),
                "skills": [s.get("name") for s in item.get("skills", [])] if isinstance(item.get("skills"), list) else [],
                "languages": [l.get("name") for l in profile.get("languages", [])] if isinstance(profile.get("languages"), list) else [],
                
                # Detailed Experience (Company, Role/Title, Description, Location)
                "experience": clean_list(item.get("work_experience", []), ["role", "company", "description", "location"]),
                
                # Detailed Education
                "education": clean_list(item.get("education", []), ["school", "degree", "field_of_study", "description"]),
                
                # Certifications
                "certifications": clean_list(item.get("certifications", []), ["name", "authority"])
            }
            
            # Infer current role for quick display (using 'role' key from Unipile)
            if candidate["experience"]:
                 curr = candidate["experience"][0]
                 candidate["current_role"] = f"{curr.get('role')} at {curr.get('company')}"
            else:
                 candidate["current_role"] = "Unknown"

            candidates.append(candidate)
            
        return {"count": len(candidates), "candidates": candidates}

    except requests.exceptions.HTTPError as e:
        try:
             err_data = response.json()
             return {"error": f"HTTP Error {response.status_code}", "details": err_data}
        except:
             return {"error": f"HTTP Error {response.status_code}", "details": response.text}
    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}
