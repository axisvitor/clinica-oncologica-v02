import { describe, expect, it } from 'vitest'
import type { PersistedClient } from '@tanstack/react-query-persist-client'

import {
  filterPersistedClient,
  isPersistableQueryKey,
  shouldPersistDashboardQuery,
} from '@/lib/react-query/persistencePolicy'

function dehydratedQuery(queryKey: unknown, data: unknown = { value: 'non-sensitive' }) {
  return {
    queryHash: JSON.stringify(queryKey),
    queryKey,
    state: {
      data,
      dataUpdatedAt: 1,
      error: null,
      errorUpdatedAt: 0,
      failureCount: 0,
      failureReason: null,
      fetchFailureCount: 0,
      fetchFailureReason: null,
      fetchMeta: null,
      isInvalidated: false,
      status: 'success',
      fetchStatus: 'idle',
    },
  }
}

function persistedClient(queries: ReturnType<typeof dehydratedQuery>[]): PersistedClient {
  return {
    timestamp: 1,
    buster: '',
    clientState: {
      mutations: [
        {
          mutationKey: ['send-message'],
          state: { status: 'pending' },
        },
      ],
      queries,
    },
  } as unknown as PersistedClient
}

describe('React Query dashboard persistence policy', () => {
  it('allows only explicit non-PHI static dictionaries and template catalogs', () => {
    expect(isPersistableQueryKey(['treatment-types'])).toBe(true)
    expect(isPersistableQueryKey(['quiz-templates', { category: 'monthly' }])).toBe(true)
    expect(isPersistableQueryKey(['questionarios', { type: 'public-template' }])).toBe(true)
    expect(isPersistableQueryKey(['flow-templates'])).toBe(true)

    expect(isPersistableQueryKey(['unknown-static'])).toBe(false)
    expect(isPersistableQueryKey(undefined)).toBe(false)
    expect(isPersistableQueryKey({ scope: 'static-config' })).toBe(false)
  })

  it('denies PHI, auth, dashboard, report, message, AI, and quiz-session keys', () => {
    const deniedKeys = [
      ['patients', { page: 1 }],
      ['patient', 'opaque-id'],
      ['dashboard-metrics'],
      ['messages', { patient_id: 'opaque-id' }],
      ['reports', { reportId: 'opaque-id' }],
      ['ai-insights', 'opaque-id'],
      ['alerts', { page: 1 }],
      ['physician', 'patients'],
      ['clinical', 'metrics'],
      ['auth', 'me'],
      ['user', 'preferences'],
      ['monthly-quiz-status', 'opaque-id'],
      ['patient-quiz-sessions', 'opaque-id'],
      ['quiz-session-analysis', 'opaque-id'],
      ['quiz-templates', { patientId: 'opaque-id' }],
      ['templates', { session_id: 'opaque-id' }],
    ]

    for (const queryKey of deniedKeys) {
      expect(isPersistableQueryKey(queryKey), JSON.stringify(queryKey)).toBe(false)
    }
  })

  it('filters mixed persisted clients and drops durable mutations', () => {
    const client = persistedClient([
      dehydratedQuery(['treatment-types'], { items: ['static'] }),
      dehydratedQuery(['patients', { page: 1 }], { items: ['redacted'] }),
      dehydratedQuery(['quiz-templates', { category: 'monthly' }], { items: ['static'] }),
      dehydratedQuery(['monthly-quiz-status', 'opaque-id'], { status: 'redacted' }),
      dehydratedQuery(['reports', { report_id: 'opaque-id' }], { value: 'redacted' }),
      dehydratedQuery(['messages', { patient_id: 'opaque-id' }], { value: 'redacted' }),
      dehydratedQuery(['auth', 'me'], { value: 'redacted' }),
    ])

    const filtered = filterPersistedClient(client)

    expect(filtered.clientState.mutations).toEqual([])
    expect(filtered.clientState.queries.map((query) => query.queryKey)).toEqual([
      ['treatment-types'],
      ['quiz-templates', { category: 'monthly' }],
    ])
  })

  it('treats legacy malformed or unknown persisted states as empty instead of throwing', () => {
    const malformed = {
      timestamp: 1,
      buster: '',
      clientState: {
        mutations: [{ mutationKey: ['auth'], state: {} }],
        queries: [
          dehydratedQuery({ nested: { patient_id: 'opaque-id' } }),
          dehydratedQuery(['unknown-key']),
        ],
      },
    } as unknown as PersistedClient

    const filtered = filterPersistedClient(malformed)

    expect(filtered.clientState.mutations).toEqual([])
    expect(filtered.clientState.queries).toEqual([])
  })

  it('supports provider-level shouldDehydrateQuery objects without payload inspection', () => {
    expect(shouldPersistDashboardQuery({ queryKey: ['templates'] })).toBe(true)
    expect(shouldPersistDashboardQuery({ queryKey: ['templates', { report_id: 'opaque-id' }] })).toBe(
      false
    )
    expect(shouldPersistDashboardQuery({ options: { queryKey: ['auth', 'me'] } })).toBe(false)
    expect(shouldPersistDashboardQuery(null)).toBe(false)
  })
})
