"use client"

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, FileUp, LoaderCircle, Trash2, X, AlertCircle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { PageHeader } from '@/components/PageHeader'
import { ScreenState } from '@/components/ScreenState'
import { useApi } from '@/hooks/useApi'
import { useBackgroundJobStatus } from '@/hooks/useBackgroundJobStatus'
import { Reveal } from '@/components/motion/Reveal'
import { Stagger, StaggerItem } from '@/components/motion/Stagger'
import { motion } from 'framer-motion'
import type { ResumeImportCommit, ResumeImportItem, ResumeImportQueued } from '@/lib/types'

type ReviewItem = ResumeImportItem & { key: string; included: boolean }
type ReviewSkill = { name: string; included: boolean }
const accepted = new Set(['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'])

export default function ResumeImport() {
  const api = useApi()
  const navigate = useRouter()
  const queryClient = useQueryClient()
  const initialized = useRef<string | null>(null)
  const commitLock = useRef(false)
  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState('')
  const [queued, setQueued] = useState<ResumeImportQueued | null>(null)
  const [items, setItems] = useState<ReviewItem[]>([])
  const [skills, setSkills] = useState<ReviewSkill[]>([])

  const submit = useMutation({
    mutationFn: () => api.resumeImports.create(file!),
    onSuccess: result => { setQueued(result); initialized.current = null },
  })
  const job = useBackgroundJobStatus(queued?.background_job_id)
  const detail = useQuery({
    queryKey: ['resume-import', queued?.resume_import_id],
    queryFn: () => api.resumeImports.get(queued!.resume_import_id),
    enabled: !!queued && job.data?.status === 'done',
  })

  useEffect(() => {
    const parsed = detail.data?.parsed_json
    if (!parsed || initialized.current === detail.data?.id) return
    initialized.current = detail.data!.id
    setItems(parsed.items.map((item, index) => ({ ...item, key: `${detail.data!.id}-${index}`, included: true })))
    setSkills(parsed.skills.map(name => ({ name, included: true })))
  }, [detail.data])

  const commit = useMutation({
    mutationFn: (payload: ResumeImportCommit) => api.resumeImports.commit(queued!.resume_import_id, payload),
    onSuccess: async (result, payload) => {
      await queryClient.invalidateQueries({ queryKey: ['skill-bank'] })
      navigate.replace(payload.items.length ? `/skill-bank?importedCount=${result.items.length}` : `/skill-bank?type=skill&importedCount=${result.items.length}`)
    },
    onSettled: () => { commitLock.current = false },
  })

  function chooseFile(next: File | null) {
    setFileError('')
    if (!next) { setFile(null); return }
    const extension = next.name.toLowerCase().split('.').pop()
    if (!accepted.has(next.type) || (extension !== 'pdf' && extension !== 'docx')) {
      setFile(null)
      setFileError('Choose a PDF or DOCX file. Other file types cannot be imported.')
      return
    }
    if (next.size > 10 * 1024 * 1024) {
      setFile(null)
      setFileError('Choose a file smaller than 10 MB.')
      return
    }
    setFile(next)
  }

  function updateItem(key: string, change: Partial<ReviewItem>) {
    setItems(current => current.map(item => item.key === key ? { ...item, ...change } : item))
  }

  function commitSelected() {
    if (commitLock.current) return
    const selectedItems = items.filter(item => item.included).map(item => ({ type: item.type, title: item.title.trim(), org: item.org?.trim() || null, start_date: item.start_date, end_date: item.end_date, bullets: item.bullets.map(bullet => bullet.trim()) }))
    commitLock.current = true
    commit.mutate({ items: selectedItems, skills: selectedSkills })
  }

  const selectedItems = items.filter(item => item.included)
  const selectedSkills = skills.filter(skill => skill.included).map(skill => skill.name)
  const invalid = selectedItems.some(item => !item.title.trim() || item.bullets.some(bullet => !bullet.trim()))
  const running = !!queued && (job.isPending || job.data?.status === 'queued' || job.data?.status === 'running')
  const failure = job.data?.status === 'failed' ? job.data.error || 'The import worker could not finish this resume.' : null

  return (
    <div className="container-normal py-10 pb-32 md:py-12">
      <PageHeader 
        eyebrow="Existing evidence" 
        title="Import from Resume" 
        description="Upload a source resume, review every extracted line, then choose exactly what enters your Skill Bank."
      />

      <Reveal delay={0.1}>
        {!queued ? (
          <section className="w-full max-w-4xl mx-auto" aria-labelledby="resume-source-title">
            <h2 id="resume-source-title" className="sr-only">Resume file</h2>
            
            <div className="rounded-xl border bg-surface shadow-sm overflow-hidden">
              <div className="p-6 sm:p-8">
                <label
                  className={`relative flex min-h-[16rem] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed transition-all ${
                    file ? 'border-accent bg-accent-soft/50' : 'border-line hover:border-accent/50 hover:bg-raised'
                  }`}
                  htmlFor="resume-file"
                >
                  <input 
                    id="resume-file" 
                    name="resume-file" 
                    type="file" 
                    accept="application/pdf,.pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.docx" 
                    className="sr-only" 
                    onChange={event => chooseFile(event.target.files?.[0] ?? null)}
                  />
                  
                  {file ? (
                    <div className="text-center px-4">
                      <div className="mx-auto mb-4 grid size-12 place-items-center rounded-full bg-accent text-white shadow-md">
                        <Check size={24} />
                      </div>
                      <span className="block font-semibold text-ink break-all">{file.name}</span>
                      <span className="mt-2 block text-sm text-muted">{(file.size / (1024 * 1024)).toFixed(2)} MB • Click to change</span>
                    </div>
                  ) : (
                    <div className="text-center px-6">
                      <FileUp className="mx-auto mb-4 text-muted" size={32} aria-hidden="true" />
                      <span className="block font-semibold text-ink">Choose a PDF or DOCX resume</span>
                      <span className="mt-2 block text-sm text-muted">PDF or DOCX, up to 10 MB</span>
                    </div>
                  )}
                </label>
                
                {fileError && (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4 flex items-center gap-2 text-sm font-medium text-danger" role="alert">
                    <AlertCircle size={16} />
                    {fileError}
                  </motion.div>
                )}
                {submit.error && (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4 flex items-center gap-2 text-sm font-medium text-danger" role="alert">
                    <AlertCircle size={16} />
                    {submit.error.message}
                  </motion.div>
                )}

                <div className="mt-6 flex flex-wrap items-center justify-between gap-4 border-t pt-6">
                  <p className="text-xs text-muted max-w-sm leading-relaxed">Parsing runs in the background. Your resume is safely processed to extract skills and experiences.</p>
                  <button
                    disabled={!file || submit.isPending}
                    className="button-primary"
                    onClick={() => submit.mutate()}
                  >
                    <FileUp size={16} aria-hidden="true" className={submit.isPending ? 'animate-pulse' : ''} />
                    {submit.isPending ? 'Uploading…' : 'Read My Resume'}
                  </button>
                </div>
              </div>
            </div>
          </section>
        ) : null}

        {running ? <ReadingStatus /> : null}
        {failure ? <ImportFailure error={failure} onRetry={() => { setQueued(null); setFile(null) }} /> : null}
        {job.data?.status === 'done' && detail.isPending ? (
          <div className="max-w-3xl mt-10">
            <ScreenState kind="loading" title="Preparing your review…" detail="Loading the extracted items without saving them." />
          </div>
        ) : null}
        {detail.isError ? (
          <div className="max-w-3xl mt-10">
            <ScreenState kind="error" title="Review unavailable" detail={detail.error.message} onRetry={() => void detail.refetch()} />
          </div>
        ) : null}

        {detail.data?.parsed_json ? (
          <section aria-labelledby="review-title" className="mt-12">
            <div className="mb-8 flex flex-wrap items-end justify-between gap-4 border-b pb-5">
              <div>
                <p className="eyebrow">Unsaved draft</p>
                <h2 id="review-title" className="mt-2 font-display text-3xl font-medium tracking-tight">Review Extracted Evidence</h2>
                <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted">Checked items and skills are included. Edit or deselect anything before importing.</p>
              </div>
              <p className="font-mono text-xs font-semibold uppercase tracking-wider text-muted" aria-live="polite">
                {selectedItems.length} of {items.length} items selected
              </p>
            </div>
            
            <div className="space-y-8">
              <Stagger staggerDelay={0.05}>
                {items.map((item, index) => (
                  <StaggerItem key={item.key}>
                    <ReviewCard item={item} index={index} onChange={change => updateItem(item.key, change)} />
                  </StaggerItem>
                ))}
              </Stagger>
            </div>
            
            <section className="mt-16 border-t pt-10 pb-8" aria-labelledby="skills-title">
              <div className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
                <div>
                  <h3 id="skills-title" className="font-display text-2xl font-medium">Skills found</h3>
                  <p className="mt-2 text-sm text-muted max-w-xl">Selected skills will be saved as individual Skill Bank entries.</p>
                </div>
                <p className="font-mono text-[11px] font-semibold uppercase tracking-wider text-muted" aria-live="polite">
                  {selectedSkills.length} of {skills.length} selected
                </p>
              </div>
              
              {skills.length ? (
                <div className="mt-6 flex flex-wrap gap-2.5">
                  {skills.map(skill => (
                    <button 
                      type="button" 
                      aria-pressed={skill.included} 
                      className={`tag gap-1.5 px-3 py-1.5 transition-all ${
                        skill.included 
                          ? '!border-accent/40 bg-accent-soft text-ink shadow-sm' 
                          : 'opacity-50 hover:opacity-100 bg-surface'
                      }`} 
                      key={skill.name} 
                      onClick={() => setSkills(current => current.map(item => item.name === skill.name ? { ...item, included: !item.included } : item))}
                    >
                      {skill.included ? <Check size={14} className="text-accent" aria-hidden="true" /> : <X size={14} className="text-muted" aria-hidden="true" />}
                      {skill.name}
                    </button>
                  ))}
                </div>
              ) : (
                <p className="mt-6 text-sm text-muted">No skills were extracted from this resume.</p>
              )}
            </section>
          </section>
        ) : null}
      </Reveal>

      {/* Sticky Action Bar */}
      {detail.data?.parsed_json ? (
        <div className="fixed inset-x-0 bottom-0 z-40 border-t border-line/60 bg-canvas/90 px-5 py-4 backdrop-blur-lg [padding-bottom:max(1rem,env(safe-area-inset-bottom))] md:px-10 lg:left-64 xl:px-16 shadow-2xl">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-ink">Nothing is saved until you confirm.</p>
              <p className="mt-1 text-xs text-muted">
                {selectedItems.length} {selectedItems.length === 1 ? 'item' : 'items'} · {selectedSkills.length} {selectedSkills.length === 1 ? 'skill' : 'skills'} selected
              </p>
            </div>
            
            <button 
              className="button-primary" 
              disabled={(!selectedItems.length && !selectedSkills.length) || invalid || commit.isPending} 
              onClick={commitSelected}
            >
              <Check size={16} aria-hidden="true" />
              {commit.isPending ? 'Importing…' : 'Import Selected'}
            </button>
          </div>
          
          {invalid && (
            <p className="mt-3 flex items-center gap-2 text-xs font-medium text-danger" role="alert">
              <AlertCircle size={14} /> Selected items need a title, and kept bullets cannot be empty.
            </p>
          )}
          {commit.error && (
            <p className="mt-3 flex items-center gap-2 text-xs font-medium text-danger" role="alert">
              <AlertCircle size={14} /> {commit.error.message}
            </p>
          )}
        </div>
      ) : null}
    </div>
  )
}

