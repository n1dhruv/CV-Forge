import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Clock3, Link2 } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { PageHeader } from '../components/PageHeader'
import { ScreenState } from '../components/ScreenState'
import { useApi } from '../hooks/useApi'
import type { MatchedBullet, MatchedItem } from '../lib/types'

const date = new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short' })
const formatDate = (value: string | null) => value ? date.format(new Date(`${value}T00:00:00`)) : 'Present'

export function MatchReview() {
  const api = useApi()
  const [params] = useSearchParams()
  const jdId = params.get('jd')
  const match = useQuery({
    queryKey: ['match', jdId],
    queryFn: () => api.match(jdId!),
    enabled: !!jdId,
    refetchOnWindowFocus: false,
  })

  if (!jdId) return <div className="px-5 py-8 md:px-10 xl:px-16"><ScreenState kind="empty" title="Choose a job description first" detail="Open a parsed job description, then start matching from its detail view."/><Link className="button-primary mt-6" to="/job-description">Open Job Descriptions</Link></div>
  if (match.isPending) return <div className="px-5 py-8 md:px-10 xl:px-16"><ScreenState kind="loading" title="Matching your evidence…" detail="Comparing each job requirement with your saved proof points."/></div>
  if (match.isError) return <div className="px-5 py-8 md:px-10 xl:px-16"><ScreenState kind="error" title="Match unavailable" detail={match.error.message} onRetry={() => void match.refetch()}/></div>

  const count = match.data.items.reduce((total, item) => total + item.bullets.length, 0)
  return <div className="page-enter px-5 py-8 pb-20 md:px-10 md:py-12 xl:px-16">
    <PageHeader eyebrow="Evidence fit" title="Match & Review" description="See which saved proof points best support this role and why. Nothing is rewritten or added to a resume here." action={<Link className="button-secondary" to={`/job-description?jd=${jdId}`}><ArrowLeft size={16} aria-hidden="true"/>Back to JD</Link>}/>

    {match.data.pending_embeddings ? <div className="mb-8 flex items-start gap-3 border-l-2 border-warning bg-surface px-5 py-4" role="status" aria-live="polite"><Clock3 className="mt-0.5 shrink-0 text-warning" size={18} aria-hidden="true"/><div><p className="font-semibold">Still processing your skill bank</p><p className="mt-1 text-sm text-muted">Some proof points do not have embeddings yet, so this match may be incomplete. Try again shortly.</p><button className="mt-3 text-sm font-semibold text-accent underline underline-offset-4" onClick={() => void match.refetch()}>Check again</button></div></div> : null}

    {count ? <><div className="mb-7 flex items-end justify-between gap-4 border-b pb-4"><div><p className="eyebrow">Evidence ledger</p><p className="mt-1 text-sm text-muted">{count} proof {count === 1 ? 'point' : 'points'} across {match.data.items.length} sources</p></div><p className="hidden max-w-sm text-right text-xs text-muted sm:block">Labels summarize relative fit; raw vector scores stay out of the way.</p></div><div className="space-y-10">{match.data.items.map((item, index) => <MatchedSource key={item.id} item={item} index={index}/>)}</div></> : <div className="grid min-h-72 place-items-center border-y text-center"><div className="max-w-md"><p className="font-display text-3xl">No matching proof points yet.</p><p className="mt-2 text-sm text-muted">Add bullets to your Skill Bank, or wait for new embeddings to finish processing.</p><Link className="button-secondary mt-5" to="/skill-bank">Open Skill Bank</Link></div></div>}
  </div>
}

function MatchedSource({ item, index }: { item: MatchedItem; index: number }) {
  return <article className="grid gap-5 lg:grid-cols-[12rem_minmax(0,1fr)]">
    <header className="lg:sticky lg:top-8 lg:self-start"><p className="font-mono text-xs text-accent">SOURCE {String(index + 1).padStart(2, '0')}</p><h2 className="mt-2 section-title">{item.title}</h2><p className="mt-1 text-sm text-muted">{item.org || 'Independent'}{item.start_date ? ` · ${formatDate(item.start_date)}—${formatDate(item.end_date)}` : ''}</p><p className="mt-3 text-xs font-semibold uppercase tracking-[.14em] text-muted">{item.type}</p></header>
    <ol className="divide-y border-y">{item.bullets.map((bullet, bulletIndex) => <MatchedEvidence key={bullet.id} bullet={bullet} index={bulletIndex}/>)}</ol>
  </article>
}

function MatchedEvidence({ bullet, index }: { bullet: MatchedBullet; index: number }) {
  const strong = bullet.score >= .72
  return <li className="grid gap-4 py-6 sm:grid-cols-[2.5rem_minmax(0,1fr)]"><span className="font-mono text-xs text-muted" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span><div><div className="mb-3 flex flex-wrap items-center gap-2"><span className={`border-l-2 px-2 py-0.5 text-xs font-semibold ${strong ? 'border-success text-success' : 'border-accent text-accent'}`}>{strong ? 'Strong match' : 'Good match'}</span></div><p className="leading-7">{bullet.text}</p><div className="mt-4 border-l pl-4"><p className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[.12em] text-muted"><Link2 size={13} aria-hidden="true"/>Matched requirements</p><ul className="space-y-1.5">{bullet.requirements.slice(0, 3).map(requirement => <li className="text-sm text-muted" key={requirement.id}>{requirement.text}</li>)}</ul></div></div></li>
}
