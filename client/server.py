# server.py
import asyncio, json, os, uuid, subprocess, platform
import websockets
from dotenv import load_dotenv


load_dotenv()
HOST = os.getenv("WS_HOST", "127.0.0.1")
PORT = int(os.getenv("WS_PORT", "8765"))

class Bridge:
    def __init__(self):
        self.clients = set()   # extension connections
        self.pending = {}      # id -> future

    async def send_rpc(self, method, params):
        if not self.clients:
            raise RuntimeError("No extension connected. Open Chrome with the extension enabled.")
        call_id = str(uuid.uuid4())
        fut = asyncio.get_running_loop().create_future()
        self.pending[call_id] = fut
        msg = {"type": "adapter/rpc_call", "id": call_id, "method": method, "params": params}
        # send RPC to all connected clients (usually 1)
        await asyncio.gather(*(c.send(json.dumps(msg)) for c in self.clients))
        return await fut

    async def handler(self, websocket):
        self.clients.add(websocket)
        print(f"[server] ✓ Extension connected (total clients: {len(self.clients)})")
        try:
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                
                # Handle ping messages (keep-alive from extension)
                if msg.get("type") == "ping":
                    # Respond with pong
                    await websocket.send(json.dumps({"type": "pong", "timestamp": msg.get("timestamp")}))
                    continue
                
                # Handle RPC results
                if msg.get("type") == "adapter/rpc_result":
                    fut = self.pending.pop(msg.get("id"), None)
                    if fut and not fut.done():
                        fut.set_result(msg)
        finally:
            self.clients.discard(websocket)
            print(f"[server] Extension disconnected (remaining clients: {len(self.clients)})")

bridge = Bridge()

async def run_server():
    try:
        async with websockets.serve(bridge.handler, HOST, PORT):
            print(f"[server] listening ws://{HOST}:{PORT}")
            await asyncio.Future()  # run forever
    except OSError as e:
        print(f"[server] FAILED to bind ws://{HOST}:{PORT} — {e}")
        raise

async def rpc(method, **params):
    res = await bridge.send_rpc(method, params)
    if not res.get("ok"):
        raise RuntimeError(res.get("error"))
    return res.get("result")

def wake_extension():
    """
    Programmatically wake up the Chrome extension service worker.
    
    This opens the extension's service worker DevTools page, which wakes
    the worker and establishes the WebSocket connection.
    """
    # Get the extension ID from Chrome's extension directory
    # The ID is consistent per installation
    extension_url = "chrome://extensions/"
    
    system = platform.system()
    
    try:
        if system == "Darwin":  # macOS
            # Try to find Chrome
            chrome_paths = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Chrome.app/Contents/MacOS/Chrome",
            ]
            chrome_cmd = next((p for p in chrome_paths if os.path.exists(p)), None)
            
            if chrome_cmd:
                # Open extensions page in a new window (non-blocking)
                subprocess.Popen([chrome_cmd, extension_url], 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
                print("[server] Opened Chrome extensions page to wake service worker")
                return True
                
        elif system == "Linux":
            chrome_cmds = ["google-chrome", "chrome", "chromium", "chromium-browser"]
            for cmd in chrome_cmds:
                try:
                    subprocess.Popen([cmd, extension_url],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
                    print("[server] Opened Chrome extensions page to wake service worker")
                    return True
                except FileNotFoundError:
                    continue
                    
        elif system == "Windows":
            chrome_paths = [
                os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            ]
            chrome_cmd = next((p for p in chrome_paths if os.path.exists(p)), None)
            
            if chrome_cmd:
                subprocess.Popen([chrome_cmd, extension_url],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                print("[server] Opened Chrome extensions page to wake service worker")
                return True
                
    except Exception as e:
        print(f"[server] Could not auto-wake extension: {e}")
        return False
    
    return False

async def wait_for_extension(timeout=20.0, auto_wake=True):
    """
    Poll for a connected extension. Optionally attempts to wake the service worker.
    
    Args:
        timeout: Maximum time to wait in seconds
        auto_wake: If True, attempts to programmatically wake the extension
    """
    if bridge.clients:
        print("[server] Extension already connected")
        return
    
    # Try to wake the extension if requested
    if auto_wake:
        print("[server] Attempting to wake extension service worker...")
        wake_extension()
        # Give it a moment to wake up
        await asyncio.sleep(2)
    
    # Poll for connection
    steps = int(timeout / 0.1)
    for i in range(max(1, steps)):
        if bridge.clients:
            print("[server] ✓ Extension connected")
            return
        await asyncio.sleep(0.1)
    
    error_msg = (
        "Extension did not connect within timeout.\n"
        "Please manually wake the extension by:\n"
        "  1. Clicking the extension icon in Chrome toolbar, OR\n"
        "  2. Opening chrome://extensions/ and clicking 'service worker' link, OR\n"
        "  3. Refreshing the extension in chrome://extensions/\n"
        "Then re-run your command."
    )
    raise RuntimeError(error_msg)