function ReadingStatus() {
  return (
    <div className="max-w-3xl rounded-xl border bg-surface p-8 shadow-sm" role="status" aria-live="polite">
      <div className="flex items-start gap-4">
        <LoaderCircle className="mt-0.5 animate-spin text-accent" size={20} aria-hidden="true" />
        <div>
          <p className="font-semibold text-ink">Reading your resume…</p>
          <p className="mt-2 text-sm leading-relaxed text-muted max-w-xl">Extracting only the content present in your file. This may take a moment.</p>
        </div>
      </div>
    </div>
  )
}

function ImportFailure({ error, onRetry }: { error: string; onRetry: () => void }) {
  const settings = /provider|llm|configured|api key|credential/i.test(error)
  const extraction = /extract|pdf|docx|document|file|text/i.test(error)
  
  return (
    <div className="max-w-3xl rounded-xl border border-danger/30 bg-danger/5 p-8 shadow-sm" role="alert">
      <div className="flex items-start gap-4">
        <AlertCircle size={20} className="mt-0.5 shrink-0 text-danger" />
        <div>
          <p className="font-semibold text-danger">Resume import failed</p>
          <p className="mt-2 text-sm leading-relaxed text-danger/80">{error}</p>
          {extraction && (
            <p className="mt-2 text-sm leading-relaxed text-danger/80">Try exporting the resume in the other supported format, then upload it again.</p>
          )}
          
          <div className="mt-6 flex flex-wrap gap-3">
            <button className="button-secondary bg-surface" onClick={onRetry}>Try Another File</button>
            {settings && <Link className="button-ghost text-accent hover:bg-accent/10" href="/settings">Open Settings</Link>}
          </div>
        </div>
      </div>
    </div>
  )
}

