// background.js - Service worker (supports modules)
const MSG = {
  HELLO: "adapter/hello",
  RPC_CALL: "adapter/rpc_call",
  RPC_RESULT: "adapter/rpc_result",
  SNAPSHOT: "adapter/snapshot"
};

function rpcResult(id, payload) {
  return { type: MSG.RPC_RESULT, id, ...payload };
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

let ws,
  wsUrl = 'ws://127.0.0.1:8765',
  retryTimer = null

function connectWS() {
  try {
    ws = new WebSocket(wsUrl)
  } catch {
    scheduleReconnect()
    return
  }
  ws.onopen = () => console.log('[adapter] connected', wsUrl)
  ws.onclose = () => {
    console.log('[adapter] disconnected')
    scheduleReconnect()
  }
  ws.onerror = (e) => {
    console.warn('[adapter] socket error', e)
    try {
      ws.close()
    } catch {}
  }
  ws.onmessage = onMessage
}

function scheduleReconnect() {
  if (!retryTimer)
    retryTimer = setTimeout(() => {
      retryTimer = null
      connectWS()
    }, 2000)
}

async function initAndConnect() {
  const s = await chrome.storage.local.get('wsUrl')
  if (s.wsUrl) wsUrl = s.wsUrl
  connectWS()
}

async function sendToActiveTab(message) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  if (!tab?.id) throw new Error('No active tab')
  return await chrome.tabs.sendMessage(tab.id, message)
}

async function callContent(method, params) {
  const payload = { type: MSG.RPC_CALL, method, params }
  const res = await sendToActiveTab(payload)
  if (!res?.ok) throw new Error(res?.error || 'unknown content error')
  return res.result
}

/**
 * Wait for content script to be ready by pinging it
 */
async function waitForContentScript(tabId, maxAttempts = 30) {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const response = await chrome.tabs.sendMessage(tabId, { 
        type: 'PING' 
      })
      if (response?.pong) {
        console.log('[adapter] content script ready after', i + 1, 'attempts')
        return true
      }
    } catch (e) {
      // Content script not ready yet, wait and retry
      console.log(`[adapter] Waiting for content script... attempt ${i + 1}/${maxAttempts}`)
      await sleep(200)
    }
  }
  throw new Error('Content script failed to load after ' + (maxAttempts * 200) + 'ms')
}

async function onMessage(evt) {
  let msg
  try {
    msg = JSON.parse(evt.data)
  } catch {
    return
  }
  const { id, type } = msg || {}
  if (type !== MSG.RPC_CALL) return // only RPCs from server

  try {
    switch (msg.method) {
      case 'navigate': {
        const { url } = msg.params
        const [tab] = await chrome.tabs.query({
          active: true,
          currentWindow: true,
        })
        const targetId = tab?.id ?? (await chrome.tabs.create({ url })).id
        
        console.log('[adapter] Navigating to', url)
        
        // Navigate
        await chrome.tabs.update(targetId, { url })
        
        // Wait for page to complete loading
        console.log('[adapter] Waiting for page load...')
        await new Promise((resolve) => {
          const listener = (tabId, changeInfo) => {
            if (tabId === targetId) {
              console.log('[adapter] Tab status:', changeInfo.status)
              if (changeInfo.status === 'complete') {
                chrome.tabs.onUpdated.removeListener(listener)
                resolve()
              }
            }
          }
          chrome.tabs.onUpdated.addListener(listener)
          
          // Fallback timeout
          setTimeout(() => {
            console.log('[adapter] Load timeout reached')
            chrome.tabs.onUpdated.removeListener(listener)
            resolve()
          }, 15000)
        })
        
        // Extra wait for SPA initialization
        console.log('[adapter] Waiting for SPA to initialize...')
        await sleep(2000)
        
        // Wait for content script to be ready
        console.log('[adapter] Checking content script readiness...')
        await waitForContentScript(targetId)
        
        console.log('[adapter] Navigation complete')
        const result = { navigated: url }
        ws?.send(JSON.stringify(rpcResult(id, { ok: true, result })))
        break
      }
      
      case 'switch_tab': {
        const { index = 0 } = msg.params || {}
        const tabs = await chrome.tabs.query({ currentWindow: true })
        if (!tabs[index]) throw new Error(`No tab at index ${index}`)
        await chrome.tabs.update(tabs[index].id, { active: true })
        
        // Wait for content script on switched tab
        await waitForContentScript(tabs[index].id)
        
        ws?.send(
          JSON.stringify(
            rpcResult(id, { ok: true, result: { activeIndex: index } })
          )
        )
        break
      }
      
      case 'download': {
        const { url, filename } = msg.params || {}
        if (!url) throw new Error('download: url is required')
        const idDl = await chrome.downloads.download({ url, filename })
        ws?.send(
          JSON.stringify(
            rpcResult(id, { ok: true, result: { downloadId: idDl } })
          )
        )
        break
      }
      
      default: {
        // Forward to content script
        const result = await callContent(msg.method, msg.params || {})
        ws?.send(JSON.stringify(rpcResult(id, { ok: true, result })))
      }
    }
  } catch (error) {
    console.error('[adapter] RPC error:', error)
    ws?.send(JSON.stringify(rpcResult(id, { ok: false, error: String(error) })))
  }
}

// Boot hooks
chrome.runtime.onInstalled.addListener(initAndConnect)
chrome.runtime.onStartup.addListener(initAndConnect)
chrome.action.onClicked.addListener(initAndConnect)