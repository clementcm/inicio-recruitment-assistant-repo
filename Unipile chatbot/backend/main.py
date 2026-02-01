from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import json
import uuid
from dotenv import load_dotenv
from openai import OpenAI

# Import core tools and logic
# Assuming tools.py is in the same directory
from .tools import search_linkedin, resolve_linkedin_location, fetch_unipile_spec

# Load Environment
import pathlib
env_path = pathlib.Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

print(f"DEBUG: Loading .env from {env_path}")
print(f"DEBUG: .env exists? {env_path.exists()}")

API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")

if not API_KEY:
    print("CRITICAL WARNING: GEMINI_API_KEY is NOT set.")
else:
    print(f"DEBUG: GEMINI_API_KEY loaded (len={len(API_KEY)})")

# Use Gemini via OpenAI Compatibility
client = OpenAI(
    api_key=API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve Frontend
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def read_root():
    return FileResponse('frontend/index.html')


# Data Models
class ChatMessage(BaseModel):
    role: str
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    session_id: Optional[str] = None

# In-memory session store (stateless for now, persists in RAM)
SESSIONS = {}

# System Prompt (Synced with core requirements)
# System Prompt - Structured Workflow
SYSTEM_PROMPT = """## ROLE
You are a **World-Class Technical Sourcing Recruiter & Automation Agent**.  
Your mission is to **intelligently interview the client, extract structured hiring requirements, generate highly optimized Boolean search strings for LinkedIn Recruiter, and execute a candidate search using the Unipile LinkedIn Recruiter API**.  
You will then **analyze, rank, and answer questions about the returned candidates**.

You must be precise, deterministic, and API-compliant at every step.

---

## OVERALL OBJECTIVE
1. Understand the Unipile API specification
2. Extract clean, structured hiring requirements from conversation  
3. Generate best-in-class Boolean search logic  
4. Build a **valid Unipile Recruiter API JSON payload**  
5. Execute a **LinkedIn Recruiter People Search**  
6. Analyze and answer questions based on the resulting candidates  

---

## STEP 0 — UNDERSTAND THE API (FIRST TIME ONLY)
- Call the `fetch_unipile_spec` tool to get the API specification
- Study required vs optional fields, field names, types, enums, limits, validation rules
- You MUST conform **exactly** to the spec when constructing JSON
- Do NOT guess or invent fields

---

## STEP 1 — REQUIREMENT EXTRACTION (FROM CHAT)
Extract and normalize the following fields from the conversation:

### Required Fields
1. **Job Title**
   - Official internal title
   - Normalize capitalization (e.g., "java developer" → "Java Developer")
   - Standardize wording (e.g., "dev" → "Developer", "sr" → "Senior")

2. **Must-Have Skills**
   - Non-negotiable hard skills only
   - Technologies, platforms, frameworks, architectures
   - No soft skills unless explicitly stated as mandatory
   - **CRITICAL**: ONLY use skills the user explicitly mentions. DO NOT add inferred skills.

### Optional (Ask if Missing or Unclear)
- Years of experience per skill
- Location constraints (if provided, use `resolve_linkedin_location` to get location ID)
- Industry/domain constraints
- Certifications
- Seniority level

If any **required field is missing or ambiguous**, ask **clear, concise follow-up questions** before proceeding.

---

## STEP 2 — BOOLEAN SEARCH STRING GENERATION
Using the extracted data, generate a **LinkedIn Recruiter-optimized Boolean string**.

### Structure
```
(Title Synonyms) AND (All Must-Have Skills)
```

### Rules
- Use `AND`, `OR`, `NOT` (UPPERCASE)
- Group synonyms with parentheses `()`
- Use quotes `""` for exact phrases
- Expand titles into realistic recruiter synonyms
- **DO NOT add inferred or speculative skills**
- Only include skills explicitly mentioned by the user

### Example
User says: "find senior java developers"
Boolean: `("Senior Java Developer" OR "Java Developer" OR "Java Engineer") AND "Java"`

User says: "find java developers with spring boot"
Boolean: `("Java Developer" OR "Java Engineer") AND "Java" AND "Spring Boot"`

---

## STEP 3 — BUILD UNIPILE RECRUITER SEARCH JSON
Using:
- The validated Boolean string
- The extracted metadata
- The Unipile API spec

Construct a **fully valid JSON body** with the following constraints:

### Mandatory Constraints
- Use **LinkedIn Recruiter API** (`"api": "recruiter"`)
- Search **People only** (`"category": "people"`)
- Use location ID from `resolve_linkedin_location` if location was provided
- **Build the JSON based on the API spec you fetched** - only include fields documented in the spec
- Match data types exactly as specified in the API documentation
- No nulls unless explicitly allowed by the spec

### JSON Construction Guidelines
- Start with the minimum required fields: `api`, `category`, `keywords`
- Add optional fields only if they are in the spec and relevant to the search
- Use the spec to validate field names, types, and allowed values
- Common fields include:
  - `keywords` (string): Your Boolean search string
  - `location` (array of objects): Location filters with `id` and optional `priority`
  - Other fields as documented in the API spec

### Client Checkpoint (MANDATORY)
- Present the JSON to the client in a code block
- Explain what the search will do
- Ask for explicit approval: "Please type 'approve' or 'yes' to execute this search."
- **WAIT for user approval before proceeding to Step 4**

---

## STEP 4 — EXECUTE LINKEDIN SEARCH
After client approval:
- Call the `search_linkedin` tool with the approved JSON payload
- Receive the response as structured JSON
- Preserve the full candidate payload for downstream analysis

---

## STEP 5 — CANDIDATE ANALYSIS & DISPLAY
Using the returned candidate data:

### Display Format
Present results in a **Markdown Table** with:
- **Name** (clickable link to LinkedIn profile using `linkedin_url`)
- **Current Role**
- **Location**
- **Key Skills** (relevant to search)
- **Ranking Rationale** (why they match)

### Example Table
| Name | Current Role | Location | Key Skills | Ranking Rationale |
|:-----|:-------------|:---------|:-----------|:------------------|
| [John Doe](https://linkedin.com/in/johndoe) | Senior Java Developer at Google | Toronto, ON | Java, Spring Boot, AWS | **High**: 8+ years Java, Spring Boot expert, AWS certified |

### Capabilities
- Rank candidates by skill match, title relevance, experience depth, location fit
- Filter candidates by specific skills, keywords, titles
- Answer client questions about candidates
- **ALWAYS include LinkedIn URLs** as clickable links in the Name column

### Rules
- Use **only returned data**
- Do NOT infer unstated skills
- Be transparent when data is missing
- Include all available fields: education, experience, certifications, skills, languages

---

## TOOLS AVAILABLE
1. **`fetch_unipile_spec()`** - Fetches API spec from Unipile docs (call once at start)
2. **`resolve_linkedin_location(location_name: str)`** - Resolves location name to LinkedIn location ID
3. **`search_linkedin(params: dict)`** - Executes LinkedIn Recruiter search with JSON payload

---

## QUALITY BAR
- No hallucinated fields
- No invalid JSON
- No skipped validation steps
- Always ask before executing API calls
- Optimize for recruiter realism and precision
- ONLY use skills explicitly mentioned by the user
"""


# Tool Definition
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_unipile_spec",
            "description": "Fetch the Unipile LinkedIn Recruiter Search API specification from the official documentation. Call this once at the start to understand the API structure, required fields, and validation rules.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_linkedin",
            "description": "Execute a LinkedIn Recruiter People Search with the provided JSON payload. The payload should be constructed based on the Unipile API specification fetched via fetch_unipile_spec. Required fields: api='recruiter', category='people', keywords (Boolean search string). Optional fields as documented in the API spec (e.g., location, skills, experience, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "api": {
                        "type": "string",
                        "description": "API type - must be 'recruiter'",
                        "enum": ["recruiter"]
                    },
                    "category": {
                        "type": "string", 
                        "description": "Search category - must be 'people'",
                        "enum": ["people"]
                    },
                    "keywords": {
                        "type": "string",
                        "description": "Boolean search string with quoted terms and operators (AND, OR, NOT)"
                    },
                    "location": {
                        "type": "array",
                        "description": "Location filters - array of objects with 'id' and optional 'priority'",
                        "items": {
                            "type": "object"
                        }
                    }
                },
                "required": ["api", "category", "keywords"],
                "additionalProperties": True
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_linkedin_location",
            "description": "Find Location ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location_name": {"type": "string"}
                },
                "required": ["location_name"]
            }
        }
    }
]

