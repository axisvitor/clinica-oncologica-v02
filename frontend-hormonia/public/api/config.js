;(function () {
  const DEFAULT_CONFIG = {
    apiUrl: (typeof process !== 'undefined' && process.env && process.env.VITE_API_URL) || 'http://localhost:8000/api/v2',
    wsUrl: (typeof process !== 'undefined' && process.env && process.env.VITE_WS_BASE_URL) || 'ws://localhost:8000/ws',
    backendUrl: (typeof process !== 'undefined' && process.env && process.env.VITE_API_BASE_URL) || 'http://localhost:8000'
  }

  const globalScope = typeof window !== 'undefined' ? window : globalThis

  const normalizeConfig = (raw) => {
    if (!raw || typeof raw !== 'object') {
      return { ...DEFAULT_CONFIG }
    }

    const normalized = { ...DEFAULT_CONFIG }
    const apiUrl = raw.VITE_API_URL || raw.apiUrl
    const backendUrl = raw.VITE_API_BASE_URL || raw.backendUrl
    const wsUrl = raw.VITE_WS_BASE_URL || raw.VITE_WS_URL || raw.wsUrl

    if (typeof apiUrl === 'string' && apiUrl.length > 0) {
      normalized.apiUrl = apiUrl
    }

    if (typeof backendUrl === 'string' && backendUrl.length > 0) {
      normalized.backendUrl = backendUrl
    } else if (normalized.apiUrl.endsWith('/api/v2')) {
      normalized.backendUrl = normalized.apiUrl.replace(/\/api\/v2$/, '')
    }

    if (typeof wsUrl === 'string' && wsUrl.length > 0) {
      normalized.wsUrl = wsUrl
    } else {
      normalized.wsUrl = normalized.backendUrl.replace(/^https?:\/\//, (match) => {
        return match === 'https://' ? 'wss://' : 'ws://'
      }) + '/ws'
    }

    return normalized
  }

  let cachedConfig = normalizeConfig(globalScope.__ENV_CONFIG__)

  const hydrateFromEndpoint = async () => {
    if (typeof fetch !== 'function') {
      return cachedConfig
    }

    try {
      const response = await fetch('/api/config', {
        method: 'GET',
        cache: 'no-store',
        credentials: 'same-origin',
        headers: { 'Accept': 'application/json' }
      })

      if (response.ok) {
        const payload = await response.json()
        cachedConfig = normalizeConfig(payload)
        const currentEnv = typeof globalScope.__ENV_CONFIG__ === 'object'
          ? globalScope.__ENV_CONFIG__
          : {}
        globalScope.__ENV_CONFIG__ = Object.assign({}, currentEnv, payload, {
          VITE_API_URL: payload.VITE_API_URL || cachedConfig.apiUrl,
          VITE_API_BASE_URL: payload.VITE_API_BASE_URL || cachedConfig.backendUrl,
          VITE_WS_BASE_URL: payload.VITE_WS_BASE_URL || cachedConfig.wsUrl,
          VITE_WS_URL: payload.VITE_WS_URL || cachedConfig.wsUrl
        })
      }
    } catch (error) {
      console.warn('[RuntimeConfig] Failed to hydrate from /api/config', error)
    }

    return cachedConfig
  }

  const runtime = globalScope.__RUNTIME_CONFIG__ || {}

  if (typeof runtime.loadConfig !== 'function') {
    runtime.loadConfig = hydrateFromEndpoint
  }

  if (typeof runtime.getConfigSync !== 'function') {
    runtime.getConfigSync = () => cachedConfig
  }

  globalScope.__RUNTIME_CONFIG__ = runtime

  globalScope.getRuntimeConfig = function getRuntimeConfig() {
    return cachedConfig
  }

  // Kick off hydration but don't block rendering
  hydrateFromEndpoint()

  if (globalScope.location && globalScope.location.pathname === '/api/config') {
    const pretty = JSON.stringify(cachedConfig, null, 2)
    if (globalScope.document && globalScope.document.body) {
      globalScope.document.body.innerHTML = '<pre>' +
        pretty.replace(/[&<>]/g, (char) => {
          if (char === '&') return '&amp;'
          if (char === '<') return '&lt;'
          if (char === '>') return '&gt;'
          return char
        }) +
        '</pre>'
      globalScope.document.body.style.fontFamily = 'monospace'
      globalScope.document.body.style.whiteSpace = 'pre'
    }
  }
})()
