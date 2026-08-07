import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, FileUp, LoaderCircle, Trash2, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PageHeader } from '../components/PageHeader'
import { ScreenState } from '../components/ScreenState'
import { useApi } from '../hooks/useApi'
import { useBackgroundJobStatus } from '../hooks/useBackgroundJobStatus'
import type { ResumeImportCommit, ResumeImportItem, ResumeImportQueued } from '../lib/types'

type ReviewItem = ResumeImportItem & { key: string; included: boolean }
type ReviewSkill = { name: string; included: boolean }
const accepted = new Set(['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'])

export function ResumeImport() {
  const api = useApi()
  const navigate = useNavigate()
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
      navigate(payload.items.length ? '/skill-bank' : '/skill-bank?type=skill', { replace: true, state: { importedCount: result.items.length, importedIds: result.items.map(item => item.id) } })
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

  return <div className="page-enter px-5 py-8 pb-32 md:px-10 md:py-12 xl:px-16">
    <PageHeader eyebrow="Existing evidence" title="Import from Resume" description="Upload a source resume, review every extracted line, then choose exactly what enters your Skill Bank."/>

    {!queued ? <section className="max-w-3xl" aria-labelledby="resume-source-title"><h2 id="resume-source-title" className="sr-only">Resume file</h2><label className="grid min-h-72 cursor-pointer place-items-center border border-dashed bg-surface px-6 text-center hover:bg-raised" htmlFor="resume-file"><input id="resume-file" name="resume-file" type="file" accept="application/pdf,.pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.docx" className="sr-only" onChange={event => chooseFile(event.target.files?.[0] ?? null)}/><span><FileUp className="mx-auto mb-4 text-muted" aria-hidden="true"/><span className="block font-semibold">{file ? file.name : 'Choose a PDF or DOCX resume'}</span><span className="mt-1 block text-sm text-muted">PDF or DOCX, up to 10 MB</span></span></label>{fileError ? <p className="mt-3 text-sm text-danger" role="alert">{fileError}</p> : null}{submit.error ? <p className="mt-3 text-sm text-danger" role="alert">{submit.error.message}</p> : null}<div className="mt-5 flex justify-end"><button className="button-primary" disabled={!file || submit.isPending} onClick={() => submit.mutate()}><FileUp size={16} aria-hidden="true"/>{submit.isPending ? 'Uploading…' : 'Read My Resume'}</button></div></section> : null}

    {running ? <ReadingStatus/> : null}
    {failure ? <ImportFailure error={failure} onRetry={() => { setQueued(null); setFile(null) }}/> : null}
    {job.data?.status === 'done' && detail.isPending ? <div className="max-w-3xl"><ScreenState kind="loading" title="Preparing your review…" detail="Loading the extracted items without saving them."/></div> : null}
    {detail.isError ? <div className="max-w-3xl"><ScreenState kind="error" title="Review unavailable" detail={detail.error.message} onRetry={() => void detail.refetch()}/></div> : null}

    {detail.data?.parsed_json ? <section aria-labelledby="review-title"><div className="mb-8 flex flex-wrap items-end justify-between gap-4 border-b pb-5"><div><p className="eyebrow">Unsaved draft</p><h2 id="review-title" className="mt-2 section-title">Review Extracted Evidence</h2><p className="mt-2 text-sm text-muted">Checked items and skills are included. Edit or deselect anything before importing.</p></div><p className="font-mono text-xs text-muted" aria-live="polite">{selectedItems.length} of {items.length} items selected</p></div><div className="space-y-8">{items.map((item, index) => <ReviewCard key={item.key} item={item} index={index} onChange={change => updateItem(item.key, change)}/>)}</div><section className="mt-10 border-y py-6" aria-labelledby="skills-title"><div className="grid gap-2 sm:grid-cols-[1fr_auto] sm:items-end"><div><h3 id="skills-title" className="section-title">Skills found</h3><p className="mt-1 text-sm text-muted">Selected skills will be saved as individual Skill Bank entries.</p></div><p className="font-mono text-xs text-muted" aria-live="polite">{selectedSkills.length} of {skills.length} selected</p></div>{skills.length ? <div className="mt-5 flex flex-wrap gap-2">{skills.map(skill => <button type="button" aria-pressed={skill.included} className={`tag gap-1.5 transition-opacity ${skill.included?'!border-accent/40 bg-accent-soft text-ink':'opacity-50 hover:opacity-100'}`} key={skill.name} onClick={() => setSkills(current => current.map(item => item.name === skill.name ? { ...item, included: !item.included } : item))}>{skill.included?<Check size={13} aria-hidden="true"/>:<X size={13} aria-hidden="true"/>}{skill.name}</button>)}</div> : <p className="mt-3 text-sm text-muted">No skills were extracted from this resume.</p>}</section></section> : null}

    {detail.data?.parsed_json ? <div className="fixed inset-x-0 bottom-0 z-20 border-t bg-canvas/95 px-5 py-3 backdrop-blur [padding-bottom:max(.75rem,env(safe-area-inset-bottom))] md:px-10 lg:left-64 xl:px-16"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-sm font-semibold">Nothing is saved until you confirm.</p><p className="text-xs text-muted">{selectedItems.length} {selectedItems.length === 1 ? 'item' : 'items'} · {selectedSkills.length} {selectedSkills.length === 1 ? 'skill' : 'skills'} selected</p></div><button className="button-primary" disabled={(!selectedItems.length && !selectedSkills.length) || invalid || commit.isPending} onClick={commitSelected}><Check size={16} aria-hidden="true"/>{commit.isPending ? 'Importing…' : 'Import Selected'}</button></div>{invalid ? <p className="mt-2 text-xs text-danger" role="alert">Selected items need a title, and kept bullets cannot be empty.</p> : null}{commit.error ? <p className="mt-2 text-xs text-danger" role="alert">{commit.error.message}</p> : null}</div> : null}
  </div>
}

function ReadingStatus() {
  return <div className="max-w-3xl border-y bg-surface px-5 py-8" role="status" aria-live="polite"><LoaderCircle className="mb-4 animate-spin text-accent" aria-hidden="true"/><p className="font-semibold">Reading your resume…</p><p className="mt-2 text-sm text-muted">Extracting only the content present in your file. This may take a moment.</p></div>
}

function ImportFailure({ error, onRetry }: { error: string; onRetry: () => void }) {
  const settings = /provider|llm|configured|api key|credential/i.test(error)
  const extraction = /extract|pdf|docx|document|file|text/i.test(error)
  return <div className="max-w-3xl border-l-2 border-danger bg-surface px-5 py-7" role="alert"><p className="font-semibold">Resume import failed</p><p className="mt-2 text-sm text-muted">{error}</p>{extraction ? <p className="mt-2 text-sm text-muted">Try exporting the resume in the other supported format, then upload it again.</p> : null}<div className="mt-5 flex flex-wrap gap-3"><button className="button-secondary" onClick={onRetry}>Try Another File</button>{settings ? <Link className="button-ghost text-accent" to="/settings">Open Settings</Link> : null}</div></div>
}

function ReviewCard({ item, index, onChange }: { item: ReviewItem; index: number; onChange: (change: Partial<ReviewItem>) => void }) {
  const setBullet = (bulletIndex: number, value: string) => onChange({ bullets: item.bullets.map((bullet, current) => current === bulletIndex ? value : bullet) })
  const removeBullet = (bulletIndex: number) => onChange({ bullets: item.bullets.filter((_, current) => current !== bulletIndex) })
  return <article className={`border-y py-6 transition-colors ${item.included ? '' : 'opacity-55'}`}><header className="mb-6 flex items-start justify-between gap-4"><label className="flex min-h-11 cursor-pointer items-start gap-3"><input className="mt-1" type="checkbox" name={`${item.key}-included`} checked={item.included} onChange={event => onChange({ included: event.target.checked })}/><span><span className="eyebrow">Item {String(index + 1).padStart(2, '0')} · {item.type}</span><span className="mt-1 block text-sm font-semibold">{item.included ? 'Included in import' : 'Not included'}</span></span></label><span className="border-l-2 border-warning px-2 py-1 text-xs font-semibold text-warning">Not saved</span></header><fieldset disabled={!item.included} className="grid gap-4 sm:grid-cols-2"><label className="text-sm font-semibold" htmlFor={`${item.key}-title`}>Title<input id={`${item.key}-title`} name={`${item.key}-title`} className="field mt-2" required autoComplete="organization-title" value={item.title} onChange={event => onChange({ title: event.target.value })}/></label><label className="text-sm font-semibold" htmlFor={`${item.key}-org`}>Organization<input id={`${item.key}-org`} name={`${item.key}-organization`} className="field mt-2" autoComplete="organization" value={item.org ?? ''} onChange={event => onChange({ org: event.target.value || null })}/></label><label className="text-sm font-semibold" htmlFor={`${item.key}-start`}>Start Date<input id={`${item.key}-start`} name={`${item.key}-start-date`} type="date" className="field mt-2" value={item.start_date ?? ''} onChange={event => onChange({ start_date: event.target.value || null })}/></label><label className="text-sm font-semibold" htmlFor={`${item.key}-end`}>End Date<input id={`${item.key}-end`} name={`${item.key}-end-date`} type="date" className="field mt-2" value={item.end_date ?? ''} onChange={event => onChange({ end_date: event.target.value || null })}/></label></fieldset><div className="mt-6"><p className="eyebrow mb-3">Proof points</p>{item.bullets.length ? <ol className="space-y-3">{item.bullets.map((bullet, bulletIndex) => <li className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]" key={`${item.key}-bullet-${bulletIndex}`}><label className="sr-only" htmlFor={`${item.key}-bullet-${bulletIndex}`}>Proof point {bulletIndex + 1} for {item.title}</label><textarea id={`${item.key}-bullet-${bulletIndex}`} name={`${item.key}-bullet-${bulletIndex}`} className="field min-h-20 resize-y py-3 leading-6" disabled={!item.included} value={bullet} onChange={event => setBullet(bulletIndex, event.target.value)}/><button type="button" className="button-ghost self-start text-danger" disabled={!item.included} onClick={() => removeBullet(bulletIndex)} aria-label={`Remove proof point ${bulletIndex + 1} from ${item.title}`}><Trash2 size={16} aria-hidden="true"/><span className="sm:hidden">Remove</span></button></li>)}</ol> : <p className="text-sm text-muted">No proof points extracted.</p>}</div></article>
}
