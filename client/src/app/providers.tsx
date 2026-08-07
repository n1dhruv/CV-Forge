"use client"

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { AuthProvider } from '@/hooks/useAuth'
import { UIProvider } from '@/store/ui'
import { LenisProvider } from '@/components/motion/LenisProvider'

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: Infinity,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
        retry: 1,
      },
    },
  }))

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <UIProvider>
          <LenisProvider>
            {children}
          </LenisProvider>
        </UIProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}
