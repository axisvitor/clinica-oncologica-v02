/**
 * Routes Module
 *
 * Barrel export for all route-related utilities
 */

export { ROUTES, buildPatientDetailRoute, buildPhysicianPatientDetailRoute } from './routeConfig';
export type { RouteKey } from './routeConfig';

export {
  publicRoutes,
  protectedRoutes,
  adminRoutes,
  physicianRoutes,
  allRoutes,
  PageLoader,
} from './routeDefinitions';
