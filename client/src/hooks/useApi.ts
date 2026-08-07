import { useMemo } from 'react'
import { createApiClient } from '@/lib/api'
import { useAuth } from './useAuth'

export function useApi() {
  const { session } = useAuth()
  return useMemo(() => createApiClient(async()=>session?.access_token??null), [session?.access_token])
}
