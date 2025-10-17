import os, asyncio
from typing import List
from anthropic import Anthropic
from dotenv import load_dotenv
from tools import CLAUDE_TOOLS
import server
from pathlib import Path


def get_system_prompt(file_path: Path):
  """Get the system prompt"""

  try:
    with open(file_path, 'r', encoding='utf-8') as md_file:
        content = md_file.read()
        return content
  except FileNotFoundError:
    print(f"Error: {file_path} not found.")
    return ""
  except Exception as e:
    print(f"Error reading {file_path}: {e}")
    return ""

class Orchestrator:
  """
  Coordinates Claude AI and the Chrome automation bridge to execute natural language tasks.

  This class sends user instructions to the Anthropic API and processes tool calls
  returned by Claude to control the browser through the Chrome Extension RPC adapter.
  It maintains conversation history, handles iterative tool calls, performs lightweight
  page-state verification after risky actions (like navigation, clicks, and typing),
  and supports multi-step browser automation.

  Workflow:
    1. Receive a natural language `task` and send it to Claude.
    2. Claude responds with tool calls (browser actions defined in CLAUDE_TOOLS).
    3. Execute each tool call via WebSocket commands in `server.rpc(...)`.
    4. Verify page state when needed and send results back to Claude.
    5. Loop until Claude signals task completion.

  Attributes:
    client (Anthropic): Claude API client instance.
    model (str): Claude model used for reasoning.
    verify_after (set): Tools that trigger auto-verification by reading viewport.
  """
    
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

    system_prompt = get_system_prompt(Path(__file__).parent / "system_prompt.md")
    
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