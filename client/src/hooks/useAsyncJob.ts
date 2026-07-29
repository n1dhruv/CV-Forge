import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { AsyncJob } from '../lib/types'
export function useAsyncJob<T>(jobId?: string, seed?: AsyncJob<T>) {
  return useQuery({ queryKey:['job',jobId], queryFn:()=>api.jobs.get<T>(jobId!), initialData:seed, enabled:Boolean(jobId), refetchInterval:(query)=>['done','failed'].includes(query.state.data?.state ?? '')?false:1200 })
}
