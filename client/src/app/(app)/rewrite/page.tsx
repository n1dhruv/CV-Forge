"use client"

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Check, FileText, LoaderCircle, ShieldCheck } from 'lucide-react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { useEffect, useState } from 'react'
import { PageHeader } from '@/components/PageHeader'
import { RewriteBulletCard } from '@/components/rewrite/RewriteBulletCard'
import { ScreenState } from '@/components/ScreenState'
import { useApi } from '@/hooks/useApi'
import { useBackgroundJobStatus } from '@/hooks/useBackgroundJobStatus'
import type { ResumeBulletSelection, ResumeBulletSelectionUpdate } from '@/lib/types'

export default function RewriteReview() {
  const api = useApi()
  const queryClient = useQueryClient()
  const params = useSearchParams()
  const router = useRouter()
  const versionId = params.get('version')
  const jobId = params.get('job') ?? undefined
  const jdId = params.get('jd')
  const reviewHref = jdId ? `/review?jd=${encodeURIComponent(jdId)}` : '/review'
  const [editing, setEditing] = useState<Set<string>>(new Set())
  const [assemblyJobId, setAssemblyJobId] = useState<string>()
  const [compileJobId, setCompileJobId] = useState<string>()
  const job = useBackgroundJobStatus(jobId)
  const jobDone = !jobId || job.data?.status === 'done'
  const bullets = useQuery({
    queryKey: ['resume-version-bullets', versionId],
    queryFn: () => api.resumeVersions.bullets(versionId!),
    enabled: !!versionId && jobDone,
  })
  const version = useQuery({
    queryKey: ['resume-version', versionId],
    queryFn: () => api.resumeVersions.get(versionId!),
    enabled: !!versionId && jobDone,
  })

  const update = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ResumeBulletSelectionUpdate }) => api.resumeVersions.updateBullet(id, payload),
    onSuccess: changed => queryClient.setQueryData<ResumeBulletSelection[]>(
      ['resume-version-bullets', versionId],
      current => current?.map(bullet => bullet.id === changed.id ? changed : bullet),
    ),
  })
  const approveAll = useMutation({
    mutationFn: async (items: ResumeBulletSelection[]) => Promise.all(items.map(item => api.resumeVersions.updateBullet(item.id, { approved: true }))),
    onSuccess: changed => {
      const byId = new Map(changed.map(item => [item.id, item]))
      queryClient.setQueryData<ResumeBulletSelection[]>(['resume-version-bullets', versionId], current => current?.map(item => byId.get(item.id) ?? item))
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['resume-version-bullets', versionId] }),
  })
  const finalize = useMutation({
    mutationFn: () => api.resumeVersions.finalize(versionId!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['resume-version', versionId] }),
  })
  const assemble = useMutation({
    mutationFn: () => api.resumeVersions.assemble(versionId!),
    onSuccess: queued => setAssemblyJobId(queued.background_job_id),
  })
  const assemblyJob = useBackgroundJobStatus(assemblyJobId)
  const compile = useMutation({
    mutationFn: () => api.resumeVersions.compile(versionId!),
    onSuccess: queued => setCompileJobId(queued.background_job_id),
  })
  const compileJob = useBackgroundJobStatus(compileJobId)

  useEffect(() => {
    if (assemblyJob.data?.status === 'done' && !compileJobId && !compile.isPending) compile.mutate()
  }, [assemblyJob.data?.status, compile, compileJobId])

  useEffect(() => {
    if (!compileJobId || !compileJob.data) return
    if (compileJob.data.status === 'done' || compileJob.data.status === 'failed') {
      router.push(`/resume-versions/${versionId}/editor?job=${compileJobId}`)
    }
  }, [compileJob.data, compileJobId, router, versionId])

  if (!versionId) {
    return <div className="container-normal py-12"><ScreenState kind="empty" title="Choose a resume draft first" detail="Start from Match & Review and select the proof points you want rewritten." /><div className="mt-6 flex justify-center"><Link className="button-primary" href="/job-description">Choose a job description</Link></div></div>
  }

  if (jobId && (job.isPending || job.data?.status === 'queued' || job.data?.status === 'running')) {
    const stage = job.data?.status === 'running' ? 'Rewriting and checking every proposal for unsupported changes.' : 'Your selected bullets are queued for rewriting.'
    return <div className="container-normal py-12"><ScreenState kind="loading" title="Preparing safe rewrites…" detail={stage} /></div>
  }

  if (job.data?.status === 'failed') {
    return (
      <div className="container-normal py-12">
        <ScreenState kind="error" title="Rewrite could not finish" detail={job.data.error ?? 'The rewrite worker failed. Return to Match & Review and try again.'} />
        <div className="mt-6 flex justify-center"><Link className="button-secondary" href={reviewHref}><ArrowLeft size={16} /> Back to Match & Review</Link></div>
      </div>
    )
  }

  if (job.isError) {
    return <div className="container-normal py-12"><ScreenState kind="error" title="Rewrite status unavailable" detail={job.error.message} onRetry={() => void job.refetch()} /></div>
  }

  if (bullets.isPending) return <div className="container-normal py-12"><ScreenState kind="loading" title="Opening your review…" detail="Loading the original and proposed wording side by side." /></div>
  if (bullets.isError) return <div className="container-normal py-12"><ScreenState kind="error" title="Review unavailable" detail={bullets.error.message} onRetry={() => void bullets.refetch()} /></div>
  if (!bullets.data?.length) return <div className="container-normal py-12"><ScreenState kind="empty" title="No rewrites to review" detail="This resume draft has no selected bullets." /><div className="mt-6 flex justify-center"><Link className="button-secondary" href={reviewHref}>Back to Match & Review</Link></div></div>

  const unresolved = bullets.data.filter(bullet => !bullet.resolved)
  const bulkEligible = unresolved.filter(bullet => bullet.flagged_terms.length === 0)
  const busy = update.isPending || approveAll.isPending || finalize.isPending
  const error = update.error ?? approveAll.error ?? finalize.error
  const finalized = finalize.data?.status === 'finalized' || version.data?.status === 'finalized'

  return (
    <div className="container-normal py-10 pb-28 md:py-12">
      <PageHeader
        eyebrow="Rewrite review"
        title="Compare every change"
        description="Original evidence stays untouched. A proposal only counts after you approve it or explicitly keep the original."
        action={<Link className="button-secondary" href={reviewHref}><ArrowLeft size={16} aria-hidden="true" /> Match & Review</Link>}
      />

      {finalized ? (
        <section className="rounded-xl border border-success/30 bg-success/10 px-6 py-8 text-center" role="status">
          <ShieldCheck className="mx-auto text-success" size={30} aria-hidden="true" />
          <h2 className="mt-4 font-display text-2xl font-medium">Review finalized</h2>
          <p className="mx-auto mt-2 max-w-xl text-sm text-muted">Every bullet has an explicit decision. This version is ready for resume assembly.</p>
          <div className="mt-6" aria-live="polite">
            {assemblyJobId || compileJobId ? (
              <div className="mx-auto max-w-md rounded-lg bg-canvas/70 px-5 py-4 text-left">
                <p className="flex items-center gap-2 text-sm font-semibold"><LoaderCircle className="animate-spin text-accent" size={16} />{compileJobId ? 'Creating PDF' : 'Preparing content'}</p>
                <p className="mt-1 text-xs text-muted">{compileJobId ? 'Typesetting the assembled resume.' : 'Turning your approved wording into resume source.'}</p>
              </div>
            ) : (
              <>
                <button className="button-primary" type="button" disabled={assemble.isPending} onClick={() => assemble.mutate()}>
                  {assemble.isPending ? <LoaderCircle className="animate-spin" size={16} /> : <FileText size={16} />}
                  Generate resume
                </button>
                <p className="mt-2 text-xs text-muted">We’ll prepare your approved content and create an editable PDF.</p>
              </>
            )}
            {assemblyJob.data?.status === 'failed' || assemble.isError || compile.isError ? (
              <div className="mt-4" role="alert">
                <p className="text-sm font-medium text-danger">{assemblyJob.data?.error ?? assemble.error?.message ?? compile.error?.message ?? 'Resume generation could not start.'}</p>
                <button className="button-secondary mt-3" type="button" onClick={() => { setAssemblyJobId(undefined); setCompileJobId(undefined); assemble.reset(); compile.reset() }}>Try again</button>
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      {!finalized ? (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b pb-5">
            <p className="text-sm text-muted"><strong className="text-ink">{bullets.data.length - unresolved.length} of {bullets.data.length}</strong> bullets resolved</p>
            <button className="button-secondary" type="button" disabled={!bulkEligible.length || busy || editing.size > 0} onClick={() => approveAll.mutate(bulkEligible)}>
              {approveAll.isPending ? <LoaderCircle className="animate-spin" size={16} /> : <Check size={16} />}
              Approve all unflagged ({bulkEligible.length})
            </button>
        </div>
      ) : null}

      <div className={finalized ? 'mt-8' : ''}>
        {bullets.data.map(bullet => <RewriteBulletCard key={bullet.id} bullet={bullet} busy={busy} readOnly={finalized} onUpdate={async (id, payload) => { await update.mutateAsync({ id, payload }) }} onEditingChange={(id, active) => setEditing(current => { const next = new Set(current); if (active) next.add(id); else next.delete(id); return next })} />)}
      </div>

      {!finalized ? <>
          {error ? <p className="mt-6 text-sm font-medium text-danger" role="alert">{error.message}</p> : null}
          <div className="mt-10 flex flex-col items-end gap-2 border-t pt-6">
            <button className="button-primary" type="button" disabled={unresolved.length > 0 || editing.size > 0 || busy} onClick={() => finalize.mutate()}>
              {finalize.isPending ? <LoaderCircle className="animate-spin" size={16} /> : <ShieldCheck size={16} />}
              Finalize reviewed bullets
            </button>
            {unresolved.length ? <p className="text-sm text-muted">Resolve {unresolved.length} remaining {unresolved.length === 1 ? 'bullet' : 'bullets'} before finalizing.</p> : null}
            {!unresolved.length && editing.size ? <p className="text-sm text-muted">Save or cancel the open edit before finalizing.</p> : null}
          </div>
      </> : null}
    </div>
  )
}
