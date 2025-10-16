# server.py
import asyncio, json, os, uuid
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
        try:
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                if msg.get("type") == "adapter/rpc_result":
                    fut = self.pending.pop(msg.get("id"), None)
                    if fut and not fut.done():
                        fut.set_result(msg)
        finally:
            self.clients.discard(websocket)

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

async def wait_for_extension(timeout=20.0):
    """Poll for a connected extension without cross-loop Events."""
    steps = int(timeout / 0.1)
    for _ in range(max(1, steps)):
        if bridge.clients:
            return
        await asyncio.sleep(0.1)
    raise RuntimeError("Extension did not connect within timeout. Is it loaded and the service worker awake?")