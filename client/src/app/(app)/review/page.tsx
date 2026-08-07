"use client"

import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Clock3, Link2, CheckCircle2 } from 'lucide-react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { motion } from 'framer-motion'
import { PageHeader } from '@/components/PageHeader'
import { ScreenState } from '@/components/ScreenState'
import { useApi } from '@/hooks/useApi'
import { Reveal } from '@/components/motion/Reveal'
import { Stagger, StaggerItem } from '@/components/motion/Stagger'
import type { MatchedBullet, MatchedItem } from '@/lib/types'

const date = new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short' })
const formatDate = (value: string | null) => value ? date.format(new Date(`${value}T00:00:00`)) : 'Present'

export default function MatchReview() {
  const api = useApi()
  const params = useSearchParams()
  const jdId = params.get('jd')
  const match = useQuery({
    queryKey: ['match', jdId],
    queryFn: () => api.match(jdId!),
    enabled: !!jdId,
    refetchOnWindowFocus: false,
  })

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

  if (match.isPending) {
    return (
      <div className="container-normal py-10 md:py-12">
        <ScreenState kind="loading" title="Matching your evidence…" detail="Comparing each job requirement with your saved proof points." />
      </div>
    )
  }

  if (match.isError) {
    return (
      <div className="container-normal py-10 md:py-12">
        <ScreenState kind="error" title="Match unavailable" detail={match.error.message} onRetry={() => void match.refetch()} />
      </div>
    )
  }

  const count = match.data.items.reduce((total, item) => total + item.bullets.length, 0)
  
  return (
    <div className="container-normal py-10 pb-24 md:py-12">
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

      <Reveal delay={0.1}>
        {match.data.pending_embeddings ? (
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
                  <strong className="text-ink font-medium">{count} proof {count === 1 ? 'point' : 'points'}</strong> across {match.data.items.length} sources
                </p>
              </div>
              <p className="hidden max-w-xs text-right text-xs leading-relaxed text-muted sm:block">
                Labels summarize relative fit; raw vector scores stay out of the way.
              </p>
            </div>
            
            <div className="divide-y">
              <Stagger staggerDelay={0.05}>
                {match.data.items.map((item, index) => (
                  <StaggerItem key={item.id}>
                    <MatchedSource item={item} index={index} />
                  </StaggerItem>
                ))}
              </Stagger>
            </div>
          </div>
        ) : (
          <div className="grid min-h-[400px] place-items-center rounded-xl border border-dashed text-center bg-raised/30">
            <div className="max-w-md px-6">
              <div className="mx-auto mb-5 grid size-12 place-items-center rounded-full bg-canvas border shadow-sm">
                <Link2 size={20} className="text-muted" />
              </div>
              <p className="font-display text-2xl font-medium">No matching proof points yet</p>
              <p className="mt-3 text-sm leading-relaxed text-muted">Add bullets to your Skill Bank, or wait for new embeddings to finish processing.</p>
              <Link className="button-secondary mt-6" href="/skill-bank">Open Skill Bank</Link>
            </div>
          </div>
        )}
      </Reveal>
    </div>
  )
}

function MatchedSource({ item, index }: { item: MatchedItem; index: number }) {
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
        {item.bullets.map((bullet, bulletIndex) => (
          <MatchedEvidence key={bullet.id} bullet={bullet} index={bulletIndex} />
        ))}
      </ol>
    </article>
  )
}

function MatchedEvidence({ bullet, index }: { bullet: MatchedBullet; index: number }) {
  const strong = bullet.score >= .72
  
  return (
    <li className="grid gap-4 py-6 sm:grid-cols-[2.5rem_minmax(0,1fr)] first:pt-4 lg:first:pt-0 last:pb-0">
      <span className="font-mono text-xs font-medium text-muted/70" aria-hidden="true">
        {String(index + 1).padStart(2, '0')}
      </span>
      <div>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider ${
            strong ? 'bg-success/10 text-success' : 'bg-accent/10 text-accent'
          }`}>
            {strong && <CheckCircle2 size={12} />}
            {strong ? 'Strong match' : 'Good match'}
          </span>
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