@app.get("/api/sessions")
async def get_sessions():
    return [{"id": k, "title": v[1]["content"] if len(v) > 1 else "New Chat"} for k, v in SESSIONS.items()]

@app.get("/api/sessions/{session_id}")
async def get_session_history(session_id: str):
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Filter and format messages for frontend display
    formatted_messages = []
    for msg in SESSIONS[session_id][1:]:  # Skip system prompt
        # Skip tool messages
        if isinstance(msg, dict) and msg.get("role") == "tool":
            continue
        
        # Handle OpenAI message objects (from tool calls)
        if hasattr(msg, 'role') and hasattr(msg, 'content'):
            formatted_messages.append({
                "role": msg.role,
                "content": msg.content or ""
            })
        # Handle dict messages
        elif isinstance(msg, dict):
            formatted_messages.append({
                "role": msg.get("role", "assistant"),
                "content": msg.get("content", "")
            })
    
    return formatted_messages

@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        session_id = request.session_id or str(uuid.uuid4())
        
        # Load or init session
        if session_id not in SESSIONS:
            SESSIONS[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
            
        # Update session with new user messages
        SESSIONS[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}] + [m.dict(exclude_none=True) for m in request.messages]
        
        full_history = SESSIONS[session_id]
        print(f"DEBUG: Session {session_id} - Sending {len(full_history)} messages to Gemini Turn 1...")

        # 1. Call OpenAI (Initial)
        # We don't stream the first call because we need to check for tools first.
        # (Technically we could stream tools, but it's complex for this demo)
        response = client.chat.completions.create(
            model="gemini-3-flash-preview", 
            messages=full_history,
            tools=TOOLS,
            tool_choice="auto"
        )
        print(f"DEBUG: Turn 1 Response: {response}")
        
        message = response.choices[0].message
        
        # 2. Check for tool calls
        if message.tool_calls:
            print(f"DEBUG: Native Tool Calls detected: {[tc.function.name for tc in message.tool_calls]}")
            
            # Execute tools directly
            tool_outputs = []
            for tool_call in message.tool_calls:
                if tool_call.function.name == "fetch_unipile_spec":
                    result = fetch_unipile_spec()
                    tool_outputs.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result)
                    })
                elif tool_call.function.name == "search_linkedin":
                    args = json.loads(tool_call.function.arguments)
                    # Use resolve_linkedin_location internally if needed, or just pass the string
                    # But the search_linkedin wrapper expects resolve_linkedin_location internally
                    result = search_linkedin(args)
                    tool_outputs.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result)
                    })
                elif tool_call.function.name == "resolve_linkedin_location":
                    args = json.loads(tool_call.function.arguments)
                    result = resolve_linkedin_location(args["location_name"])
                    tool_outputs.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result)
                    })
            
            # Append Tool Outputs
            full_history.append(message)
            full_history.extend(tool_outputs)
            print(f"DEBUG: History updated with {len(tool_outputs)} tool results. Starting secondary stream.")
            
            # 3. Stream Final Response
            # Now we stream the final answer from Gemini
            async def generate():
                print("DEBUG: Starting stream generation...")
                full_assistant_content = ""
                try:
                    stream = client.chat.completions.create(
                        model="gemini-3-flash-preview",
                        messages=full_history,
                        stream=True
                    )
                    print("DEBUG: Stream created. Iterating...")
                    for chunk in stream:
                        content = chunk.choices[0].delta.content
                        if content:
                            full_assistant_content += content
                            yield content
                    
                    # Persist the final response
                    full_history.append({"role": "assistant", "content": full_assistant_content})
                    print("DEBUG: Stream finished and history updated.")
                except Exception as e:
                    print(f"DEBUG: Stream ERROR: {e}")
                    yield f"\n[SYSTEM ERROR]: {str(e)}"
                        
            return StreamingResponse(generate(), media_type="text/plain")
            
        else:
            # Fallback: Check for "hallucinated" JSON tool calls if native failed
            import re
            content = message.content or ""
            print(f"DEBUG: No native tool calls. Content length: {len(content)}")
            
            tool_detected = False
            fname = None
            fargs = {}
            
            # Use a more aggressive search: find anything between { and }
            # and try to find tool-like keywords inside
            potential_json_blocks = re.findall(r"({[\s\S]*?})", content)
            
            for block_str in potential_json_blocks:
                try:
                    # Basic cleanup for common hallucination issues (single quotes, trailing commas)
                    clean_str = block_str.replace("'", '"')
                    # Remove trailing commas before closing braces/brackets
                    clean_str = re.sub(r",\s*([}\]])", r"\1", clean_str)
                    
                    data = json.loads(clean_str)
                    print(f"DEBUG: Inspected block keys: {list(data.keys())}")
                    
                    if "tool_name" in data:
                        fname = data["tool_name"]
                        fargs = data.get("parameters", data) # Use data as args if parameters missing
                    elif "keywords" in data or "location_name" in data:
                        fname = "resolve_linkedin_location" if "location_name" in data else "search_linkedin"
                        fargs = data
                        
                    if fname in ["search_linkedin", "resolve_linkedin_location"]:
                        print(f"DEBUG: Intercepted Tool: {fname}")
                        break
                except Exception as e:
                    print(f"DEBUG: Skipping block parse error: {e}")
                    continue

            # Python-style call fallback (default_api, unipile, or direct function.search)
            if not fname:
                hal_m = re.search(r"(?:default_api|unipile|search_linkedin|resolve_linkedin_location)\.(search_linkedin|resolve_linkedin_location|search|resolve)\((.*?)\)", content, re.DOTALL)
                if hal_m:
                    raw_name = hal_m.group(1)
                    # Normalize name
                    if raw_name in ["search", "search_linkedin"]: fname = "search_linkedin"
                    elif raw_name in ["resolve", "resolve_linkedin_location"]: fname = "resolve_linkedin_location"
                    
                    a = hal_m.group(2)
                    fargs = {}
                    # Clean the arguments string (keywords='...' or keywords="...")
                    k = re.search(r'keywords\s*=\s*["\'](.*?)["\']', a)
                    if k: fargs["keywords"] = k.group(1)
                    l = re.search(r'location_name\s*=\s*["\'](.*?)["\']', a)
                    if l: fargs["location_name"] = l.group(1)
                    loc = re.search(r'location\s*=\s*["\'](.*?)["\']', a) # For simpler location='Toronto'
                    if loc: fargs["location_name"] = loc.group(1)
                    g = re.search(r'geo_urns\s*=\s*\[["\'](.*?)["\']\]', a)
                    if g: fargs["location"] = [{"id": g.group(1), "priority": "MUST_HAVE"}]
                    lim = re.search(r'limit\s*=\s*(\d+)', a)
                    if lim: fargs["limit"] = int(lim.group(1))

            # Final standalone variable fallback (e.g. keywords = '...')
            if not fname:
                k = re.search(r'keywords\s*=\s*["\'](.*?)["\']', content)
                if k:
                    fargs["keywords"] = k.group(1)
                    fname = "search_linkedin"
                    # Also look for location in the same vicinity
                    l = re.search(r'location\s*=\s*["\'](.*?)["\']', content)
                    if l: fargs["location_name"] = l.group(1)

            if fname in ["search_linkedin", "resolve_linkedin_location"]:
                print(f"DEBUG: Proceeding with manual tool execution [{fname}]")
                tool_detected = True
                try:
                    # Clean fargs of metadata like 'tool_name' if we used flat data
                    call_args = {k: v for k, v in fargs.items() if k not in ["tool_name", "parameters"]}
                    if fname == "search_linkedin":
                        result = search_linkedin(call_args)
                    else:
                        result = resolve_linkedin_location(call_args.get("location_name", ""))
                    print(f"DEBUG: Tool result size: {len(str(result))}")
                except Exception as e:
                    print(f"DEBUG: Tool EXCEPTION: {e}")
                    result = {"error": str(e)}
                
                full_history.append(message)
                full_history.append({"role": "user", "content": f"SYSTEM: Manually intercepted tool {fname}. RESULT: {json.dumps(result)}"})
                        
                async def generate_manual():
                    print("DEBUG: Starting Turn 2 stream (manual)...")
                    full_assistant_content = ""
                    try:
                        stream = client.chat.completions.create(model="gemini-3-flash-preview", messages=full_history, stream=True)
                        for chunk in stream:
                            c = chunk.choices[0].delta.content
                            if c:
                                full_assistant_content += c
                                yield c
                        
                        full_history.append({"role": "assistant", "content": full_assistant_content})
                        print("DEBUG: Turn 2 stream finished and history updated.")
                    except Exception as e:
                        print(f"DEBUG: Turn 2 stream ERROR: {e}")
                        yield f"\n[SYSTEM ERROR]: {str(e)}"
                return StreamingResponse(generate_manual(), media_type="text/plain")

            print("DEBUG: No tool detected. Returning raw text.")
            full_history.append({"role": "assistant", "content": content})
            return StreamingResponse(iter([content]), media_type="text/plain")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"CRITICAL ERROR: {e}")
        return StreamingResponse(iter([f"Error: {str(e)}"]), media_type="text/plain")
