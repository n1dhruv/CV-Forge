"use client"

import { ArrowRight, Check, X, Info } from 'lucide-react'
import Link from 'next/link'
import { PageHeader } from '@/components/PageHeader'
import { Reveal } from '@/components/motion/Reveal'
import { jd } from '@/lib/demo'

export default function ATSScore() {
  const matched = jd.atsKeywords.slice(0, 6)
  const missing = jd.atsKeywords.slice(6)

  return (
    <div className="container-normal py-10 pb-24 md:py-12">
      <PageHeader 
        eyebrow="Version v4 · Fathom" 
        title="ATS coverage" 
        description="Keyword coverage is tied to this exact resume version, not your full skill bank." 
        action={
          <Link className="button-secondary" href="/editor">
            Open version <ArrowRight size={16} />
          </Link>
        }
      />

      <Reveal delay={0.1}>
        <div className="grid gap-12 lg:grid-cols-[20rem_minmax(0,1fr)] lg:gap-16">
          <aside className="lg:sticky lg:top-24 lg:self-start">
            <div className="rounded-xl border bg-surface p-8 text-center shadow-sm">
              <div 
                className="relative mx-auto grid aspect-square w-full max-w-48 place-items-center rounded-full" 
                style={{ background: 'conic-gradient(var(--accent) 0 86%, var(--line) 86% 100%)' }}
              >
                <div className="grid size-[82%] place-items-center rounded-full bg-surface shadow-sm text-center">
                  <div>
                    <p className="font-display text-6xl tracking-tight text-ink">86</p>
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-muted mt-1">Percent covered</p>
                  </div>
                </div>
              </div>
              <p className="mt-8 text-sm leading-relaxed text-muted">
                <strong className="text-ink font-medium">Strong alignment.</strong> One source keyword is not represented in the approved resume evidence.
              </p>
            </div>
            
            <div className="mt-6 flex items-start gap-3 rounded-lg border border-line-soft bg-canvas p-4 text-xs text-muted shadow-sm">
              <Info size={16} className="mt-0.5 shrink-0" />
              <p className="leading-relaxed">Coverage measures literal language alignment. Missing keywords should only be addressed when your skill bank contains truthful evidence.</p>
            </div>
          </aside>

          <section className="flex flex-col gap-8 lg:mt-2">
            <KeywordGroup title="Matched keywords" items={matched} matched />
            <KeywordGroup title="Missing keywords" items={missing} matched={false} />
          </section>
        </div>
      </Reveal>
    </div>
  )
}

function KeywordGroup({ title, items, matched }: { title: string; items: string[]; matched: boolean }) {
  return (
    <div className="rounded-xl border bg-surface p-6 sm:p-8 shadow-sm">
      <div className="mb-6 flex items-center justify-between border-b pb-4">
        <h2 className="font-display text-xl font-medium">{title}</h2>
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider ${
          matched ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'
        }`}>
          {items.length} {items.length === 1 ? 'Keyword' : 'Keywords'}
        </span>
      </div>
      
      <ul className="grid gap-3 sm:grid-cols-2">
        {items.map(x => (
          <li 
            className="flex items-center gap-3 rounded-lg border border-line-soft bg-canvas px-4 py-3 text-sm shadow-sm transition-colors hover:border-line" 
            key={x}
          >
            <div className={`grid size-6 shrink-0 place-items-center rounded-full ${
              matched ? 'bg-success/15 text-success' : 'bg-danger/15 text-danger'
            }`}>
              {matched ? <Check size={14} /> : <X size={14} />}
            </div>
            <span className="font-medium text-ink/90">{x}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
