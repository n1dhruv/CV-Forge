"use client"

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, FileText, LoaderCircle, ChevronDown, ChevronUp } from 'lucide-react'
import Link from 'next/link'
import { PageHeader } from '@/components/PageHeader'
import { ScreenState } from '@/components/ScreenState'
import { useApi } from '@/hooks/useApi'
import type { ResumeMetadataUpdate, ResumeFamily } from '@/lib/types'

function ResumeFamilyCard({ family, rename, save }: { family: ResumeFamily, rename: any, save: any }) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <section className="rounded-xl border bg-surface overflow-hidden shadow-sm transition-all" aria-labelledby={`family-${family.id}`}>
      <div className="flex flex-wrap items-center justify-between gap-3 p-4 sm:p-5">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <button 
            type="button"
            onClick={() => setIsOpen(!isOpen)}
            className="grid size-8 place-items-center rounded-md hover:bg-raised text-muted hover:text-ink transition-colors shrink-0"
            aria-expanded={isOpen}
            aria-label={isOpen ? "Collapse" : "Expand"}
          >
            {isOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </button>
          <input 
            id={`family-${family.id}`} 
            className="field !min-h-10 max-w-md text-base font-semibold bg-transparent hover:bg-raised focus:bg-raised border-transparent hover:border-line focus:border-accent !px-2 transition-all -ml-2" 
            defaultValue={family.name} 
            maxLength={120} 
            aria-label="Resume name" 
            onBlur={event => save(family.id, 'name', event.target.value, family.name)} 
            onKeyDown={event => { if (event.key === 'Enter') event.currentTarget.blur() }} 
          />
          {rename.isPending ? <span className="flex items-center gap-2 text-xs text-muted shrink-0"><LoaderCircle className="animate-spin" size={14} /> Saving…</span> : null}
        </div>
        <div className="text-sm text-muted hidden sm:block shrink-0">
          {family.versions.length} version{family.versions.length === 1 ? '' : 's'}
        </div>
      </div>
      
      {isOpen && (
        <div className="border-t bg-canvas/50">
          <ul className="divide-y">
            {family.versions.map(version => (
              <li key={version.id} className="flex flex-col gap-3 p-4 sm:p-5 sm:flex-row sm:items-center hover:bg-surface/50 transition-colors">
                <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-surface text-muted border shadow-sm"><FileText size={18} /></span>
                <div className="min-w-0 flex-1">
                  <input 
                    className="field !min-h-9 max-w-sm !px-2 font-medium bg-transparent hover:bg-raised focus:bg-raised border-transparent hover:border-line focus:border-accent transition-all -ml-2" 
                    defaultValue={version.version_label} 
                    maxLength={80} 
                    aria-label={`Version label for ${family.name}`} 
                    onBlur={event => save(version.id, 'version_label', event.target.value, version.version_label)} 
                    onKeyDown={event => { if (event.key === 'Enter') event.currentTarget.blur() }} 
                  />
                  <p className="mt-1 text-xs text-muted flex items-center gap-2">
                    <span>{new Date(version.created_at).toLocaleString()}</span>
                    <span>·</span>
                    <span className="capitalize">{version.status.replace('_', ' ')}</span>
                    {version.has_pdf ? <span className="inline-flex items-center gap-1 text-success bg-success/10 px-1.5 py-0.5 rounded-sm"><Check size={12} /> PDF ready</span> : null}
                  </p>
                </div>
                <Link className="button-secondary shrink-0" href={`/resume-versions/${version.id}/editor?from=resumes`}>Open</Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

export default function ResumesPage() {
  const api = useApi()
  const queryClient = useQueryClient()
  const families = useQuery({ queryKey: ['resume-families'], queryFn: api.resumeVersions.list })
  const rename = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ResumeMetadataUpdate }) => api.resumeVersions.updateMetadata(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['resume-families'] }),
  })

  const save = (id: string, field: 'name' | 'version_label', value: string, original: string) => {
    const trimmed = value.trim()
    if (trimmed && trimmed !== original) rename.mutate({ id, payload: { [field]: trimmed } })
  }

  if (families.isPending) return <div className="container-normal py-12"><ScreenState kind="loading" title="Opening your resumes…" detail="Loading saved resume families and versions." /></div>
  if (families.isError) return <div className="container-normal py-12"><ScreenState kind="error" title="Resumes unavailable" detail={families.error.message} onRetry={() => void families.refetch()} /></div>

  return (
    <div className="container-normal py-10 md:py-12">
      <PageHeader eyebrow="Resume library" title="Your resumes" description="Open any saved version directly. Family names and version labels stay editable." />
      {!families.data.length ? <ScreenState kind="empty" title="No resumes yet" detail="Generate a resume from a completed rewrite and it will appear here." /> : null}
      <div className="space-y-6">
        {families.data.map(family => (
          <ResumeFamilyCard key={family.id} family={family} rename={rename} save={save} />
        ))}
      </div>
      {rename.isError ? <p className="mt-5 text-sm text-danger" role="alert">{rename.error.message} Your typed name was kept; try again.</p> : null}
    </div>
  )
}
