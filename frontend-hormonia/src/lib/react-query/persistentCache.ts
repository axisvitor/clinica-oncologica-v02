/**
 * IndexedDB Persistent Cache for React Query
 *
 * Provides offline-first caching with automatic TTL management,
 * cache invalidation, and error handling with fallbacks.
 *
 * Features:
 * - 7-day default TTL with automatic expiration
 * - IndexedDB integration for persistent storage
 * - Automatic cache versioning and migration
 * - Error boundaries with graceful degradation
 * - Cache size monitoring and cleanup
 *
 * @module persistentCache
 */

import { openDB, DBSchema, IDBPDatabase } from 'idb'
import { PersistedClient, Persister } from '@tanstack/react-query-persist-client'
import { createLogger } from '@/lib/logger'

const logger = createLogger('QueryCache')

/**
 * IndexedDB schema for React Query cache
 */
interface QueryCacheDB extends DBSchema {
  queryCache: {
    key: string
    value: PersistedClient
  }
  metadata: {
    key: string
    value: CacheMetadata
  }
}

/**
 * Cache metadata for monitoring and management
 */
interface CacheMetadata {
  version: number
  createdAt: number
  lastAccessed: number
  size: number
  queryCount: number
}

/**
 * Cache configuration options
 */
interface CacheConfig {
  /** Database name for IndexedDB */
  dbName?: string
  /** Cache version for migrations */
  version?: number
  /** Time-to-live in milliseconds (default: 7 days) */
  ttl?: number
  /** Maximum cache size in bytes (default: 50MB) */
  maxSize?: number
  /** Enable debug logging */
  debug?: boolean
  /** Optional policy filter applied before writes and after legacy restores */
  filterClient?: (client: PersistedClient) => PersistedClient
}

// Constants
const DEFAULT_DB_NAME = 'react-query-cache'
const DEFAULT_CACHE_VERSION = 1
const DEFAULT_CACHE_TTL = 1000 * 60 * 60 * 24 * 7 // 7 days
const DEFAULT_MAX_SIZE = 50 * 1024 * 1024 // 50MB

/**
 * Logger utility for cache operations
 */
class CacheLogger {
  constructor(private debug: boolean = false) {}

  info(message: string, ...args: unknown[]) {
    if (this.debug) {
      logger.info(`[QueryCache] ${message}`, ...args)
    }
  }

  warn(message: string, ...args: unknown[]) {
    logger.warn(`[QueryCache] ${message}`, ...args)
  }

  error(message: string, ...args: unknown[]) {
    logger.error(`[QueryCache] ${message}`, ...args)
  }
}

/**
 * Creates an IndexedDB-backed persister for React Query
 *
 * @param config - Configuration options for the cache
 * @returns Persister instance for React Query
 *
 * @example
 * ```typescript
 * const persister = createIndexedDBPersister({
 *   ttl: 1000 * 60 * 60 * 24, // 1 day
 *   debug: true
 * });
 * ```
 */
