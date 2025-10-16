from pydantic import BaseModel
from typing import Any, Dict

# RPC envelope used between orchestrator and extension
class Rpc(BaseModel):
    id: str
    type: str
    method: str
    params: Dict[str, Any] = {}

# Claude tool schemas (mirroring extension capabilities)
CLAUDE_TOOLS = [
    {
        "name": "navigate",
        "description": "Open or navigate the active tab to a URL. Always wait briefly after navigation for page to load.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"]
        }
    },
    {
        "name": "read_viewport",
        "description": "Read a plaintext snapshot of the current page (title, URL, visible text). Use this to verify page state after navigation or interactions.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "query_text",
        "description": "Get innerText or an attribute of elements matching a CSS selector. CRITICAL for extracting data like image URLs (use attr='src' on img elements) or link targets (use attr='href' on anchor tags).",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector (e.g., 'img', 'a.download-link', '#main-image')"},
                "all": {"type": "boolean", "description": "Return all matches instead of just first"},
                "attr": {"type": "string", "description": "HTML attribute to extract (e.g., 'src', 'href', 'data-url')"},
                "max": {"type": "integer", "description": "Maximum results when all=true (default 20)"}
            },
            "required": ["selector"]
        }
    },
    {
        "name": "click",
        "description": "Click the first (or Nth) element that matches a CSS selector. Element will be scrolled into view before clicking.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "index": {"type": "integer", "description": "Which match to click if multiple exist (0-indexed)"}
            },
            "required": ["selector"]
        }
    },
    {
        "name": "type",
        "description": "Type text into an input/textarea matched by a CSS selector. Triggers focus, input, and change events.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "text": {"type": "string"},
                "clear": {"type": "boolean", "description": "Clear existing text first (default true)"},
                "submit": {"type": "boolean", "description": "Submit the form after typing"}
            },
            "required": ["selector", "text"]
        }
    },
    {
        "name": "press_key",
        "description": "Send a key press to the focused element (e.g., 'Enter', 'Escape', 'Tab'). Useful for submitting forms or triggering shortcuts.",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string", "description": "Key name like 'Enter', 'Escape', 'ArrowDown'"}},
            "required": ["key"]
        }
    },
    {
        "name": "wait_for_selector",
        "description": "Block until a CSS selector exists in the DOM or timeout is reached. Use this after actions that trigger page changes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "timeout_ms": {"type": "integer", "description": "Max wait time in milliseconds (default 8000)"}
            },
            "required": ["selector"]
        }
    },
    {
        "name": "scroll",
        "description": "Scroll the page vertically by dy pixels. Use positive values to scroll down, negative to scroll up.",
        "input_schema": {
            "type": "object",
            "properties": {"dy": {"type": "integer", "description": "Pixels to scroll (e.g., 600 for one screen down)"}},
            "required": ["dy"]
        }
    },
    {
        "name": "switch_tab",
        "description": "Activate a tab by zero-based index in the current window.",
        "input_schema": {
            "type": "object",
            "properties": {"index": {"type": "integer"}},
            "required": ["index"]
        }
    },
    {
        "name": "download",
        "description": "Trigger a browser download for a direct file URL. IMPORTANT: You must first extract the URL using query_text (e.g., get 'src' attribute from an img element or 'href' from a download link). This tool cannot download from page URLs, only direct file URLs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Direct URL to file (e.g., https://example.com/image.jpg)"},
                "filename": {"type": "string", "description": "Optional filename to save as"}
            },
            "required": ["url"]
        }
    }
]