"use client"

import { useQuery } from '@tanstack/react-query'
import { Plus, Settings2, FileText, Briefcase, FileUp } from 'lucide-react'
import Link from 'next/link'
import { PageHeader } from '@/components/PageHeader'
import { ScreenState } from '@/components/ScreenState'
import { useApi } from '@/hooks/useApi'
import { Reveal } from '@/components/motion/Reveal'
import { Stagger, StaggerItem } from '@/components/motion/Stagger'

export default function Dashboard() {
  const api = useApi()

  const { data: llmSettings } = useQuery({
    queryKey: ['llm-settings'],
    queryFn: api.llmSettings.get,
    retry: false,
  })

  const { data: skillBank, isLoading: skillBankLoading } = useQuery({
    queryKey: ['skill-bank'],
    queryFn: () => api.skillBank.list(),
  })

  const { data: jobDescriptions, isLoading: jdLoading } = useQuery({
    queryKey: ['job-descriptions'],
    queryFn: () => api.jd.list(),
  })

  const loading = skillBankLoading || jdLoading
  const hasItems = (skillBank?.length ?? 0) > 0 || (jobDescriptions?.length ?? 0) > 0

  return (
    <div className="container-normal py-10 md:py-12">
      <PageHeader
        eyebrow="Workspace"
        title="Dashboard"
        description="Your unified career evidence and tailored resumes."
      />

      <Reveal variant="up" className="mb-12">
        <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-4">
          <StatCard
            icon={FileText}
            label="Skill bank items"
            value={skillBank?.length ?? 0}
            link="/skill-bank"
          />
          <StatCard
            icon={Briefcase}
            label="Job descriptions"
            value={jobDescriptions?.length ?? 0}
            link="/job-description"
          />
          <StatCard
            icon={FileUp}
            label="Resume imports"
            value={0} // To be implemented when backend supports listing imports on dashboard
            link="/resume-import"
          />
          <StatCard
            icon={Settings2}
            label="AI setup"
            value={llmSettings ? 'Configured' : 'Missing'}
            link="/settings"
            alert={!llmSettings}
          />
        </div>
      </Reveal>

      {loading ? (
        <ScreenState kind="loading" title="Loading workspace" detail="Fetching your data…" />
      ) : hasItems ? (
        <Stagger className="grid gap-10 md:grid-cols-2" staggerDelay={0.1}>
          <StaggerItem as="section" className="min-w-0">
            <div className="mb-4 flex items-end justify-between">
              <h2 className="section-title text-xl">Recent Evidence</h2>
              <Link className="button-ghost" href="/skill-bank">View all</Link>
            </div>
            {skillBank?.length ? (
              <ul className="grid gap-3">
                {skillBank.slice(0, 5).map((item) => (
                  <li key={item.id} className="min-w-0">
                    <Link
                      href="/skill-bank"
                      className="group block rounded-lg border bg-surface p-4 transition-all hover:border-accent hover:bg-raised"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <p className="truncate font-semibold text-ink group-hover:text-accent transition-colors">
                            {item.title}
                          </p>
                          <p className="mt-1 truncate text-xs text-muted">
                            {item.type.charAt(0).toUpperCase() + item.type.slice(1)} • {item.org ?? 'Personal'}
                          </p>
                        </div>
                        <span className="shrink-0 text-xs font-mono text-muted">
                          {new Date(item.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="rounded-lg border border-dashed p-8 text-center bg-surface/50">
                <p className="text-sm font-semibold">No evidence yet</p>
                <Link className="button-secondary mt-4" href="/skill-bank">
                  <Plus size={16} /> Add item
                </Link>
              </div>
            )}
          </StaggerItem>

          <StaggerItem as="section" className="min-w-0">
            <div className="mb-4 flex items-end justify-between">
              <h2 className="section-title text-xl">Recent Roles</h2>
              <Link className="button-ghost" href="/job-description">View all</Link>
            </div>
            {jobDescriptions?.filter(jd => jd.status !== 'failed').length ? (
              <ul className="grid gap-3">
                {jobDescriptions.filter(jd => jd.status !== 'failed').slice(0, 5).map((jd) => (
                  <li key={jd.id} className="min-w-0">
                    <Link
                      href={`/job-description?jd=${jd.id}#parsed`}
                      className="group block rounded-lg border bg-surface p-4 transition-all hover:border-accent hover:bg-raised"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <p className="line-clamp-2 text-sm leading-relaxed text-muted group-hover:text-ink transition-colors">
                            {jd.excerpt}
                          </p>
                        </div>
                        <span className="shrink-0 rounded bg-raised px-2 py-1 font-mono text-[10px] uppercase text-muted group-hover:bg-accent-soft group-hover:text-accent transition-colors">
                          {jd.status}
                        </span>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="rounded-lg border border-dashed p-8 text-center bg-surface/50">
                <p className="text-sm font-semibold">No parsed JDs</p>
                <Link className="button-secondary mt-4" href="/job-description">
                  <Plus size={16} /> Parse JD
                </Link>
              </div>
            )}
          </StaggerItem>
        </Stagger>
      ) : (
        <ScreenState
          kind="empty"
          title="Your workspace is ready"
          detail="Start by importing your existing resume or adding items to your skill bank."
        />
      )}
    </div>
  )
}

function StatCard({
  icon: Icon,
  label,
  value,
  link,
  alert,
}: {
  icon: any
  label: string
  value: string | number
  link: string
  alert?: boolean
}) {
  return (
    <Link
      href={link}
      className={`group flex flex-col justify-between rounded-xl border bg-surface p-5 transition-all hover:border-accent hover:bg-raised hover:shadow-sm ${
        alert ? 'border-warning/30 bg-warning/5' : ''
      }`}
    >
      <div className="flex items-start justify-between">
        <span
          className={`grid size-10 place-items-center rounded-lg transition-colors ${
            alert
              ? 'bg-warning/20 text-warning group-hover:bg-warning group-hover:text-white'
              : 'bg-raised text-muted group-hover:bg-accent-soft group-hover:text-accent'
          }`}
        >
          <Icon size={18} />
        </span>
      </div>
      <div className="mt-6">
        <p className="text-sm font-semibold text-muted transition-colors group-hover:text-ink">
          {label}
        </p>
        <p className={`mt-1 font-display text-2xl font-medium tracking-tight ${alert ? 'text-warning' : 'text-ink'}`}>
          {value}
        </p>
      </div>
    </Link>
  )
}
