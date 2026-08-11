import { useQuery } from '@tanstack/react-query'
import type { JobStatus } from '@/lib/types'
import { useApi } from './useApi'

const isTerminal = (status?: JobStatus) => status === 'done' || status === 'failed'

export function useBackgroundJobStatus(jobId?: string) {
  const api = useApi()
  return useQuery({
    queryKey: ['background-job', jobId],
    queryFn: () => api.jd.getStatus(jobId!),
    enabled: !!jobId,
    refetchInterval: current =>
      isTerminal(current.state.data?.status) ? false : 2_000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: 'always',
  })
}