export function createIndexedDBPersister(config: CacheConfig = {}): Persister {
  const {
    dbName = DEFAULT_DB_NAME,
    version = DEFAULT_CACHE_VERSION,
    ttl = DEFAULT_CACHE_TTL,
    maxSize = DEFAULT_MAX_SIZE,
    debug = false,
    filterClient,
  } = config

  const logger = new CacheLogger(debug)
  let db: IDBPDatabase<QueryCacheDB> | null = null
  let initializationPromise: Promise<IDBPDatabase<QueryCacheDB>> | null = null

  /**
   * Initialize or retrieve the IndexedDB instance
   */
  async function getDB(): Promise<IDBPDatabase<QueryCacheDB>> {
    if (db) return db

    if (initializationPromise) {
      return initializationPromise
    }

    initializationPromise = (async () => {
      try {
        logger.info('Initializing IndexedDB', { dbName, version })

        const database = await openDB<QueryCacheDB>(dbName, version, {
          upgrade(db, oldVersion, newVersion, _transaction) {
            logger.info('Upgrading database', { oldVersion, newVersion })

            // Create object stores if they don't exist
            if (!db.objectStoreNames.contains('queryCache')) {
              db.createObjectStore('queryCache')
              logger.info('Created queryCache store')
            }

            if (!db.objectStoreNames.contains('metadata')) {
              db.createObjectStore('metadata')
              logger.info('Created metadata store')
            }
          },
          blocked() {
            logger.warn('Database upgrade blocked by another tab')
          },
          blocking() {
            logger.warn('This tab is blocking database upgrade')
          },
          terminated() {
            logger.error('Database connection terminated unexpectedly')
            db = null
            initializationPromise = null
          },
        })

        db = database
        logger.info('IndexedDB initialized successfully')
        return database
      } catch (error) {
        logger.error('Failed to initialize IndexedDB', error)
        initializationPromise = null
        throw error
      }
    })()

    return initializationPromise
  }

  /**
   * Get or create cache metadata
   */
  async function getMetadata(database: IDBPDatabase<QueryCacheDB>): Promise<CacheMetadata> {
    try {
      const existing = await database.get('metadata', 'info')
      if (existing) {
        return existing
      }
    } catch (error) {
      logger.warn('Failed to retrieve metadata', error)
    }

    // Create default metadata
    const metadata: CacheMetadata = {
      version,
      createdAt: Date.now(),
      lastAccessed: Date.now(),
      size: 0,
      queryCount: 0,
    }

    try {
      await database.put('metadata', metadata, 'info')
    } catch (error) {
      logger.warn('Failed to store metadata', error)
    }

    return metadata
  }

  /**
   * Update cache metadata
   */
  async function updateMetadata(
    database: IDBPDatabase<QueryCacheDB>,
    updates: Partial<CacheMetadata>
  ): Promise<void> {
    try {
      const current = await getMetadata(database)
      const updated: CacheMetadata = {
        ...current,
        ...updates,
        lastAccessed: Date.now(),
      }
      await database.put('metadata', updated, 'info')
      logger.info('Metadata updated', updates)
    } catch (error) {
      logger.warn('Failed to update metadata', error)
    }
  }

  /**
   * Calculate approximate size of cached data
   */
  function calculateSize(client: PersistedClient): number {
    try {
      return JSON.stringify(client).length * 2 // Approximate UTF-16 bytes
    } catch {
      return 0
    }
  }

  function getQueryCount(client: PersistedClient): number {
    return Array.isArray(client.clientState?.queries) ? client.clientState.queries.length : 0
  }

  function emptyClientFrom(client?: Partial<PersistedClient>): PersistedClient {
    return {
      timestamp: typeof client?.timestamp === 'number' ? client.timestamp : Date.now(),
      buster: typeof client?.buster === 'string' ? client.buster : '',
      clientState: {
        mutations: [],
        queries: [],
      },
    }
  }

  function applyClientFilter(client: PersistedClient): PersistedClient {
    if (!filterClient) return client

    try {
      return filterClient(client)
    } catch (error) {
      logger.warn('Client filter failed; dropping persisted query payloads', error)
      return emptyClientFrom(client)
    }
  }

  /**
   * Check if cache has exceeded size limit
   */
  async function checkCacheSize(database: IDBPDatabase<QueryCacheDB>): Promise<boolean> {
    try {
      const metadata = await getMetadata(database)
      if (metadata.size > maxSize) {
        logger.warn('Cache size exceeded limit', {
          size: metadata.size,
          maxSize,
        })
        return true
      }
      return false
    } catch {
      return false
    }
  }

  /**
   * Clear cache if it's too large
   */
  async function clearIfOversized(database: IDBPDatabase<QueryCacheDB>): Promise<void> {
    const isOversized = await checkCacheSize(database)
    if (isOversized) {
      logger.info('Clearing oversized cache')
      await database.delete('queryCache', 'state')
      await updateMetadata(database, { size: 0, queryCount: 0 })
    }
  }

  return {
    /**
     * Persist React Query client state to IndexedDB
     */
    async persistClient(client: PersistedClient): Promise<void> {
      try {
        const database = await getDB()

        // Check cache size before persisting
        await clearIfOversized(database)

        const originalQueryCount = getQueryCount(client)
        const filteredClient = applyClientFilter(client)
        const queryCount = getQueryCount(filteredClient)

        // Store only the filtered client state
        await database.put('queryCache', filteredClient, 'state')

        // Update metadata from the filtered payload only
        const size = calculateSize(filteredClient)
        const filteredOutCount = Math.max(0, originalQueryCount - queryCount)

        await updateMetadata(database, { size, queryCount })

        logger.info('Client state persisted', { size, queryCount, filteredOutCount })
      } catch (error) {
        logger.error('Failed to persist client state', error)
        // Don't throw - allow app to continue without persistence
      }
    },

    /**
     * Restore React Query client state from IndexedDB
     */
    async restoreClient(): Promise<PersistedClient | undefined> {
      try {
        const database = await getDB()
        const cache = await database.get('queryCache', 'state')

        if (!cache) {
          logger.info('No cached state found')
          return undefined
        }

        // Check if cache has expired
        const age = Date.now() - cache.timestamp
        if (age > ttl) {
          logger.info('Cache expired, clearing', { age, ttl })
          await database.delete('queryCache', 'state')
          await updateMetadata(database, { size: 0, queryCount: 0 })
          return undefined
        }

        const filteredCache = applyClientFilter(cache)
        const originalQueryCount = getQueryCount(cache)
        const queryCount = getQueryCount(filteredCache)

        if (queryCount !== originalQueryCount) {
          await database.put('queryCache', filteredCache, 'state')
          await updateMetadata(database, {
            size: calculateSize(filteredCache),
            queryCount,
          })
        } else {
          // Update last accessed time
          await updateMetadata(database, {})
        }

        logger.info('Client state restored', {
          age,
          queryCount,
          filteredOutCount: Math.max(0, originalQueryCount - queryCount),
        })

        return filteredCache
      } catch (error) {
        logger.error('Failed to restore client state', error)
        return undefined
      }
    },

    /**
     * Remove cached client state
     */
    async removeClient(): Promise<void> {
      try {
        const database = await getDB()
        await database.delete('queryCache', 'state')
        await updateMetadata(database, { size: 0, queryCount: 0 })
        logger.info('Client state removed')
      } catch (error) {
        logger.error('Failed to remove client state', error)
      }
    },
  }
}

