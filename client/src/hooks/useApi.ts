import { useAuth } from '@clerk/react'
import { useMemo } from 'react'
import { createApiClient } from '../lib/api'

export function useApi() {
  const { getToken } = useAuth()
  return useMemo(() => createApiClient(getToken), [getToken])
}
