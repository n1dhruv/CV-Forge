"use client"

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ArrowRight, Check, FileUp, LoaderCircle, RotateCw, Sparkles, FileText, CheckCircle2, ChevronDown } from 'lucide-react'
import { useEffect, useState, useRef } from 'react'
import Link from 'next/link'
import { useSearchParams, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { PageHeader } from '@/components/PageHeader'
import { ScreenState } from '@/components/ScreenState'
import { useApi } from '@/hooks/useApi'
import { useBackgroundJobStatus } from '@/hooks/useBackgroundJobStatus'
import { ApiError } from '@/lib/api'
import { Reveal } from '@/components/motion/Reveal'
import { Stagger, StaggerItem } from '@/components/motion/Stagger'
import { AsyncProgress } from '@/components/AsyncProgress'
import { DURATION, EASE } from '@/lib/motion'
import type { JobDescription, JDParseQueued } from '@/lib/types'

const date = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' })

export default function JDInput() {
  const api = useApi()
  const queryClient = useQueryClient()
  const params = useSearchParams()
  const router = useRouter()
  const [mode, setMode] = useState<'paste' | 'upload'>('paste')
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [queued, setQueued] = useState<JDParseQueued | null>(null)

  const settings = useQuery({
    queryKey: ['llm-settings'],
    queryFn: api.llmSettings.get,
    retry: (count, error) => (error instanceof ApiError && error.status === 404 ? false : count < 1),
  })

  const jds = useQuery({
    queryKey: ['jds'],
    queryFn: api.jd.list,
    enabled: !!settings.data,
  })

  const submit = useMutation({
    mutationFn: () => (mode === 'paste' ? api.jd.parseText(text.trim()) : api.jd.parsePdf(file!)),
    onSuccess: async (result) => {
      setQueued(result)
      router.replace(`/job-description?jd=${result.job_description_id}`, { scroll: false })
      await queryClient.invalidateQueries({ queryKey: ['jds'] })
    },
  })

  const job = useBackgroundJobStatus(queued?.background_job_id)
  const selectedId = queued?.job_description_id ?? params.get('jd')

  const detail = useQuery({
    queryKey: ['jd', selectedId],
    queryFn: () => api.jd.get(selectedId!),
    enabled: !!selectedId && (!queued || job.data?.status === 'done'),
  })

  useEffect(() => {
    if (job.data?.status === 'done' || job.data?.status === 'failed') {
      void queryClient.invalidateQueries({ queryKey: ['jds'] })
    }
  }, [job.data?.status, queryClient])

  if (settings.isPending) {
    return (
      <div className="container-normal py-10 md:py-12">
        <ScreenState kind="loading" title="Checking AI readiness…" detail="Looking for your saved provider." />
      </div>
    )
  }

  if (settings.error instanceof ApiError && settings.error.status === 404) {
    return (
      <div className="container-normal py-10 md:py-12">
        <PageHeader eyebrow="Target role" title="Job Descriptions" />
        <Reveal variant="scale">
          <div className="rounded-xl border border-accent/20 bg-accent-soft px-8 py-10 shadow-sm text-center">
            <div className="mx-auto grid size-12 place-items-center rounded-full bg-accent/10 text-accent mb-6">
              <Sparkles size={24} aria-hidden="true" />
            </div>
            <h2 className="section-title">AI Provider Required</h2>
            <p className="mx-auto mt-3 max-w-lg text-sm leading-relaxed text-muted">
              Add your own LLM provider key before parsing job descriptions. ResumeForge uses your configuration to parse safely and securely.
            </p>
            <Link className="button-primary mt-8" href="/settings">
              Configure AI Provider
            </Link>
          </div>
        </Reveal>
      </div>
    )
  }

  if (settings.isError) {
    return (
      <div className="container-normal py-10 md:py-12">
        <ScreenState kind="error" title="AI settings unavailable" detail={settings.error.message} onRetry={() => void settings.refetch()} />
      </div>
    )
  }

  const terminalError = job.data?.status === 'failed' ? job.data.error : null

  // Optimistically add the queued item to the list so it appears in the accordion immediately
  let displayJds = jds.data?.filter(item => item.status !== 'failed') || []
  if (queued && !displayJds.find(jd => jd.id === queued.job_description_id)) {
    displayJds = [
      {
        id: queued.job_description_id,
        excerpt: mode === 'paste' ? 'Pasted Job Description' : file?.name || 'Uploaded PDF',
        status: job.data?.status || 'queued',
        created_at: new Date().toISOString()
      },
      ...displayJds
    ]
  }

  return (
    <div className="container-normal py-10 pb-32 md:py-12">
      <PageHeader
        eyebrow="Target role"
        title="Job Descriptions"
        description="Provide the source. ResumeForge separates requirements from preferences before it touches your resume."
      />

      <div className="flex flex-col gap-12 items-center">
        {/* Input Section */}
        <Reveal variant="up" delay={0.1} as="section" aria-labelledby="jd-source" className="w-full max-w-4xl">
          <h2 id="jd-source" className="sr-only">Job description source</h2>
          
          <div className="rounded-xl border bg-surface shadow-sm overflow-hidden">
            <div role="tablist" aria-label="Job description input" className="flex border-b bg-raised/50">
              <button
                role="tab"
                aria-selected={mode === 'paste'}
                onClick={() => setMode('paste')}
                className={`relative flex-1 py-3.5 text-sm font-semibold transition-colors ${
                  mode === 'paste' ? 'text-ink' : 'text-muted hover:text-ink hover:bg-surface'
                }`}
              >
                Paste Text
                {mode === 'paste' && (
                  <motion.div layoutId="jd-tab" className="absolute inset-x-0 bottom-0 h-0.5 bg-accent" />
                )}
              </button>
              <button
                role="tab"
                aria-selected={mode === 'upload'}
                onClick={() => setMode('upload')}
                className={`relative flex-1 py-3.5 text-sm font-semibold transition-colors ${
                  mode === 'upload' ? 'text-ink' : 'text-muted hover:text-ink hover:bg-surface'
                }`}
              >
                Upload PDF
                {mode === 'upload' && (
                  <motion.div layoutId="jd-tab" className="absolute inset-x-0 bottom-0 h-0.5 bg-accent" />
                )}
              </button>
            </div>

            <div className="p-6 sm:p-8">
              <AnimatePresence mode="wait">
                {mode === 'paste' ? (
                  <motion.div
                    key="paste"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.2 }}
                  >
                    <label className="sr-only" htmlFor="jd-text">Job Description Text</label>
                    <textarea
                      id="jd-text"
                      name="job-description"
                      className="field min-h-[16rem] resize-y py-4 leading-relaxed bg-canvas"
                      autoComplete="off"
                      value={text}
                      onChange={(e) => setText(e.target.value)}
                      placeholder="Paste the complete job description here… Includes responsibilities, requirements, and company overview."
                    />
                  </motion.div>
                ) : (
                  <motion.div
                    key="upload"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.2 }}
                  >
                    <label
                      className={`relative flex min-h-[16rem] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed transition-all ${
                        file ? 'border-accent bg-accent-soft/50' : 'border-line hover:border-accent/50 hover:bg-raised'
                      }`}
                      htmlFor="jd-file"
                    >
                      <input
                        id="jd-file"
                        name="job-description-pdf"
                        type="file"
                        accept="application/pdf,.pdf"
                        className="sr-only"
                        onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                      />
                      
                      {file ? (
                        <div className="text-center px-4">
                          <div className="mx-auto mb-4 grid size-12 place-items-center rounded-full bg-accent text-white shadow-md">
                            <FileText size={24} />
                          </div>
                          <span className="block font-semibold text-ink break-all">{file.name}</span>
                          <span className="mt-2 block text-sm text-muted">{(file.size / (1024 * 1024)).toFixed(2)} MB • Click to change</span>
                        </div>
                      ) : (
                        <div className="text-center px-6">
                          <FileUp className="mx-auto mb-4 text-muted" size={32} aria-hidden="true" />
                          <span className="block font-semibold text-ink">Choose a job description PDF</span>
                          <span className="mt-2 block text-sm text-muted">Supports text-based PDFs up to 10 MB</span>
                        </div>
                      )}
                    </label>
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="mt-6 flex flex-wrap items-center justify-between gap-4 border-t pt-6">
                <p className="text-xs text-muted max-w-sm leading-relaxed">Parsing runs in the background. You can navigate away safely while the AI structures your target job description.</p>
                <button
                  disabled={submit.isPending || (mode === 'paste' ? !text.trim() : !file)}
                  className="button-primary"
                  onClick={() => submit.mutate()}
                >
                  <Sparkles size={16} aria-hidden="true" className={submit.isPending ? 'animate-pulse' : ''} />
                  {submit.isPending ? 'Queuing Analysis…' : 'Parse Requirements'}
                </button>
              </div>

              {submit.error && (
                <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4 text-sm text-danger font-medium" role="alert">
                  {submit.error.message}
                </motion.p>
              )}
            </div>
          </div>
        </Reveal>
        
        {/* History Accordion Section */}
        <Reveal variant="up" delay={0.2} as="section" className="w-full max-w-4xl" aria-labelledby="history">
          <div className="mb-6 border-b pb-4">
            <h2 id="history" className="font-display text-2xl font-medium">Previous Job Descriptions</h2>
            <p className="text-sm text-muted mt-2">Expand a previously parsed job description to view its structured requirements.</p>
          </div>
          
          {jds.isPending ? (
            <div className="flex flex-col gap-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-24 animate-pulse rounded-xl bg-surface border border-line-soft" />
              ))}
            </div>
          ) : jds.isError ? (
            <ScreenState kind="error" title="History unavailable" detail={jds.error.message} onRetry={() => void jds.refetch()} />
          ) : (
            <div className="flex flex-col gap-4">
              {displayJds.map((item) => {
                const isOpen = selectedId === item.id
                
                return (
                  <div key={item.id} className={`rounded-xl border transition-all duration-300 overflow-hidden ${isOpen ? 'bg-surface shadow-md border-accent/40 ring-1 ring-accent/20' : 'bg-surface hover:border-accent hover:shadow-sm'}`}>
                    {/* Accordion Header */}
                    <button
                      className="w-full text-left p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-inset"
                      onClick={() => {
                        if (isOpen) {
                          router.replace('/job-description', { scroll: false })
                          setQueued(null)
                        } else {
                          router.replace(`/job-description?jd=${item.id}`, { scroll: false })
                        }
                      }}
                    >
                      <div className="flex-1 min-w-0 pr-4">
                        <p className={`line-clamp-2 text-sm font-medium leading-relaxed transition-colors ${isOpen ? 'text-accent' : 'text-ink'}`}>
                          {item.excerpt || 'PDF job description'}
                        </p>
                        <div className="mt-3 flex flex-wrap items-center gap-3">
                          <time className="font-mono text-[11px] text-muted tracking-wider" dateTime={item.created_at}>
                            {date.format(new Date(item.created_at))}
                          </time>
                          <span className={`rounded-full px-2 py-0.5 font-mono text-[9px] uppercase font-bold tracking-widest ${
                            item.status === 'done' ? 'bg-success/10 text-success' :
                            item.status === 'failed' ? 'bg-danger/10 text-danger' :
                            'bg-accent/10 text-accent'
                          }`}>
                            {item.status}
                          </span>
                        </div>
                      </div>
                      
                      <div className={`shrink-0 grid size-8 place-items-center rounded-full transition-all duration-300 ${isOpen ? 'bg-accent/10 text-accent rotate-180' : 'bg-raised text-muted'}`}>
                        <ChevronDown size={18} />
                      </div>
                    </button>

                    {/* Accordion Content */}
                    <AnimatePresence initial={false}>
                      {isOpen && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.3, ease: EASE.outExpo }}
                          className="border-t"
                        >
                          {queued && item.id === queued.job_description_id && (job.isPending || job.data?.status === 'queued' || job.data?.status === 'running') ? (
                            <div className="min-h-[16rem] flex flex-col justify-center bg-raised/30">
                              <AsyncProgress state={job.data?.status ?? 'queued'} progress={job.data?.status === 'running' ? 50 : 10} stage={job.data?.status === 'queued' ? 'Waiting for worker' : 'Parsing requirements'} />
                              <div className="p-8 text-center mt-6">
                                <div className="mx-auto mb-10 size-16 relative flex items-center justify-center">
                                  {/* Steam */}
                                  <div className="absolute top-0 inset-x-0 flex justify-center gap-2 z-0">
                                    {[0, 1, 2].map(i => (
                                      <motion.div
                                        key={i}
                                        className="w-1 h-4 bg-accent/60 rounded-full blur-[1px]"
                                        animate={{ y: [8, -12], opacity: [0, 1, 0], scaleY: [0.8, 1.2, 0.8] }}
                                        transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.4, ease: "easeInOut" }}
                                      />
                                    ))}
                                  </div>
                                  
                                  {/* The Pot Body */}
                                  <div className="absolute bottom-1 w-12 h-8 bg-surface border-2 border-ink rounded-b-2xl rounded-t-sm z-10 overflow-hidden shadow-sm">
                                     {/* Bubbling liquid inside */}
                                     <motion.div 
                                       className="absolute inset-x-0 bottom-0 bg-accent-soft border-t-2 border-accent"
                                       animate={{ height: ['40%', '70%', '40%'] }}
                                       transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                                     />
                                     {/* Floating bubbles */}
                                     {[0, 1, 2].map(i => (
                                       <motion.div
                                         key={`bubble-${i}`}
                                         className="absolute size-1.5 bg-accent rounded-full"
                                         style={{ left: `${20 + i * 25}%` }}
                                         animate={{ bottom: ['0%', '100%'], opacity: [1, 0], scale: [0.5, 1.5] }}
                                         transition={{ duration: 0.8 + (i * 0.2), repeat: Infinity, delay: i * 0.2, ease: 'easeOut' }}
                                       />
                                     ))}
                                  </div>
                                  
                                  {/* Pot handles */}
                                  <div className="absolute bottom-3.5 -left-1 w-1.5 h-3 border-2 border-ink rounded-l-sm border-r-0 z-0" />
                                  <div className="absolute bottom-3.5 -right-1 w-1.5 h-3 border-2 border-ink rounded-r-sm border-l-0 z-0" />
                                  
                                  {/* Bouncing Lid */}
                                  <motion.div 
                                    className="absolute bottom-[33px] w-[56px] flex flex-col items-center z-20"
                                    animate={{ y: [0, -4, 0], rotate: [0, 3, -2, 0] }}
                                    transition={{ duration: 0.5, repeat: Infinity, ease: 'easeOut' }}
                                  >
                                     <div className="w-4 h-2 border-2 border-ink border-b-0 rounded-t-md" />
                                     <div className="w-full h-1 bg-ink rounded-full" />
                                  </motion.div>
                                </div>
                                <p className="text-sm text-muted">Analysis usually takes 15-30 seconds.</p>
                              </div>
                            </div>
                          ) : terminalError && item.id === queued?.job_description_id ? (
                            <Failed error={terminalError} onRetry={() => submit.mutate()} />
                          ) : detail.isPending ? (
                            <div className="p-8 space-y-6 bg-raised/30">
                              {[1, 2, 3].map(i => (
                                <div key={i} className="space-y-3">
                                  <div className="h-4 w-1/4 animate-pulse rounded bg-raised" />
                                  <div className="flex gap-2">
                                    <div className="h-8 w-24 animate-pulse rounded-full bg-raised" />
                                    <div className="h-8 w-32 animate-pulse rounded-full bg-raised" />
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : detail.isError ? (
                            <div className="p-8 grid place-items-center bg-raised/30">
                              <ScreenState kind="error" title="Result unavailable" detail={detail.error.message} onRetry={() => void detail.refetch()} />
                            </div>
                          ) : detail.data?.parsed_json ? (
                            <div className="bg-raised/30">
                              <ParsedResult detail={detail.data} />
                            </div>
                          ) : null}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                )
              })}
              
              {!displayJds.length && (
                <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted bg-surface/30">
                  <div className="mx-auto mb-4 grid size-12 place-items-center rounded-full bg-raised text-muted">
                    <FileText size={20} />
                  </div>
                  No job descriptions parsed yet. Your history will appear here.
                </div>
              )}
            </div>
          )}
        </Reveal>
      </div>
    </div>
  )
}

