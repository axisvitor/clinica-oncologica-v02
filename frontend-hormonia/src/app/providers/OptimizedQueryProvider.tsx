import React, { memo, useMemo } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
// import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { createOptimizedQueryClient } from '../../lib/react-optimizations'
// import { environment } from '../../lib/environment' // Unused while devtools disabled

interface OptimizedQueryProviderProps {
  children: React.ReactNode
}

export const OptimizedQueryProvider = memo<OptimizedQueryProviderProps>(({ children }) => {
  // Create optimized query client only once
  const queryClient = useMemo(() => createOptimizedQueryClient(), [])

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {/* ReactQueryDevtools disabled due to module not found */}
      {/* {environment.isDevelopment && (
        <ReactQueryDevtools
          initialIsOpen={false}
          position="bottom-right"
          buttonPosition="bottom-right"
        />
      )} */}
    </QueryClientProvider>
  )
})

OptimizedQueryProvider.displayName = 'OptimizedQueryProvider'

export default OptimizedQueryProvider
