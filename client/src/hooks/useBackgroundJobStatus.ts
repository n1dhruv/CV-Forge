import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import type { BackgroundJob, JobStatus } from '@/lib/types'
import { supabase } from '@/lib/supabase'
import { useApi } from './useApi'

type RealtimeState = 'connecting' | 'connected' | 'failed'
type BackgroundJobRow = BackgroundJob & { id: string }

const isTerminal = (status?: JobStatus) => status === 'done' || status === 'failed'

export function useBackgroundJobStatus(jobId?: string) {
  const api = useApi()
  const queryClient = useQueryClient()
  const [realtimeState, setRealtimeState] = useState<RealtimeState>('connecting')
  const queryKey = ['background-job', jobId] as const
  const query = useQuery({
    queryKey,
    queryFn: () => api.jd.getStatus(jobId!),
    enabled: !!jobId,
    refetchInterval: current =>
      !isTerminal(current.state.data?.status) && realtimeState === 'failed' ? 2_000 : false,
  })
  const terminal = isTerminal(query.data?.status)
  const { refetch } = query

  useEffect(() => {
    if (!jobId || terminal) return

    let active = true
    setRealtimeState('connecting')
    const channel = supabase
      .channel(`background-job:${jobId}`)
      .on(
        'postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'background_jobs', filter: `id=eq.${jobId}` },
        payload => {
          const next = payload.new as BackgroundJobRow
          if (!active || next.id !== jobId) return
          queryClient.setQueryData<BackgroundJob>(['background-job', jobId], {
            status: next.status,
            result: next.result,
            error: next.error,
          })
        },
      )
      .subscribe(status => {
        if (!active) return
        if (status === 'SUBSCRIBED') {
          setRealtimeState('connected')
          void refetch()
        } else if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT' || status === 'CLOSED') {
          setRealtimeState('failed')
        }
      })

    return () => {
      active = false
      void supabase.removeChannel(channel)
    }
  }, [jobId, queryClient, refetch, terminal])

  return { ...query, realtimeState }
}