function Failed({ error, onRetry }: { error: string; onRetry: () => void }) {
  const provider = /key|provider|settings|rate limit/i.test(error)
  return (
    <div className="p-8 text-center bg-raised/30" role="alert">
      <div className="mx-auto mb-4 grid size-12 place-items-center rounded-full bg-danger/10 text-danger shadow-sm border border-danger/20">
        <AlertTriangle size={20} aria-hidden="true" />
      </div>
      <p className="font-display text-xl font-medium tracking-tight text-danger">Parsing failed</p>
      <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-muted">{error}</p>
      
      <div className="mt-6 flex justify-center gap-3">
        <button className="button-secondary bg-surface" onClick={onRetry}>
          <RotateCw size={14} aria-hidden="true" /> Retry Parse
        </button>
        {provider && (
          <Link className="button-primary shadow-sm" href="/settings">
            Check LLM Settings
          </Link>
        )}
      </div>
    </div>
  )
}

function ParsedResult({ detail }: { detail: JobDescription }) {
  const parsed = detail.parsed_json!
  const verbs = parsed.action_verbs ?? detail.action_verbs ?? []
  
  return (
    <div className="flex h-full flex-col">
      <div className="p-6 sm:p-8 space-y-8">
        <Requirement title="Required Skills" items={parsed.required_skills} highlight />
        <Requirement title="Nice to Have" items={parsed.nice_to_have_skills} />
        
        <div>
          <p className="eyebrow mb-3">Seniority</p>
          <span className="tag px-3 py-1.5 capitalize border-accent/20 bg-accent-soft text-accent shadow-sm">{parsed.seniority}</span>
        </div>
        
        <Requirement title="ATS Keywords" items={parsed.ats_keywords} />
        
        {verbs.length > 0 && <Requirement title="Action verbs to echo" items={verbs} />}
        
        <div>
          <p className="eyebrow mb-3">Responsibilities</p>
          {parsed.responsibilities.length ? (
            <ul className="space-y-3 rounded-xl border border-line-soft bg-surface p-5 shadow-inner">
              {parsed.responsibilities.map((item, i) => (
                <li key={i} className="flex gap-4 text-sm leading-relaxed text-ink/90">
                  <span className="mt-2.5 size-1.5 shrink-0 rounded-full bg-accent/60" aria-hidden="true" />
                  {item}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted italic border rounded-lg p-4 bg-surface text-center">None identified.</p>
          )}
        </div>
      </div>
      
      <div className="border-t bg-surface p-5 sm:p-6 rounded-b-xl flex justify-end">
        <Link className="button-primary shadow-sm hover:-translate-y-0.5 transition-transform" href={`/review?jd=${detail.id}`}>
          Match my resume to this job <ArrowRight size={16} aria-hidden="true" />
        </Link>
      </div>
    </div>
  )
}

function Requirement({ title, items, highlight }: { title: string; items: string[]; highlight?: boolean }) {
  return (
    <div>
      <p className="eyebrow mb-3">{title}</p>
      {items.length ? (
        <div className="flex flex-wrap gap-2">
          {items.map((item) => (
            <span 
              className={`tag break-all px-2.5 py-1 transition-colors ${highlight ? 'border-success/30 bg-success/5 text-success-dark hover:border-success/50 hover:bg-success/10' : 'bg-surface hover:border-line-dark shadow-sm border border-line-soft'}`} 
              key={item}
            >
              {item}
            </span>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted italic border rounded-lg p-4 bg-surface text-center">None identified.</p>
      )}
    </div>
  )
}
