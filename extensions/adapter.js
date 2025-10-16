export const MSG = {
  HELLO: "adapter/hello",
  RPC_CALL: "adapter/rpc_call",
  RPC_RESULT: "adapter/rpc_result",
  SNAPSHOT: "adapter/snapshot"
};

export function ok(result) { return { ok: true, result }; }
export function fail(error) { return { ok: false, error: String(error) }; }

export function rpcCall(id, method, params) {
  return { type: MSG.RPC_CALL, id, method, params };
}

export function rpcResult(id, payload) {
  return { type: MSG.RPC_RESULT, id, ...payload };
}

export async function sleep(ms){ return new Promise(r=>setTimeout(r, ms)); }