/**
 * Clear all React Query cache data
 *
 * @param dbName - Database name to clear (default: 'react-query-cache')
 *
 * @example
 * ```typescript
 * await clearQueryCache();
 * ```
 */
export async function clearQueryCache(dbName: string = DEFAULT_DB_NAME): Promise<void> {
  try {
    const db = await openDB<QueryCacheDB>(dbName, DEFAULT_CACHE_VERSION)
    await db.clear('queryCache')
    await db.clear('metadata')
    logger.info('[QueryCache] Cache cleared successfully')
  } catch (error) {
    logger.error('[QueryCache] Failed to clear cache', error)
    throw error
  }
}

/**
 * Get cache metadata and statistics
 *
 * @param dbName - Database name to query (default: 'react-query-cache')
 * @returns Cache metadata or null if not available
 *
 * @example
 * ```typescript
 * const stats = await getCacheStats();
 * console.log(`Cache size: ${stats?.size} bytes`);
 * ```
 */
export async function getCacheStats(
  dbName: string = DEFAULT_DB_NAME
): Promise<CacheMetadata | null> {
  try {
    const db = await openDB<QueryCacheDB>(dbName, DEFAULT_CACHE_VERSION)
    const metadata = await db.get('metadata', 'info')
    return metadata || null
  } catch (error) {
    logger.error('[QueryCache] Failed to get cache stats', error)
    return null
  }
}

/**
 * Export cache data for debugging or backup
 *
 * @param dbName - Database name to export (default: 'react-query-cache')
 * @returns Serialized cache data or null
 */
export async function exportCacheData(dbName: string = DEFAULT_DB_NAME): Promise<string | null> {
  try {
    const db = await openDB<QueryCacheDB>(dbName, DEFAULT_CACHE_VERSION)
    const cache = await db.get('queryCache', 'state')
    const metadata = await db.get('metadata', 'info')

    return JSON.stringify({ cache, metadata }, null, 2)
  } catch (error) {
    logger.error('[QueryCache] Failed to export cache data', error)
    return null
  }
}
