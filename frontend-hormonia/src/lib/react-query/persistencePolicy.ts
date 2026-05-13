/**
 * Deny-by-default React Query persistence policy for the dashboard.
 *
 * Browser persistence is allowed only for explicitly non-PHI/static reference
 * data. Patient, dashboard, auth/session, report, message, alert, AI,
 * clinical, physician, and quiz-session payloads must remain memory-only.
 */

import type { PersistedClient } from '@tanstack/react-query-persist-client'

export type PersistableQueryLike = {
  queryKey?: unknown
  options?: {
    queryKey?: unknown
  }
}

const ALLOWED_QUERY_ROOTS = new Set([
  // Static dictionaries/catalogs with no patient/session/user binding.
  'treatment-types',
  'treatment-type-dictionaries',
  'quiz-templates',
  'questionarios',
  'templates',
  'template-catalog',
  'flow-templates',
  'public-config',
  'static-config',
  'config-dictionaries',
  'metadata-dictionaries',
])

const DENIED_WORDS = new Set([
  'patient',
  'patients',
  'dashboard',
  'message',
  'messages',
  'report',
  'reports',
  'ai',
  'alert',
  'alerts',
  'physician',
  'clinical',
  'auth',
  'user',
  'users',
  'session',
  'sessions',
])

const DENIED_FULL_PREFIXES = [
  'monthly-quiz',
  'patient-quiz',
  'quiz-session',
  'quiz-sessions',
  'quiz-response',
  'quiz-responses',
]

function normalizeToken(value: string): string {
  return value
    .replace(/([a-z0-9])([A-Z])/g, '$1-$2')
    .trim()
    .toLowerCase()
    .replace(/[_\s]+/g, '-')
    .replace(/[^a-z0-9-]/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
}

function collectTokens(value: unknown, tokens: string[] = [], seen = new WeakSet<object>()): string[] {
  if (typeof value === 'string') {
    const normalized = normalizeToken(value)
    if (normalized) tokens.push(normalized)
    return tokens
  }

  if (Array.isArray(value)) {
    for (const item of value) collectTokens(item, tokens, seen)
    return tokens
  }

  if (value && typeof value === 'object') {
    if (seen.has(value)) return tokens
    seen.add(value)

    for (const [key, nestedValue] of Object.entries(value as Record<string, unknown>)) {
      const normalizedKey = normalizeToken(key)
      if (normalizedKey) tokens.push(normalizedKey)
      collectTokens(nestedValue, tokens, seen)
    }
  }

  return tokens
}

function hasDeniedToken(queryKey: unknown): boolean {
  const tokens = collectTokens(queryKey)

  return tokens.some((token) => {
    if (DENIED_FULL_PREFIXES.some((prefix) => token === prefix || token.startsWith(`${prefix}-`))) {
      return true
    }

    const parts = token.split('-').filter(Boolean)
    return parts.some((part) => DENIED_WORDS.has(part))
  })
}

function getQueryRoot(queryKey: unknown): string | undefined {
  if (typeof queryKey === 'string') {
    return normalizeToken(queryKey)
  }

  if (Array.isArray(queryKey) && typeof queryKey[0] === 'string') {
    return normalizeToken(queryKey[0])
  }

  return undefined
}

function getQueryKey(query: PersistableQueryLike | unknown): unknown {
  if (!query || typeof query !== 'object') return undefined

  const candidate = query as PersistableQueryLike
  if ('queryKey' in candidate) return candidate.queryKey
  return candidate.options?.queryKey
}

/**
 * Returns true only for explicitly allowlisted static/non-PHI query keys.
 */
export function isPersistableQueryKey(queryKey: unknown): boolean {
  if (hasDeniedToken(queryKey)) return false

  const root = getQueryRoot(queryKey)
  if (!root) return false

  return ALLOWED_QUERY_ROOTS.has(root)
}

/**
 * Provider-level predicate compatible with TanStack's shouldDehydrateQuery hook.
 */
export function shouldPersistDashboardQuery(query: PersistableQueryLike | unknown): boolean {
  return isPersistableQueryKey(getQueryKey(query))
}

function emptyPersistedClient(client?: Partial<PersistedClient>): PersistedClient {
  return {
    timestamp: typeof client?.timestamp === 'number' ? client.timestamp : Date.now(),
    buster: typeof client?.buster === 'string' ? client.buster : '',
    clientState: {
      mutations: [],
      queries: [],
    },
  }
}

/**
 * Filters a persisted React Query client down to non-PHI allowlisted queries.
 *
 * Mutations are always removed because queued mutation variables can contain
 * user/session/patient data and should never be durable browser state.
 */
export function filterPersistedClient(client: PersistedClient): PersistedClient {
  try {
    if (!client || typeof client !== 'object') {
      return emptyPersistedClient()
    }

    const clientState = (client as PersistedClient).clientState
    if (!clientState || typeof clientState !== 'object') {
      return emptyPersistedClient(client)
    }

    const queries = Array.isArray(clientState.queries) ? clientState.queries : []
    const filteredQueries = queries.filter((query) => shouldPersistDashboardQuery(query))

    return {
      ...client,
      clientState: {
        ...clientState,
        mutations: [],
        queries: filteredQueries,
      },
    }
  } catch {
    return emptyPersistedClient(client)
  }
}
