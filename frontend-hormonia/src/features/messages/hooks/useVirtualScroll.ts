/**
 * useVirtualScroll Hook - Manage virtual scrolling for messages
 *
 * Handles scroll position, height estimation, and auto-scroll to bottom
 */

import { useRef, useEffect, useCallback } from 'react'
import type { VariableSizeList } from 'react-window'
import { estimateMessageHeight, getDateSeparatorHeight } from '../utils/heightEstimation'
import type { ListItem } from './useMessageGroups'

interface UseVirtualScrollOptions {
  items: ListItem[]
  autoScrollToBottom?: boolean
}

interface UseVirtualScrollReturn {
  listRef: React.RefObject<VariableSizeList | null>
  getItemSize: (index: number) => number
  scrollToBottom: () => void
}

/**
 * Hook to manage virtual scrolling behavior
 */
export function useVirtualScroll({
  items,
  autoScrollToBottom = true,
}: UseVirtualScrollOptions): UseVirtualScrollReturn {
  const listRef = useRef<VariableSizeList>(null)

  /**
   * Calculate item height based on type and content
   */
  const getItemSize = useCallback(
    (index: number): number => {
      const item = items[index]
      if (!item) return 50

      if (item.type === 'date') {
        return getDateSeparatorHeight()
      }

      if (item.type === 'message' && item.message) {
        return estimateMessageHeight(item.message.content.length)
      }

      return 50
    },
    [items]
  )

  /**
   * Scroll to bottom of list
   */
  const scrollToBottom = useCallback(() => {
    if (items.length > 0 && listRef.current) {
      listRef.current.scrollToItem(items.length - 1, 'end')
    }
  }, [items.length])

  /**
   * Auto-scroll to bottom when new messages arrive
   */
  useEffect(() => {
    if (autoScrollToBottom) {
      scrollToBottom()
    }
  }, [autoScrollToBottom, scrollToBottom])

  return {
    listRef,
    getItemSize,
    scrollToBottom,
  }
}
