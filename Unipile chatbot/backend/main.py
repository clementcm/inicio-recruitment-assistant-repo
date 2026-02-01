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
from .tools import search_linkedin, resolve_linkedin_location

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
    validate_json: bool = False

# In-memory session store (stateless for now, persists in RAM)
SESSIONS = {}

# System Prompt (Synced with core requirements)
SYSTEM_PROMPT = """You are a Strategic Technical Recruiter with advanced reasoning capabilities. Your goal is tofind, analyze, and rank the best candidates using the Unipile LinkedIn Recruiter  API.

**AVAILABLE DATA FIELDS**:
The `search_linkedin` tool returns exact profile data including:
- `name`, `headline`, `location`, `summary`
- `skills` (list of strings)
- `languages` (list of strings)
- `experience`: List of objects with `title`, `company`, `description`, `location`, `date_range`
- `education`: List of objects with `school`, `degree`, `field`, `description`, `date_range`
- `certifications`: List of objects with `name`, `authority`

**BOOLEAN SEARCH RULES**:
- **Quotes**: EVERY search term MUST be enclosed in double quotes (e.g., `"Java"`, `"Developer"`, `"Senior Java Developer"`).
- **Operators**: Use `AND`, `OR`, and `NOT` in ALL CAPS.
- **Grouping**: Use parentheses `( )` for complex logic.

Process:
1.  **Search & Resolve**: Use tools as needed.
2.  **Multidimensional Analysis**: Evaluate profiles using all **AVAILABLE DATA FIELDS**.
3.  **Rich Display**: Present results in a **Markdown Table**.
    *   **Data Mandate**: You CAN and MUST display any field requested (e.g., **Education**, **Experience**, **Skills**) in table columns. 
    *   **Dynamic Columns**: Add columns for specific user requests (e.g., **Education Breakdown**, **Ranking Rationale**).

**CRITICAL INSTRUCTIONS**:
- **MANDATORY QUOTING**: Always put double quotes around every keyword or phrase in the `keywords` parameter.
- **NEVER** output Python code, `unipile` objects, or any markdown code blocks for tools like `tool_code`.
- **NEVER** say you can't display a field like `education`. The tool provides this data; use it.
- **NEVER** refuse to rank or filter. Use available data for logical inference.
- **NEVER** suggest code or libraries to the user.
- Use **Native Function Calling** only.

**Example Boolean `keywords`**:
- `"Full Stack Developer" AND ("React" OR "Angular")`
- `"Java" AND "Developer" NOT "Intern"`
- `("Project Manager" OR "Program Manager") AND "PMP"`

**Example Full-Data Table**:
| Name | Current Role | Education | Ranking Rationale |
| :--- | :--- | :--- | :--- |
| **John Doe** | Senior Dev | MS Computer Science, Stanford | **High**: Top-tier education and 5 years in client-facing roles. |
"""

# Tool Definition
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_linkedin",
            "description": "Search for candidates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keywords": {"type": "string", "description": "Boolean search keywords"},
                    "location_name": {"type": "string", "description": "City or Region name (e.g. 'Toronto')"}
                },
                "required": ["keywords"]
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
            
        # Build system prompt based on validation setting
        if request.validate_json:
            validation_prompt = SYSTEM_PROMPT + """\n\n**IMPORTANT VALIDATION WORKFLOW**:
When the user asks you to search for candidates, follow this two-step process:

**STEP 1 - Show JSON for Approval:**
Before calling the `search_linkedin` tool, show the user the exact JSON body:
```json
{
  "api": "recruiter",
  "category": "people",
  "keywords": "<the boolean search string you created>",
  "location": [{"id": "<location_id>"}]
}
```
Then ask: "Please type 'approve' or 'yes' to execute this search."

**STEP 2 - Execute After Approval:**
When the user responds with "approve", "yes", or "confirm", IMMEDIATELY call the `search_linkedin` tool with the exact parameters you showed them. Do NOT ask for approval again - just execute the search.

CRITICAL: You MUST actually CALL THE TOOL after receiving approval. The user expects the search to execute."""
        else:
            validation_prompt = SYSTEM_PROMPT
            
        # Update session with new user messages
        SESSIONS[session_id] = [{"role": "system", "content": validation_prompt}] + [m.dict(exclude_none=True) for m in request.messages]
        
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
                if tool_call.function.name == "search_linkedin":
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
