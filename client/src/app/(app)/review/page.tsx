"use client"

import { useMutation, useQuery } from '@tanstack/react-query'
import { ArrowLeft, Clock3, Link2, CheckCircle2, LoaderCircle, WandSparkles } from 'lucide-react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { useEffect, useRef, useState } from 'react'
import { PageHeader } from '@/components/PageHeader'
import { ScreenState } from '@/components/ScreenState'
import { useApi } from '@/hooks/useApi'
import { matchSelection, orderedSelections, selectionKey } from '@/lib/task4'
import type { MatchedBullet, MatchedItem, RewriteSelection } from '@/lib/types'

const date = new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short' })
const formatDate = (value: string | null) => value ? date.format(new Date(`${value}T00:00:00`)) : 'Present'

export default function MatchReview() {
  const api = useApi()
  const router = useRouter()
  const params = useSearchParams()
  const jdId = params.get('jd')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const initializedFrom = useRef<string | null>(null)
  const match = useQuery({
    queryKey: ['match', jdId],
    queryFn: () => api.match(jdId!),
    enabled: !!jdId,
    retry: false,
  })
  const result = match.data
  const matchData = result?.jd_id === jdId && Array.isArray(result.items) && Array.isArray(result.requirements)
    ? result
    : null

  useEffect(() => {
    if (matchData && initializedFrom.current !== jdId) {
      setSelected(new Set(orderedSelections(matchData.items).map(selectionKey)))
      initializedFrom.current = jdId
    }
  }, [jdId, matchData])

  const startRewrite = useMutation({
    mutationFn: async () => {
      if (!matchData) throw new Error('Match results are not ready.')
      const version = await api.resumeVersions.create(jdId!)
      return api.resumeVersions.rewrite(version.id, orderedSelections(matchData.items, selected))
    },
    onSuccess: queued => router.push(`/rewrite?version=${queued.resume_version_id}&job=${queued.background_job_id}&jd=${jdId}`),
  })

  function toggleSelection(selection: RewriteSelection) {
    const key = selectionKey(selection)
    setSelected(current => {
      const next = new Set(current)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  if (!jdId) {
    return (
      <div className="container-normal py-10 md:py-12">
        <ScreenState kind="empty" title="Choose a job description first" detail="Open a parsed job description, then start matching from its detail view." />
        <div className="mt-6 flex justify-center">
          <Link className="button-primary" href="/job-description">Open Job Descriptions</Link>
        </div>
      </div>
    )
  }

  const matching = match.isPending
  const failure = match.error?.message
    ?? (match.data && !matchData ? 'The matching API returned an invalid result.' : null)

  if (matching) {
    return (
      <div className="container-normal py-10 md:py-12">
        <ScreenState kind="loading" title="Matching your evidence…" detail="Comparing each job requirement with your saved proof points." />
      </div>
    )
  }

  if (failure) {
    return (
      <div className="container-normal py-10 md:py-12">
        <ScreenState
          kind="error"
          title="Match unavailable"
          detail={failure}
          onRetry={() => void match.refetch()}
        />
      </div>
    )
  }

  if (!matchData) return null

  const count = matchData.items.reduce((total, item) => total + item.bullets.length, 0)
  const selectableCount = count
  const selectedSelections = orderedSelections(matchData.items, selected)
  const selectedBulletCount = selectedSelections.filter(selection => selection.kind === 'bullet').length
  const unmatched = matchData.requirements.filter(requirement => requirement.no_match)
  
  return (
    <div className="container-normal pt-10 pb-28 md:pt-12 md:pb-32">
      <PageHeader
        eyebrow="Evidence fit"
        title="Match & Review"
        description="See which saved proof points best support this role and why. Nothing is rewritten or added to a resume here."
        action={
          <Link className="button-secondary" href={`/job-description?jd=${jdId}`}>
            <ArrowLeft size={16} aria-hidden="true" /> Back to JD
          </Link>
        }
      />

      <>
        {matchData.pending_embeddings ? (
          <div className="mb-10 flex items-start gap-4 rounded-xl border border-warning/30 bg-warning/5 px-6 py-5 shadow-sm" role="status" aria-live="polite">
            <Clock3 className="mt-0.5 shrink-0 text-warning" size={20} aria-hidden="true" />
            <div>
              <p className="font-semibold text-warning-dark">Still processing your skill bank</p>
              <p className="mt-1 text-sm leading-relaxed text-muted max-w-2xl">Some proof points do not have embeddings yet, so this match may be incomplete. Try again shortly.</p>
              <button className="mt-4 text-sm font-semibold text-warning-dark underline underline-offset-4 hover:text-warning" onClick={() => void match.refetch()}>
                Check again
              </button>
            </div>
          </div>
        ) : null}

        {count ? (
          <div className="rounded-xl border bg-surface shadow-sm">
            <div className="flex flex-col gap-4 border-b bg-raised/50 px-6 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-8">
              <div>
                <p className="eyebrow !mb-1 !text-accent">Evidence ledger</p>
                <p className="text-sm text-muted">
                  <strong className="text-ink font-medium">{count} proof {count === 1 ? 'point' : 'points'}</strong> across {matchData.items.length} sources
                </p>
              </div>
              <p className="hidden max-w-xs text-right text-xs leading-relaxed text-muted sm:block">
                Confidence uses fixed relevance thresholds, not relative ranking.
              </p>
            </div>
            
            <div className="divide-y">
              {matchData.items.map((item, index) => (
                <MatchedSource key={item.id} item={item} index={index} selected={selected} onToggle={toggleSelection} />
              ))}
            </div>
          </div>
        ) : (
          <div className="grid min-h-[400px] place-items-center rounded-xl border border-dashed text-center bg-raised/30">
            <div className="max-w-md px-6">
              <div className="mx-auto mb-5 grid size-12 place-items-center rounded-full bg-canvas border shadow-sm">
                <Link2 size={20} className="text-muted" />
              </div>
              <p className="font-display text-2xl font-medium">No matching proof points yet</p>
              <p className="mt-3 text-sm leading-relaxed text-muted">No saved proof point cleared the relevance threshold for this role.</p>
              <Link className="button-secondary mt-6" href="/skill-bank">Open Skill Bank</Link>
            </div>
          </div>
        )}

        {unmatched.length ? (
          <section className="mt-8 rounded-xl border bg-raised/40 px-6 py-5 sm:px-8" aria-labelledby="unmatched-requirements">
            <h2 id="unmatched-requirements" className="font-display text-xl font-medium">No strong match found</h2>
            <p className="mt-1 text-sm text-muted">These requirements had no qualifying Skill Bank evidence.</p>
            <ul className="mt-4 flex flex-wrap gap-2">
              {unmatched.map(requirement => (
                <li className="tag" key={requirement.id}>{requirement.text}</li>
              ))}
            </ul>
          </section>
        ) : null}

      </>

      {selectableCount ? (
        <div className="fixed inset-x-0 bottom-0 z-30 border-t bg-surface/95 shadow-lg backdrop-blur-sm">
          <div className="container-normal flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm text-muted" aria-live="polite">
                <strong className="text-ink">{selectedSelections.length} selected</strong> for a new, reviewable resume draft
              </p>
              {startRewrite.isError ? <p className="mt-1 text-sm font-medium text-danger" role="alert">{startRewrite.error.message}</p> : null}
            </div>
            <button
              type="button"
              className="button-primary"
              disabled={!selectedBulletCount || startRewrite.isPending}
              onClick={() => startRewrite.mutate()}
            >
              {startRewrite.isPending ? <LoaderCircle className="animate-spin" size={16} aria-hidden="true" /> : <WandSparkles size={16} aria-hidden="true" />}
              {startRewrite.isPending ? 'Starting rewrite…' : 'Rewrite selected bullets for this JD'}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}

function MatchedSource({ item, index, selected, onToggle }: { item: MatchedItem; index: number; selected: Set<string>; onToggle: (selection: RewriteSelection) => void }) {
  return (
    <article className="grid gap-6 p-6 sm:p-8 lg:grid-cols-[14rem_minmax(0,1fr)] lg:gap-10 transition-colors hover:bg-raised/30">
      <header className="lg:sticky lg:top-24 lg:self-start">
        <p className="font-mono text-[11px] font-bold tracking-wider text-accent">
          SOURCE {String(index + 1).padStart(2, '0')}
        </p>
        <h2 className="mt-3 font-display text-xl font-medium tracking-tight text-ink">{item.title}</h2>
        <p className="mt-2 text-sm text-muted">{item.org || 'Independent'}</p>
        {item.start_date && (
          <p className="mt-1 text-sm text-muted">
            {formatDate(item.start_date)} — {formatDate(item.end_date)}
          </p>
        )}
        <span className="tag mt-4">{item.type}</span>
      </header>
      
      <ol className="divide-y border-t lg:border-t-0 lg:border-l lg:pl-10">
        {item.bullets.map(bullet => {
          const selection = matchSelection(item, bullet)
          return (
          <MatchedEvidence
            key={selection ? selectionKey(selection) : `evidence:${item.id}`}
            bullet={bullet}
            selected={selection ? selected.has(selectionKey(selection)) : false}
            onToggle={selection ? () => onToggle(selection) : undefined}
          />
          )
        })}
      </ol>
    </article>
  )
}

function MatchedEvidence({ bullet, selected, onToggle }: { bullet: MatchedBullet; selected: boolean; onToggle?: () => void }) {
  const strong = bullet.confidence === 'strong'
  
  return (
    <li className="grid gap-4 py-6 sm:grid-cols-[2.5rem_minmax(0,1fr)] first:pt-4 lg:first:pt-0 last:pb-0">
      {onToggle ? <label className="flex min-h-11 min-w-11 cursor-pointer items-start justify-center pt-1" aria-label={`Select ${bullet.skill_bank_item_id ? 'skill' : 'proof point'}: ${bullet.text}`}>
          <input className="mt-0.5 size-4 accent-accent" type="checkbox" checked={selected} onChange={onToggle} />
          <span className="sr-only">Select {bullet.skill_bank_item_id ? 'skill' : 'proof point'}: {bullet.text}</span>
        </label> : <span aria-hidden="true" />}
      <div>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider ${
            strong ? 'bg-success/10 text-success' : 'bg-accent/10 text-accent'
          }`}>
            {strong && <CheckCircle2 size={12} />}
            {strong ? 'Strong match' : 'Moderate match'}
          </span>
          {bullet.skill_bank_item_id ? <span className="tag">Skill entry</span> : null}
          {bullet.recommended ? <span className="tag !border-accent/40 bg-accent-soft text-ink">Recommended</span> : null}
        </div>
        
        <p className="leading-relaxed text-ink/90">{bullet.text}</p>
        
        <div className="mt-5 rounded-lg border border-line-soft bg-canvas p-4 shadow-sm">
          <p className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-muted">
            <Link2 size={13} aria-hidden="true" /> Matched requirements
          </p>
          <ul className="space-y-2">
            {bullet.requirements.slice(0, 3).map(requirement => (
              <li className="text-sm leading-relaxed text-muted before:content-['—'] before:mr-2 before:text-muted/50" key={requirement.id}>
                {requirement.text}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </li>
  )
}
