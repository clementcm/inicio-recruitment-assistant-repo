import os
import json
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.markdown import Markdown

from tools import search_linkedin

# Setup
load_dotenv()
console = Console()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    console.print("[red]Error: OPENAI_API_KEY not found in .env[/red]")
    exit(1)

client = OpenAI(api_key=API_KEY)

# Tool Definition for OpenAI
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_linkedin",
            "description": "Search for candidates on LinkedIn using the Unipile Recruiter API. Use this tool when you have gathered sufficient criteria (e.g., role, location, skills) from the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of results to return (default 10, max 100).",
                        "default": 10
                    },
                    "keywords": {
                        "type": "string",
                        "description": "Boolean search string (e.g. 'developer AND python NOT java')."
                    },
                     "location": {
                        "type": "array",
                        "items": {
                             "type": "object",
                             "properties": {
                                 "id": {"type": "string", "description": "Location ID if known (use search param list to find), acts as ID filter."},
                                 "priority": {"type": "string", "enum": ["MUST_HAVE", "CAN_HAVE"], "default": "MUST_HAVE"}
                             }
                        },
                        "description": "Location filter. Note: This API often requires ID. If unsure, prefer using keywords or ask user for precise location, or attempt to infer ID if known mapping exists. For this demo, keywords in 'keywords' field is safer for general location."
                    },
                    "role": {
                        "type": "array",
                        "items": {
                             "type": "object", 
                             "properties": {
                                 "keywords": {"type": "string", "description": "Job title keywords (e.g. 'Software Engineer')"},
                                 "scope": {"type": "string", "enum": ["CURRENT", "PAST", "CURRENT_OR_PAST"], "default": "CURRENT"}
                             }
                        },
                        "description": "Job title filters."
                    },
                     "skills": {
                        "type": "array",
                        "items": {
                             "type": "object", 
                             "properties": {
                                 "keywords": {"type": "string", "description": "Skill keywords (e.g. 'Python', 'React')"},
                                 "priority": {"type": "string", "enum": ["MUST_HAVE", "CAN_HAVE"], "default": "MUST_HAVE"}
                             }
                        },
                        "description": "Skills filters."
                    }
                },
                "required": []
            }
        }
    }
]

SYSTEM_PROMPT = """You are an expert technical recruiter assistant. Your goal is to help the user find the best candidates using the Unipile LinkedIn Recruiter API.

**IMPORTANT CONSTRAINT**: You are ONLY allowed to search for **PEOPLE** using the **RECRUITER** API. Do not attempt company searches or use other API types.

Process:
1.  **Gather Requirements**: Ask the user clarifying questions to build a strong search query. You need at least a specific role (e.g., "Frontend Developer") and ideally a location, skills, or experience level.
2.  **Construct Query**: When you have enough information, call the `search_linkedin` tool. 
    *   Construct boolean strings for `keywords` if complex logic is needed.
    *   Use `role` > `keywords` for job titles.
    *   Use `skills` > `keywords` for specific tech stacks.
3.  **Analyze Results**: The tool will return a list of candidates.
    *   Present the top 5 candidates to the user with a brief summary of why they fit.
    *   Ask if the user wants to see more or refine the search.
4.  **Refine**: If the user wants changes (e.g., "Only senior ones"), call the tool again with updated parameters (e.g., adding `seniority` or adjusting keywords).

Memory:
You have access to the conversation history. Use it to refine subsequent searches.
"""

def chat_loop():
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    console.print("[yellow]Unipile Recruiter Bot Initialized. How can I help you find candidates today?[/yellow]")

    while True:
        try:
            user_input = console.input("[green]You > [/green]")
            if user_input.lower() in ["exit", "quit"]:
                break

            messages.append({"role": "user", "content": user_input})

            # First API Call (Determine intent/tool usage)
            response = client.chat.completions.create(
                model="gpt-4o", # Or gpt-3.5-turbo
                messages=messages,
                tools=TOOLS,
                tool_choice="auto"
            )

            msg = response.choices[0].message
            messages.append(msg)

            if msg.tool_calls:
                console.print("[blue]Executing Search...[/blue]")
                for tool_call in msg.tool_calls:
                    if tool_call.function.name == "search_linkedin":
                        # Parse args
                        try:
                            args = json.loads(tool_call.function.arguments)
                            console.print(f"[dim]Params: {args}[/dim]")
                            
                            # Execute Tool
                            result = search_linkedin(args)
                            
                            # Handle Results
                            # If result is huge, maybe truncate for context window?
                            # For now, pass it all (assuming reasonable limit)
                            tool_output = json.dumps(result)
                            
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": tool_output
                            })
                            
                        except Exception as e:
                            console.print(f"[red]Tool Execution Error: {e}[/red]")
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": f"Error: {str(e)}"
                            })

                # Second API Call (Interpret results)
                final_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages
                )
                final_msg = final_response.choices[0].message
                messages.append(final_msg)
                console.print(Markdown(final_msg.content))
            else:
                # Normal conversation (asking for more info)
                console.print(Markdown(msg.content))

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

if __name__ == "__main__":
    chat_loop()
