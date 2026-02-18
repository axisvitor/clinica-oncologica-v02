import type { Patient } from '@/types/api'

export type PatientListCacheBase = {
  data?: Patient[]
  items?: Patient[]
  total?: number
}

export function getPatientsFromCache(cache?: PatientListCacheBase): Patient[] {
  if (!cache) return []
  if (Array.isArray(cache.data)) return cache.data
  if (Array.isArray(cache.items)) return cache.items
  return []
}

export function setPatientsInCache<T extends PatientListCacheBase>(
  cache: T,
  patients: Patient[],
  total?: number,
): T {
  const nextCache: T = {
    ...cache,
    data: patients,
    items: patients,
  }
  if (typeof total === 'number') {
    nextCache.total = total
  }
  return nextCache
}
