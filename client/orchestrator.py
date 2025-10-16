import os, asyncio
from typing import List
from anthropic import Anthropic
from dotenv import load_dotenv
from tools import CLAUDE_TOOLS
import server
from datetime import datetime

def get_system_prompt() -> str:
    """Generate system prompt with current date dynamically"""
    
    return f"""You are an advanced browser automation agent with comprehensive web interaction capabilities.

CORE CAPABILITIES:
You have access to tools for navigation, interaction, data extraction, file operations, and tab management. Always approach tasks methodically and verify outcomes.

OPERATING PRINCIPLES:
1. Verify page state after major actions using read_viewport
2. Wait for elements to load before interacting (use wait_for_selector)
3. Extract data with query_text before performing dependent actions
4. Use stable CSS selectors and avoid fragile element targeting
5. Handle errors gracefully and retry with alternative approaches
6. Report progress and findings clearly to the user

TASK EXECUTION PATTERNS:

Navigation & Search:
  1. Navigate to target URL
  2. Wait for page load completion (check viewport or key selectors)
  3. Interact with UI elements (search, click, type)
  4. Verify action results before proceeding

Gmail Search (Optimized):
  - Use direct URL navigation for searches: https://mail.google.com/mail/u/0/#search/ENCODED_QUERY

Web Scraping & Downloads:
  1. Navigate to target page
  2. Wait for content to load
  3. Use query_text to extract data (text, links, image URLs)
  4. For images: extract 'src' attribute from img tags
  5. For downloads: get href from download links or img src
  6. Call download tool with the extracted URL

File Uploads:
  1. Locate file input element (usually <input type="file">)
  2. Use upload_file tool with selector and file path
  3. Wait for upload confirmation

Tab Management:
  1. Use switch_tab with zero-based index to change active tab
  2. After switching, verify correct tab is active (read_viewport)
  3. Content script must be ready on target tab before interactions

Multi-Step Workflows:
  - Break complex tasks into discrete steps
  - Verify each step before proceeding to next
  - If a step fails, diagnose with read_viewport and try alternatives
  - Use scroll when content is below viewport
  - Handle popups, cookie banners, and login screens as needed

ERROR RECOVERY:
  - If selector not found: wait longer, scroll, or try alternative selector
  - If navigation fails: check URL, wait for load, refresh if needed
  - If search doesn't execute: use direct URL method
  - If download fails: verify URL is direct file link, not webpage
  - If upload fails: confirm input type="file" and file path is valid

BEST PRACTICES:
  - Always read viewport after navigation to understand page state
  - Use descriptive selectors (aria-labels, data attributes, IDs)
  - Wait appropriately between actions (1-2 seconds for UI updates)
  - Prefer direct URL manipulation for complex searches (Gmail, filters)
  - Extract data before performing actions that depend on it
  - Report clear, actionable results to the user

Continue executing steps until task completion or determination of impossibility."""

class Orchestrator:
  def __init__(self):
    load_dotenv()
    self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    self.model = os.getenv("ANTHROPIC_MODEL")
    self.verify_after = {"navigate", "click", "type"}
  
  async def run(self, task: str):
    messages: List[dict] = [
      {"role": "user", "content": task}
    ]
    max_iterations = 50
    iteration = 0
    
    system_prompt = get_system_prompt()
    
    while iteration < max_iterations:
      iteration += 1
      resp = self.client.messages.create(
        model=self.model,
        system=system_prompt,
        max_tokens=8000,
        messages=messages,
        tools=CLAUDE_TOOLS
      )
      
      tool_calls = [b for b in resp.content if b.type == "tool_use"]
      text_parts = [b for b in resp.content if b.type == "text"]
      
      if text_parts:
        print(f"\n[Agent Reasoning #{iteration}]:", "\n".join([t.text for t in text_parts]))
      
      if not tool_calls:
        print("\n[Task Complete]")
        break

      tool_results = []
      for call in tool_calls:
        print(f"[Tool Call] {call.name}({call.input})")
        try:
          result = await server.rpc(call.name, **(call.input or {}))
          print(f"[Tool Result] {result}")
          
          result_text = str(result)
          
          if call.name in self.verify_after:
            await asyncio.sleep(1.5)
            try:
              viewport = await server.rpc("read_viewport")
              result_text += f"\n\n[Page State After {call.name}]:\nTitle: {viewport.get('title', 'N/A')}\nURL: {viewport.get('url', 'N/A')}"
              print(f"[Auto-Verify] Page state: {viewport.get('title', 'N/A')}")
            except Exception as e:
              print(f"[Auto-Verify Failed] {e}")
          
          tool_results.append({
            "type": "tool_result",
            "tool_use_id": call.id,
            "content": [{"type": "text", "text": result_text}],
          })
                  
        except Exception as e:
          print(f"[Tool Error] {e}")
          tool_results.append({
            "type": "tool_result",
            "tool_use_id": call.id,
            "is_error": True,
            "content": [{"type": "text", "text": str(e)}],
          })

      messages.append({"role": "assistant", "content": resp.content})
      messages.append({"role": "user", "content": tool_results})
    
    if iteration >= max_iterations:
      print("\n[Warning] Max iterations reached")

async def main(task: str):
    server_task = asyncio.create_task(server.run_server())
    try:
        await server.wait_for_extension(timeout=20)
        orch = Orchestrator()
        await orch.run(task)
    finally:
        server_task.cancel()

if __name__ == "__main__":
  import sys
  asyncio.run(main(sys.argv[1]))