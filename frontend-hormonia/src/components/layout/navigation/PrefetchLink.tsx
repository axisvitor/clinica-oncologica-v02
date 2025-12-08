/**
 * PrefetchLink Component
 *
 * Enhanced Link component that prefetches route code on hover.
 * Improves perceived performance by loading page code before navigation.
 *
 * Features:
 * - Automatic prefetch on hover (with configurable delay)
 * - Respects network conditions (save-data, slow connections)
 * - Cancels prefetch on mouse leave
 * - Falls back gracefully on errors
 * - TypeScript support for all react-router-dom Link props
 *
 * Usage:
 * ```tsx
 * import { PrefetchLink } from '@/components/navigation/PrefetchLink'
 *
 * // Basic usage
 * <PrefetchLink to="/dashboard">
 *   Dashboard
 * </PrefetchLink>
 *
 * // With custom delay
 * <PrefetchLink to="/patients" prefetchDelay={300}>
 *   Pacientes
 * </PrefetchLink>
 *
 * // Disable prefetch
 * <PrefetchLink to="/settings" enablePrefetch={false}>
 *   Configurações
 * </PrefetchLink>
 * ```
 */

import { useRef, MouseEvent, TouchEvent } from "react";
import { Link, LinkProps } from "react-router-dom";
import { usePrefetchRoute } from "@/utils/route-prefetch";

export interface PrefetchLinkProps
  extends Omit<LinkProps, "onMouseEnter" | "onMouseLeave" | "onTouchStart"> {
  /**
   * Delay in milliseconds before starting prefetch on hover
   * @default 200
   */
  prefetchDelay?: number;

  /**
   * Enable/disable prefetch functionality
   * @default true
   */
  enablePrefetch?: boolean;

  /**
   * Callback fired when prefetch starts
   */
  onPrefetchStart?: (route: string) => void;

  /**
   * Callback fired when prefetch is cancelled
   */
  onPrefetchCancel?: (route: string) => void;

  /**
   * Mouse enter event handler
   */
  onMouseEnter?: (event: MouseEvent<HTMLAnchorElement>) => void;

  /**
   * Mouse leave event handler
   */
  onMouseLeave?: (event: MouseEvent<HTMLAnchorElement>) => void;

  /**
   * Touch start event handler
   */
  onTouchStart?: (event: TouchEvent<HTMLAnchorElement>) => void;
}

export function PrefetchLink({
  to,
  children,
  prefetchDelay = 200,
  enablePrefetch = true,
  onPrefetchStart,
  onPrefetchCancel,
  onMouseEnter: onMouseEnterProp,
  onMouseLeave: onMouseLeaveProp,
  onTouchStart: onTouchStartProp,
  ...linkProps
}: PrefetchLinkProps) {
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const hasTriggeredRef = useRef(false);

  // Extract route path
  const route = typeof to === "string" ? to : to.pathname || "";

  // Get prefetch handlers from hook
  const prefetchHandlers = usePrefetchRoute(route, prefetchDelay);

  /**
   * Handle mouse enter - start prefetch with delay
   */
  const handleMouseEnter = (event: MouseEvent<HTMLAnchorElement>) => {
    // Call original handler if provided
    onMouseEnterProp?.(event);

    // Skip if prefetch disabled or already triggered
    if (!enablePrefetch || hasTriggeredRef.current) {
      return;
    }

    // Clear any existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    // Start prefetch with delay
    timeoutRef.current = setTimeout(() => {
      hasTriggeredRef.current = true;
      onPrefetchStart?.(route);
      prefetchHandlers.onMouseEnter();
    }, prefetchDelay);
  };

  /**
   * Handle mouse leave - cancel pending prefetch
   */
  const handleMouseLeave = (event: MouseEvent<HTMLAnchorElement>) => {
    // Call original handler if provided
    onMouseLeaveProp?.(event);

    // Cancel prefetch if not yet triggered
    if (timeoutRef.current && !hasTriggeredRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
      onPrefetchCancel?.(route);
      prefetchHandlers.onMouseLeave();
    }
  };

  /**
   * Handle touch start - trigger immediate prefetch on mobile
   */
  const handleTouchStart = (event: React.TouchEvent<HTMLAnchorElement>) => {
    // Call original handler if provided
    if (onTouchStartProp) {
      onTouchStartProp(event as any);
    }

    // Skip if prefetch disabled or already triggered
    if (!enablePrefetch || hasTriggeredRef.current) {
      return;
    }

    // Immediate prefetch on touch (no delay)
    hasTriggeredRef.current = true;
    onPrefetchStart?.(route);
    prefetchHandlers.onMouseEnter();
  };

  return (
    <Link
      to={to}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onTouchStart={handleTouchStart}
      {...linkProps}
    >
      {children}
    </Link>
  );
}

/**
 * Variant with visual loading indicator (optional)
 */
export function PrefetchLinkWithIndicator({ children, ...props }: PrefetchLinkProps) {
  return (
    <PrefetchLink
      {...props}
      className={`${props.className || ""} transition-opacity hover:opacity-80`}
    >
      {children}
    </PrefetchLink>
  );
}