function ReviewCard({ item, index, onChange }: { item: ReviewItem; index: number; onChange: (change: Partial<ReviewItem>) => void }) {
  const setBullet = (bulletIndex: number, value: string) => onChange({ bullets: item.bullets.map((bullet, current) => current === bulletIndex ? value : bullet) })
  const removeBullet = (bulletIndex: number) => onChange({ bullets: item.bullets.filter((_, current) => current !== bulletIndex) })
  
  return (
    <article className={`rounded-xl border bg-surface shadow-sm transition-all duration-300 ${item.included ? 'border-line' : 'opacity-60 grayscale-[0.5]'}`}>
      <header className="flex flex-col gap-4 border-b bg-raised/40 p-5 sm:flex-row sm:items-start sm:justify-between sm:p-6 sm:px-8">
        <label className="flex min-h-11 cursor-pointer items-start gap-4">
          <input 
            className="mt-1.5 size-4 rounded border-line text-accent focus:ring-accent" 
            type="checkbox" 
            name={`${item.key}-included`} 
            checked={item.included} 
            onChange={event => onChange({ included: event.target.checked })}
          />
          <span>
            <span className="font-mono text-[11px] font-bold tracking-wider text-muted">
              ITEM {String(index + 1).padStart(2, '0')} · {item.type.toUpperCase()}
            </span>
            <span className="mt-1 block text-sm font-semibold text-ink">
              {item.included ? 'Included in import' : 'Not included'}
            </span>
          </span>
        </label>
        
        <span className="inline-flex items-center gap-1.5 rounded-full border border-warning/30 bg-warning/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-warning-dark">
          <div className="size-1.5 rounded-full bg-warning" />
          Not saved
        </span>
      </header>
      
      <div className="p-6 sm:p-8">
        <fieldset disabled={!item.included} className="grid gap-5 sm:grid-cols-2">
          <label className="text-sm font-semibold text-ink" htmlFor={`${item.key}-title`}>
            Title
            <input 
              id={`${item.key}-title`} 
              name={`${item.key}-title`} 
              className="field mt-2.5 bg-canvas font-medium" 
              required 
              autoComplete="organization-title" 
              value={item.title} 
              onChange={event => onChange({ title: event.target.value })}
            />
          </label>
          <label className="text-sm font-semibold text-ink" htmlFor={`${item.key}-org`}>
            Organization
            <input 
              id={`${item.key}-org`} 
              name={`${item.key}-organization`} 
              className="field mt-2.5 bg-canvas" 
              autoComplete="organization" 
              value={item.org ?? ''} 
              onChange={event => onChange({ org: event.target.value || null })}
            />
          </label>
          <label className="text-sm font-semibold text-ink" htmlFor={`${item.key}-start`}>
            Start Date
            <input 
              id={`${item.key}-start`} 
              name={`${item.key}-start-date`} 
              type="date" 
              className="field mt-2.5 bg-canvas font-mono text-sm" 
              value={item.start_date ?? ''} 
              onChange={event => onChange({ start_date: event.target.value || null })}
            />
          </label>
          <label className="text-sm font-semibold text-ink" htmlFor={`${item.key}-end`}>
            End Date
            <input 
              id={`${item.key}-end`} 
              name={`${item.key}-end-date`} 
              type="date" 
              className="field mt-2.5 bg-canvas font-mono text-sm" 
              value={item.end_date ?? ''} 
              onChange={event => onChange({ end_date: event.target.value || null })}
            />
          </label>
        </fieldset>
        
        <div className="mt-8 border-t pt-8">
          <p className="eyebrow mb-5">Proof points</p>
          
          {item.bullets.length ? (
            <ol className="space-y-4">
              {item.bullets.map((bullet, bulletIndex) => (
                <li className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]" key={`${item.key}-bullet-${bulletIndex}`}>
                  <label className="sr-only" htmlFor={`${item.key}-bullet-${bulletIndex}`}>
                    Proof point {bulletIndex + 1} for {item.title}
                  </label>
                  <textarea 
                    id={`${item.key}-bullet-${bulletIndex}`} 
                    name={`${item.key}-bullet-${bulletIndex}`} 
                    className="field min-h-24 resize-y bg-canvas py-3.5 leading-relaxed text-ink/90" 
                    disabled={!item.included} 
                    value={bullet} 
                    onChange={event => setBullet(bulletIndex, event.target.value)}
                  />
                  <button 
                    type="button" 
                    className="button-ghost self-start text-danger hover:!bg-danger/10" 
                    disabled={!item.included} 
                    onClick={() => removeBullet(bulletIndex)} 
                    aria-label={`Remove proof point ${bulletIndex + 1} from ${item.title}`}
                  >
                    <Trash2 size={16} aria-hidden="true" />
                    <span className="sm:hidden font-medium">Remove</span>
                  </button>
                </li>
              ))}
            </ol>
          ) : (
            <div className="rounded-lg border border-dashed p-6 text-center">
              <p className="text-sm text-muted">No proof points extracted for this item.</p>
            </div>
          )}
        </div>
      </div>
    </article>
  )
}
