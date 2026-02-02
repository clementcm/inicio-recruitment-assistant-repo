from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import json
import uuid
from dotenv import load_dotenv
from openai import AsyncOpenAI
import asyncio

# Database & Auth Imports
from sqlalchemy.orm import Session
from .database import engine, Base, get_db
from . import models, auth
from fastapi.security import OAuth2PasswordRequestForm

# Create Tables
Base.metadata.create_all(bind=engine)

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

# Use Gemini via OpenAI Compatibility (Async)
client = AsyncOpenAI(
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

# Startup Event: Seed Admin User
@app.on_event("startup")
def startup_seed_admin():
    from .database import SessionLocal
    db = SessionLocal()
    try:
        admin_email = "admin@example.com"
        existing_admin = db.query(models.User).filter(models.User.email == admin_email).first()
        if not existing_admin:
            print(f"DEBUG: Seeding default admin user: {admin_email}")
            hashed_pwd = auth.get_password_hash("admin123")
            admin_user = models.User(
                email=admin_email, 
                hashed_password=hashed_pwd, 
                is_admin=True, 
                is_approved=True,
                verify_json=False
            )
            db.add(admin_user)
            db.commit()
            print("DEBUG: Default admin user created.")
        else:
            print("DEBUG: Admin user already exists.")
    except Exception as e:
        print(f"WARNING: Failed to seed admin user: {e}")
    finally:
        db.close()

# Add Login Page Route (to be created)
@app.get("/login")
async def login_page():
    return FileResponse('frontend/login.html')

@app.get("/admin")
async def admin_page():
    return FileResponse('frontend/admin.html')

# Auth Endpoints
@app.post("/api/auth/signup")
async def signup(email: str, password: str, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pwd = auth.get_password_hash(password)
    # Default: Not Admin, Not Approved
    new_user = models.User(email=email, hashed_password=hashed_pwd, is_admin=False, is_approved=False)
    db.add(new_user)
    db.commit()
    return {"message": "User created successfully"}

@app.post("/api/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_approved:
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account pending approval. Please contact administrator.",
        )
    
    access_token = auth.create_access_token(data={"sub": user.email})
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "is_admin": user.is_admin
    }


# Data Models
class ChatMessage(BaseModel):
    role: str
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    session_id: Optional[str] = None
    verify_json: bool = True

class UserBase(BaseModel):
    email: str

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    password: Optional[str] = None
    is_admin: Optional[bool] = None
    verify_json: Optional[bool] = None

class UserProfileUpdate(BaseModel):
    password: Optional[str] = None
    verify_json: Optional[bool] = None

class UserResponse(UserBase):
    id: int
    is_active: bool
    is_admin: bool
    is_approved: bool
    verify_json: bool

    class Config:
        from_attributes = True

# Admin Dependency
async def get_current_admin_user(current_user: models.User = Depends(auth.get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user

# Admin Endpoints
@app.get("/api/admin/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db), 
    admin: models.User = Depends(get_current_admin_user)
):
    users = db.query(models.User).offset(skip).limit(limit).all()
    return users

@app.post("/api/admin/users", response_model=UserResponse)
async def create_user_admin(
    user: UserCreate, 
    db: Session = Depends(get_db), 
    admin: models.User = Depends(get_current_admin_user)
):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pwd = auth.get_password_hash(user.password)
    # Admin created users are approved by default, but not admins (unless manually promoted later)
    new_user = models.User(email=user.email, hashed_password=hashed_pwd, is_approved=True, is_admin=False)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.put("/api/admin/users/{user_id}/approve")
async def approve_user(
    user_id: int, 
    db: Session = Depends(get_db), 
    admin: models.User = Depends(get_current_admin_user)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_approved = True
    db.commit()
    return {"message": f"User {user.email} approved"}

@app.put("/api/admin/users/{user_id}")
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin_user)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_update.is_admin is not None:
        user.is_admin = user_update.is_admin
        
    if user_update.password:
        user.hashed_password = auth.get_password_hash(user_update.password)

    db.commit()
    return {"message": f"User {user.email} updated"}

@app.delete("/api/admin/users/{user_id}")
async def delete_user(
    user_id: int, 
    db: Session = Depends(get_db), 
    admin: models.User = Depends(get_current_admin_user)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}

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
- **REMEMBER THIS EXACT JSON** - you will need to pass it to `search_linkedin` when they approve
- **WAIT for user approval before proceeding to Step 4**
- **DO NOT call any tools while waiting** - just wait for their response

---

## STEP 4 — EXECUTE LINKEDIN SEARCH
**CRITICAL: When the user responds with "approve", "yes", "confirm", "ok", or similar approval:**
1. **IMMEDIATELY call `search_linkedin`** with the exact JSON payload you showed them
2. **DO NOT** call `fetch_unipile_spec` again
3. **DO NOT** ask for more clarification
4. **DO NOT** regenerate the JSON
5. **Just execute the search** with the approved parameters

After calling `search_linkedin`:
- Receive the response as structured JSON
- Preserve the full candidate payload for Step 5 analysis

---

## STEP 5 — CANDIDATE ANALYSIS & DISPLAY
Using the returned candidate data:

### Display Format (STRICT)
**Structure your response using ONLY H3 (###) headers for sections.**

1. **### Candidates Found**
   - Present results in a **Markdown Table** with:
     - **Name** (clickable link to LinkedIn profile using `linkedin_url`)
     - **Current Role**
     - **Location**
     - **Key Skills**
     - **Ranking Rationale**

### Example Table
| Name | Current Role | Location | Key Skills | Ranking Rationale |
|:-----|:-------------|:---------|:-----------|:------------------|
| [John Doe](https://linkedin.com/in/johndoe) | Senior Java Developer | Toronto, ON | Java, AWS | **High**: 8+ years exp |

### Search Summary & Insights
**Mandatory: Provide a concise summary of the ACTUAL candidates returned.**
- **Candidate Count**: State exactly how many relevant candidates were found.
- **Top Titles**: List the most common job titles found in the results (e.g., "Most are Senior Java Engineers...").
- **Top Skills**: List the most frequent skills appearing in these specific profiles.
- **Location Distribution**: Briefly mention where they are located.
- **NO GENERIC FILLER**: Do NOT say "This list is biased..." or "Would you like me to filter...". Just summarize the data you have.

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

def serialize_history(history: List[Any]) -> List[Dict[str, Any]]:
    """Converts OpenAI message objects to serializable dicts."""
    serialized = []
    for msg in history:
        if hasattr(msg, 'dict') and callable(msg.dict):
            serialized.append(msg.dict(exclude_none=True))
        elif isinstance(msg, dict):
            serialized.append(msg)
        else:
            # Fallback for unexpected types
            serialized.append(str(msg))
    return serialized

@app.get("/api/users/me", response_model=UserResponse)
async def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user

@app.put("/api/users/me", response_model=UserResponse)
async def update_users_me(
    user_update: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    if user_update.password:
        current_user.hashed_password = auth.get_password_hash(user_update.password)
    if user_update.verify_json is not None:
        current_user.verify_json = user_update.verify_json
    
    db.commit()
    db.refresh(current_user)
    return current_user

@app.get("/api/sessions")
async def get_sessions(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    db_sessions = db.query(models.ChatSession).filter(models.ChatSession.user_id == current_user.id).all()
    results = []
    for s in db_sessions:
        history = json.loads(s.history)
        title = "New Chat"
        if len(history) > 1:
            title = history[1].get("content", "New Chat")[:50]
        results.append({"id": s.id, "title": title})
    return results

@app.get("/api/sessions/{session_id}")
async def get_session_history(
    session_id: str, 
    current_user: models.User = Depends(auth.get_current_user), 
    db: Session = Depends(get_db)
):
    db_session = db.query(models.ChatSession).filter(
        models.ChatSession.id == session_id,
        models.ChatSession.user_id == current_user.id
    ).first()
    
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    history = json.loads(db_session.history)
    # Filter for frontend (hide system prompt and keep it simple)
    formatted_messages = []
    for msg in history[1:]:
        if msg.get("role") == "tool": continue
        formatted_messages.append({
            "role": msg.get("role"),
            "content": msg.get("content") or ""
        })
    return formatted_messages

@app.post("/api/chat")
async def chat(request: ChatRequest, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    try:
        session_id = request.session_id or str(uuid.uuid4())
        
        # Prepare System Prompt based on verification setting
        current_system_prompt = SYSTEM_PROMPT
        if not current_user.verify_json:
            print("DEBUG: Verification disabled. Modifying system prompt.")
            checkpoint_block = """### Client Checkpoint (MANDATORY)
- Present the JSON to the client in a code block
- Explain what the search will do
- Ask for explicit approval: "Please type 'approve' or 'yes' to execute this search."
- **REMEMBER THIS EXACT JSON** - you will need to pass it to `search_linkedin` when they approve
- **WAIT for user approval before proceeding to Step 4**
- **DO NOT call any tools while waiting** - just wait for their response"""

            checkpoint_replacement = """### Client Checkpoint (SKIPPED)
- **DO NOT ask for approval.**
- **IMMEDIATELY** call the `search_linkedin` tool with the JSON you just built.
- Proceed to Step 5 (Analysis) immediately after the tool call."""
            
            current_system_prompt = current_system_prompt.replace(checkpoint_block, checkpoint_replacement)
            
            step4_block = """## STEP 4 — EXECUTE LINKEDIN SEARCH
**CRITICAL: When the user responds with "approve", "yes", "confirm", "ok", or similar approval:**
1. **IMMEDIATELY call `search_linkedin`** with the exact JSON payload you showed them"""

            step4_replacement = """## STEP 4 — EXECUTE LINKEDIN SEARCH
**CRITICAL: EXECUTE IMMEDIATELY**
1. **Call `search_linkedin`** with the JSON payload from Step 3"""
            
            if checkpoint_block in current_system_prompt:
                print("DEBUG: Checkpoint block FOUND and replacing...")
            else:
                print("DEBUG: Checkpoint block NOT FOUND - Replacement failed!")

            current_system_prompt = current_system_prompt.replace(checkpoint_block, checkpoint_replacement)
            
            if step4_block in current_system_prompt:
                 print("DEBUG: Step 4 block FOUND and replacing...")
            else:
                 print("DEBUG: Step 4 block NOT FOUND - Replacement failed!")

            current_system_prompt = current_system_prompt.replace(step4_block, step4_replacement)

        # Load or init session from DB
        db_session = db.query(models.ChatSession).filter(
            models.ChatSession.id == session_id,
            models.ChatSession.user_id == current_user.id
        ).first()

        if not db_session:
            current_history = [{"role": "system", "content": current_system_prompt}]
            db_session = models.ChatSession(
                id=session_id, 
                user_id=current_user.id, 
                history=json.dumps(current_history)
            )
            db.add(db_session)
            db.commit()
        else:
            current_history = json.loads(db_session.history)
            # Update system prompt if it changed (e.g. toggle verification)
            if current_history and current_history[0]["role"] == "system":
                current_history[0]["content"] = current_system_prompt
        
        # Merge Strategy: Append only new messages from the client
        incoming_messages = [m.dict(exclude_none=True) for m in request.messages]
        
        if incoming_messages:
            last_incoming = incoming_messages[-1]
            # Simple check to avoid duplicates in DB
            if not any(msg.get("role") == last_incoming["role"] and msg.get("content") == last_incoming["content"] for msg in current_history[-2:]):
                current_history.append(last_incoming)

        full_history = current_history
        print(f"DEBUG: User {current_user.email} - Session {session_id} - Sending {len(full_history)} messages to Gemini...")

        # 1. Call Async OpenAI (Initial)
        # Loop to handle chained tool calls (e.g., fetch_spec -> search_linkedin)
        while True:
            response = await client.chat.completions.create(
                model="gemini-3-flash-preview", 
                messages=full_history,
                tools=TOOLS,
                tool_choice="auto"
            )
            
            message = response.choices[0].message
            
            # If no tools, break and go to streaming text
            if not message.tool_calls:
                break
            
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
            
            # Append Assistant Message (Tool Request)
            full_history.append(message)
            # Append Tool Outputs
            full_history.extend(tool_outputs)
            
        async def generate():
            # If we exited the loop, 'message' contains the text response
            content = message.content or ""
            # Yield in smaller chunks to simulate streaming for better frontend UX
            chunk_size = 50
            for i in range(0, len(content), chunk_size):
                 yield content[i:i+chunk_size]
                 # Small yield to let event loop breathe
                 await asyncio.sleep(0.005)
                
            # Persist the final response
            full_history.append({"role": "assistant", "content": content})
            
            # Save updated history TO DB
            db_session.history = json.dumps(serialize_history(full_history))
            db.add(db_session)
            db.commit()
            print("DEBUG: [GENERATE] History persisted to DB.")
                    
        return StreamingResponse(
            generate(), 
            media_type="text/plain",
            headers={
                "X-Accel-Buffering": "no",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )


    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"CRITICAL ERROR: {e}")
        return StreamingResponse(iter([f"Error: {str(e)}"]), media_type="text/plain")
