// Used For DOM Interactions

const MSG = {
  HELLO: "adapter/hello",
  RPC_CALL: "adapter/rpc_call",
  RPC_RESULT: "adapter/rpc_result",
  SNAPSHOT: "adapter/snapshot",
};

function ok(result) { return { ok: true, result }; }
function fail(error) { return { ok: false, error: String(error) }; }

console.log("[content] ready on", location.href);

const api = {
  async read_viewport() {
    const text = document.body?.innerText || "";
    const title = document.title || "";
    return {
      url: location.href,
      title,
      text: text.slice(0, 50000)
    };
  },

  async query_text({ selector, all=false, attr=null, max=20 }) {
    if (!selector) throw new Error("selector required");
    const nodes = all ? [...document.querySelectorAll(selector)] : [document.querySelector(selector)];
    const vals = nodes.filter(Boolean).slice(0, max).map(n => attr ? n.getAttribute(attr) : (n.innerText||n.textContent||""));
    return { count: vals.length, values: vals };
  },

  async click({ selector, index=0 }) {
    const el = (index===0) ? document.querySelector(selector) : document.querySelectorAll(selector)[index];
    if (!el) throw new Error(`No element for ${selector}[${index}]`);
    el.scrollIntoView({ behavior: "instant", block: "center" });
    el.click();
    return { clicked: true };
  },

  async type({ selector, text, clear=true, submit=false }) {
    if (!selector) throw new Error("selector required");
    const el = document.querySelector(selector);
    if (!el) throw new Error(`No element for ${selector}`);
    el.focus();
    el.dispatchEvent(new Event("focus", { bubbles: true }));
    if ("value" in el) {
      if (clear) el.value = "";
      el.value = (el.value || "") + (text || "");
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    } else {
      // Fallback for contenteditable
      if (clear) el.textContent = "";
      el.textContent = (el.textContent || "") + (text || "");
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    }
    if (submit) el.form?.submit();
    return { typed: text?.length||0 };
  },

  async press_key({ key="Enter" }) {
    const t = document.activeElement || document.body;
    t.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
    t.dispatchEvent(new KeyboardEvent("keyup", { key, bubbles: true }));
    return { pressed: key };
  },

  async wait_for_selector({ selector, timeout_ms=8000 }) {
    const start = Date.now();
    while (Date.now() - start < timeout_ms) {
      if (document.querySelector(selector)) return { present: true };
      await new Promise(r => setTimeout(r, 100));
    }
    throw new Error(`Timeout waiting for ${selector}`);
  },

  async scroll({ dy=600 }) {
    window.scrollBy({ top: dy, behavior: "smooth" });
    return { scrolled: dy };
  },

  async upload_file({ selector }) {
    const input = document.querySelector(selector);
    if (!input) throw new Error(`No element for ${selector}`);
    if (input.type !== "file") throw new Error("selector must target <input type=file>");
    return { uploaded: false, note: "File uploads generally require a user gesture." };
  }
};

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    // Handle PING for readiness check
    if (msg?.type === 'PING') {
      sendResponse({ pong: true });
      return;
    }
    
    if (msg?.type !== MSG.RPC_CALL) return;
    
    try {
      const fn = api[msg.method];
      if (!fn) throw new Error(`Unknown method: ${msg.method}`);
      const result = await fn(msg.params || {});
      sendResponse(ok(result));
    } catch (e) {
      sendResponse(fail(e));
    }
  })();
  return true; // async response
});