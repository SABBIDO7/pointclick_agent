// background.js - Service worker with keep-alive

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
  retryTimer = null,
  keepAliveTimer = null,
  isConnected = false

function connectWS() {
  // Clear any existing timers
  if (retryTimer) {
    clearTimeout(retryTimer)
    retryTimer = null
  }
  
  if (keepAliveTimer) {
    clearInterval(keepAliveTimer)
    keepAliveTimer = null
  }

  try {
    console.log('[adapter] Attempting connection to', wsUrl)
    ws = new WebSocket(wsUrl)
  } catch (e) {
    console.warn('[adapter] WebSocket creation failed:', e.message)
    scheduleReconnect()
    return
  }
  
  ws.onopen = () => {
    isConnected = true
    console.log('[adapter] ✓ Connected to', wsUrl)
    
    // Clear retry timer on successful connection
    if (retryTimer) {
      clearTimeout(retryTimer)
      retryTimer = null
    }
    
    // Start keep-alive pings every 20 seconds
    startKeepAlive()
  }
  
  ws.onclose = (e) => {
    isConnected = false
    console.log('[adapter] Disconnected (code:', e.code, ')')
    
    // Stop keep-alive
    if (keepAliveTimer) {
      clearInterval(keepAliveTimer)
      keepAliveTimer = null
    }
    
    scheduleReconnect()
  }
  
  ws.onerror = (e) => {
    isConnected = false
    console.warn('[adapter] WebSocket error:', e.type)
  }
  
  ws.onmessage = onMessage
}

function startKeepAlive() {
  /**
   * Send periodic pings to keep both the WebSocket and service worker alive.
   * This prevents the service worker from going to sleep.
   */
  if (keepAliveTimer) {
    clearInterval(keepAliveTimer)
  }
  
  console.log('[adapter] Starting keep-alive (ping every 20s)')
  
  keepAliveTimer = setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        // Send a ping message
        ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }))
        console.log('[adapter] Keep-alive ping sent')
      } catch (e) {
        console.warn('[adapter] Keep-alive ping failed:', e)
        // Connection might be dead, let onclose handle it
      }
    } else {
      console.warn('[adapter] Keep-alive: WebSocket not open, reconnecting...')
      clearInterval(keepAliveTimer)
      keepAliveTimer = null
      connectWS()
    }
  }, 20000)
}

function scheduleReconnect() {
  // Prevent multiple reconnect timers
  if (retryTimer) {
    return
  }
  
  console.log('[adapter] Will retry connection in 2 seconds...')
  retryTimer = setTimeout(() => {
    retryTimer = null
    if (!isConnected) {
      connectWS()
    }
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

async function waitForContentScript(tabId, maxAttempts = 30) {
  /**
   * Wait for content script to be ready by pinging it
   */
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
  
  // Handle pong responses (if server sends them)
  if (type === 'pong') {
    console.log('[adapter] Received pong from server')
    return
  }
  
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
        // Check connection before sending
        if (ws && isConnected && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify(rpcResult(id, { ok: true, result })))
        } else {
          throw new Error('WebSocket not connected')
        }
        break
      }
      
      case 'switch_tab': {
        const { index = 0 } = msg.params || {}
        const tabs = await chrome.tabs.query({ currentWindow: true })
        if (!tabs[index]) throw new Error(`No tab at index ${index}`)
        await chrome.tabs.update(tabs[index].id, { active: true })
        
        // Wait for content script on switched tab
        await waitForContentScript(tabs[index].id)
        
        if (ws && isConnected && ws.readyState === WebSocket.OPEN) {
          ws.send(
            JSON.stringify(
              rpcResult(id, { ok: true, result: { activeIndex: index } })
            )
          )
        }
        break
      }
      
      case 'download': {
        const { url, filename } = msg.params || {}
        if (!url) throw new Error('download: url is required')
        const idDl = await chrome.downloads.download({ url, filename })
        if (ws && isConnected && ws.readyState === WebSocket.OPEN) {
          ws.send(
            JSON.stringify(
              rpcResult(id, { ok: true, result: { downloadId: idDl } })
            )
          )
        }
        break
      }
      
      default: {
        // Forward to content script
        const result = await callContent(msg.method, msg.params || {})
        if (ws && isConnected && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify(rpcResult(id, { ok: true, result })))
        }
      }
    }
  } catch (error) {
    console.error('[adapter] RPC error:', error)
    if (ws && isConnected && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(rpcResult(id, { ok: false, error: String(error) })))
    }
  }
}

// Boot hooks - these wake the service worker
chrome.runtime.onInstalled.addListener(initAndConnect)
chrome.runtime.onStartup.addListener(initAndConnect)
chrome.action.onClicked.addListener(initAndConnect)

// CRITICAL: Keep service worker alive
// Chrome will terminate service workers after 30 seconds of inactivity
// We need to do periodic work to prevent termination
chrome.alarms.create('keep-alive', { periodInMinutes: 0.5 }) // Every 30 seconds

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'keep-alive') {
    console.log('[adapter] Keep-alive alarm fired')
    
    if (!isConnected) {
      console.log('[adapter] Not connected, attempting to connect...')
      connectWS()
    }
  }
})

// Connect immediately when service worker starts
console.log('[adapter] Service worker starting...')
initAndConnect()