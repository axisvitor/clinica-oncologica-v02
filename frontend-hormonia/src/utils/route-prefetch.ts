/**
 * Route Prefetch Utility
 *
 * Implements strategic route prefetching to improve perceived performance.
 *
 * Features:
 * - Priority-based prefetching (high/medium/low)
 * - Idle callback usage for better performance
 * - Network-aware prefetching (respects save-data and connection speed)
 * - Deduplication to avoid multiple prefetches
 * - Error handling and fallbacks
 *
 * Usage:
 * ```typescript
 * import { prefetchCriticalRoutes, prefetchRoute } from '@/utils/route-prefetch'
 *
 * // In App.tsx - prefetch critical routes after initial load
 * useEffect(() => {
 *   prefetchCriticalRoutes()
 * }, [])
 *
 * // Manual prefetch on hover
 * onMouseEnter={() => prefetchRoute('/patients')}
 * ```
 */

// Route import map - maps route paths to their lazy import functions
import { createLogger } from '@/lib/logger';

// Network Information API types (not yet standardized)
interface NetworkInformation {
  readonly effectiveType?: '2g' | '3g' | '4g' | 'slow-2g';
  readonly saveData?: boolean;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type RouteImportMap = Record<string, () => Promise<any>>;

const logger = createLogger('RoutePrefetch');

const routeImports: RouteImportMap = {
  "/dashboard": () => import("@/pages/DashboardPage"),
  "/patients": () => import("@/pages/PatientsPage"),
  "/messages": () => import("@/pages/MessagesPage"),
  "/analytics": () => import("@/pages/AnalyticsPage"),
  "/reports": () => import("@/pages/ReportsPage"),
  "/alerts": () => import("@/pages/AlertsPage"),
  "/flows": () => import("@/pages/FlowsPage"),
  "/settings": () => import("@/pages/SettingsPage"),
  "/quiz": () => import("@/pages/QuizPage"),
  "/monthly-quiz": () => import("@/pages/MonthlyQuizDashboard"),
  "/questionarios": () => import("@/pages/QuestionariosPage"),
  "/whatsapp": () => import("@/pages/WhatsAppPage"),
};

// Priority levels for routes
const HIGH_PRIORITY_ROUTES = ["/dashboard", "/patients"];

const MEDIUM_PRIORITY_ROUTES = ["/messages", "/analytics", "/alerts"];

const LOW_PRIORITY_ROUTES = [
  "/reports",
  "/flows",
  "/settings",
  "/quiz",
  "/monthly-quiz",
  "/questionarios",
  "/whatsapp",
];

// Track prefetched routes to avoid duplication
const prefetchedRoutes = new Set<string>();

// Track in-progress prefetches
const prefetchingRoutes = new Map<string, Promise<{ default: React.ComponentType }>>();

/**
 * Check if prefetching should be performed based on network conditions
 */
function shouldPrefetch(): boolean {
  // Check if user has save-data preference
  if ("connection" in navigator) {
    const connection = (navigator as Navigator & { connection?: NetworkInformation }).connection;

    // Respect save-data preference
    if (connection?.saveData) {
      logger.warn("[Prefetch] Skipping prefetch - save-data enabled");
      return false;
    }

    // Don't prefetch on slow connections (2G)
    if (connection?.effectiveType === "slow-2g" || connection?.effectiveType === "2g") {
      logger.warn("[Prefetch] Skipping prefetch - slow connection");
      return false;
    }
  }

  return true;
}

/**
 * Prefetch a single route
 *
 * @param route - Route path to prefetch (e.g., '/dashboard')
 * @param force - Force prefetch even if already prefetched
 * @returns Promise that resolves when prefetch completes
 */
export async function prefetchRoute(route: string, force: boolean = false): Promise<void> {
  // Skip if already prefetched
  if (prefetchedRoutes.has(route) && !force) {
    logger.info(`[Prefetch] Route ${route} already prefetched`);
    return;
  }

  // Wait for existing prefetch if in progress
  if (prefetchingRoutes.has(route)) {
    logger.info(`[Prefetch] Route ${route} prefetch in progress`);
    await prefetchingRoutes.get(route);
    return;
  }

  // Check network conditions
  if (!shouldPrefetch()) {
    return;
  }

  const importFn = routeImports[route];

  if (!importFn) {
    logger.warn(`[Prefetch] No import function found for route: ${route}`);
    return;
  }

  logger.info(`[Prefetch] Starting prefetch for route: ${route}`);

  const prefetchPromise = importFn()
    .then((module) => {
      prefetchedRoutes.add(route);
      prefetchingRoutes.delete(route);
      logger.info(`[Prefetch] Successfully prefetched route: ${route}`);
      return module;
    })
    .catch((error) => {
      prefetchingRoutes.delete(route);
      logger.error(`[Prefetch] Failed to prefetch route ${route}:`, error);
      throw error;
    });

  prefetchingRoutes.set(route, prefetchPromise);

  return prefetchPromise.then(() => {});
}

/**
 * Prefetch multiple routes with delay between each
 *
 * @param routes - Array of route paths
 * @param delayMs - Delay in milliseconds between each prefetch
 */
async function prefetchRoutesSequentially(routes: string[], delayMs: number = 500): Promise<void> {
  for (const route of routes) {
    await prefetchRoute(route).catch(() => {
      // Swallow errors and continue
    });

    // Delay before next prefetch
    if (delayMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }
}

/**
 * Prefetch high priority routes immediately after page load
 *
 * Uses requestIdleCallback to avoid blocking main thread
 */
export function prefetchHighPriorityRoutes(): void {
  if (!shouldPrefetch()) {
    return;
  }

  const prefetchFn = () => {
    logger.info("[Prefetch] Starting high priority route prefetch");
    prefetchRoutesSequentially(HIGH_PRIORITY_ROUTES, 200);
  };

  if ("requestIdleCallback" in window) {
    requestIdleCallback(prefetchFn, { timeout: 2000 });
  } else {
    setTimeout(prefetchFn, 1000);
  }
}

/**
 * Prefetch medium priority routes after high priority routes
 */
export function prefetchMediumPriorityRoutes(): void {
  if (!shouldPrefetch()) {
    return;
  }

  const prefetchFn = () => {
    logger.info("[Prefetch] Starting medium priority route prefetch");
    prefetchRoutesSequentially(MEDIUM_PRIORITY_ROUTES, 500);
  };

  if ("requestIdleCallback" in window) {
    requestIdleCallback(prefetchFn, { timeout: 5000 });
  } else {
    setTimeout(prefetchFn, 3000);
  }
}

/**
 * Prefetch low priority routes when idle
 */
export function prefetchLowPriorityRoutes(): void {
  if (!shouldPrefetch()) {
    return;
  }

  const prefetchFn = () => {
    logger.info("[Prefetch] Starting low priority route prefetch");
    prefetchRoutesSequentially(LOW_PRIORITY_ROUTES, 1000);
  };

  if ("requestIdleCallback" in window) {
    requestIdleCallback(prefetchFn, { timeout: 10000 });
  } else {
    setTimeout(prefetchFn, 5000);
  }
}

/**
 * Prefetch all critical routes in priority order
 *
 * Call this function once after the app has loaded to prefetch
 * the most commonly used routes.
 *
 * @example
 * ```typescript
 * useEffect(() => {
 *   prefetchCriticalRoutes()
 * }, [])
 * ```
 */
export function prefetchCriticalRoutes(): void {
  logger.info("[Prefetch] Initializing critical route prefetch");

  // Prefetch high priority immediately (with delay)
  setTimeout(() => {
    prefetchHighPriorityRoutes();
  }, 1000);

  // Prefetch medium priority after high priority
  setTimeout(() => {
    prefetchMediumPriorityRoutes();
  }, 3000);

  // Prefetch low priority when really idle
  setTimeout(() => {
    prefetchLowPriorityRoutes();
  }, 8000);
}

/**
 * Prefetch route on hover with debounce
 *
 * @param route - Route to prefetch
 * @param delayMs - Delay before starting prefetch (default: 200ms)
 * @returns Cleanup function to cancel prefetch
 */
export function prefetchOnHover(route: string, delayMs: number = 200): () => void {
  let timeoutId: NodeJS.Timeout | null = null;

  timeoutId = setTimeout(() => {
    prefetchRoute(route).catch(() => {
      // Swallow errors
    });
  }, delayMs);

  // Return cleanup function
  return () => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
  };
}

/**
 * Clear prefetch cache
 * Useful for testing or when routes change
 */
export function clearPrefetchCache(): void {
  prefetchedRoutes.clear();
  prefetchingRoutes.clear();
  logger.warn("[Prefetch] Cache cleared");
}

/**
 * Get prefetch statistics
 */
export function getPrefetchStats() {
  return {
    prefetchedCount: prefetchedRoutes.size,
    inProgressCount: prefetchingRoutes.size,
    prefetchedRoutes: Array.from(prefetchedRoutes),
    inProgressRoutes: Array.from(prefetchingRoutes.keys()),
  };
}

/**
 * React hook for route prefetching on hover
 *
 * @example
 * ```typescript
 * function NavLink({ to, children }) {
 *   const { onMouseEnter, onMouseLeave } = usePrefetchRoute(to)
 *
 *   return (
 *     <Link to={to} onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave}>
 *       {children}
 *     </Link>
 *   )
 * }
 * ```
 */
export function usePrefetchRoute(route: string, delayMs: number = 200) {
  let cleanup: (() => void) | null = null;

  const onMouseEnter = () => {
    cleanup = prefetchOnHover(route, delayMs);
  };

  const onMouseLeave = () => {
    if (cleanup) {
      cleanup();
      cleanup = null;
    }
  };

  return {
    onMouseEnter,
    onMouseLeave,
  };
}

/**
 * Preload critical vendor chunks
 *
 * Useful for preloading heavy libraries before they're needed
 */
export function preloadVendorChunks(): void {
  const criticalChunks: string[] = [
    // Add paths to critical vendor chunks from build output
    // These will be determined after running 'npm run build'
  ];

  criticalChunks.forEach((chunk) => {
    const link = document.createElement("link");
    link.rel = "modulepreload";
    link.href = chunk;
    document.head.appendChild(link);
  });
}
