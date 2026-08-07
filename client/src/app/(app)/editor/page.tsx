"use client"

import Editor from '@monaco-editor/react'
import { AlertTriangle, Check, ChevronDown, Download, History, Play, Save, X, FileCheck, AlertCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { AsyncProgress } from '@/components/AsyncProgress'
import { tex, versions } from '@/lib/demo'
import { useUI } from '@/store/ui'
import { DURATION, EASE } from '@/lib/motion'
import type { JobState } from '@/lib/types'

export default function LatexEditor() {
  const { theme } = useUI()
  const [source, setSource] = useState(tex)
  const [state, setState] = useState<JobState>('done')
  const [progress, setProgress] = useState(100)
  const [mobilePane, setMobilePane] = useState<'source' | 'preview'>('source')
  const [history, setHistory] = useState(false)
  const [hasError, setHasError] = useState(false)

  // Demo error detection
  useEffect(() => {
    setHasError(source.includes('\\badcommand'))
  }, [source])

  const compile = () => {
    setState('running')
    setProgress(14)
    const timer = setInterval(() => setProgress((p) => Math.min(p + 24, 94)), 380)
    setTimeout(() => {
      clearInterval(timer)
      setState(hasError ? 'failed' : 'done')
      setProgress(100)
      if (!hasError && window.innerWidth < 1024) {
        setMobilePane('preview')
      }
    }, 1700)
  }

  // Ctrl+Enter to compile
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault()
        compile()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  })

  return (
    <div className="flex h-[calc(100vh-3.5rem)] lg:h-[calc(100vh-4rem)] flex-col bg-surface overflow-hidden">
      {/* ─── Toolbar ─────────────────────────────────────── */}
      <header className="no-print flex min-h-16 shrink-0 flex-wrap items-center justify-between gap-3 border-b bg-canvas px-4 py-2 md:px-6 shadow-sm z-20 relative">
        <div className="flex min-w-0 items-center gap-4">
          <div>
            <p className="eyebrow !mb-0.5">Resume version</p>
            <button className="group flex items-center gap-1.5 truncate font-semibold transition-colors hover:text-accent">
              Fathom · Senior Product Engineer
              <ChevronDown size={15} className="text-muted transition-transform group-hover:translate-y-px" />
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <AnimatePresence mode="wait">
            {state === 'done' ? (
              <motion.span
                key="done"
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                className="mr-3 hidden items-center gap-1.5 rounded-full bg-success/10 px-2.5 py-1 text-xs font-semibold text-success sm:flex"
              >
                <Check size={14} /> Compiled
              </motion.span>
            ) : state === 'failed' ? (
              <motion.span
                key="failed"
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                className="mr-3 hidden items-center gap-1.5 rounded-full bg-danger/10 px-2.5 py-1 text-xs font-semibold text-danger sm:flex"
              >
                <AlertTriangle size={14} /> Compile failed
              </motion.span>
            ) : (
              <motion.span
                key="compiling"
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                className="mr-3 hidden items-center gap-1.5 rounded-full bg-accent/10 px-2.5 py-1 text-xs font-semibold text-accent sm:flex"
              >
                <span className="relative flex size-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75"></span>
                  <span className="relative inline-flex size-2 rounded-full bg-accent"></span>
                </span>
                Compiling
              </motion.span>
            )}
          </AnimatePresence>

          <button 
            className={`button-ghost !px-2.5 sm:!px-3 transition-colors ${history ? 'bg-surface text-ink' : ''}`} 
            onClick={() => setHistory(!history)}
          >
            <History size={16} />
            <span className="hidden sm:inline">History</span>
          </button>
          <div className="h-6 w-px bg-line/60 hidden sm:block" />
          <button className="button-secondary !px-2.5 sm:!px-3 text-muted hover:text-ink">
            <Save size={16} />
            <span className="hidden sm:inline">Save</span>
          </button>
          <button 
            className="button-primary !px-3 sm:!px-4" 
            onClick={compile} 
            disabled={state === 'running'}
          >
            {state === 'running' ? (
              <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}>
                <Play size={16} className="fill-current" />
              </motion.div>
            ) : (
              <Play size={16} className="fill-current" />
            )}
            <span className="hidden sm:inline">Compile</span>
          </button>
        </div>
      </header>

      {/* ─── State banners ───────────────────────────────── */}
      <AnimatePresence>
        {state === 'running' && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="shrink-0 overflow-hidden bg-surface"
          >
            <AsyncProgress
              state={state}
              progress={progress}
              stage={progress < 45 ? 'Validating LaTeX source' : progress < 80 ? 'Tectonic is typesetting' : 'Preparing preview'}
            />
          </motion.div>
        )}
        {state === 'failed' && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="shrink-0 overflow-hidden"
          >
            <div role="alert" className="flex items-start gap-3 border-b bg-danger/10 px-5 py-3 text-sm text-danger shadow-sm">
              <AlertCircle size={18} className="mt-0.5 shrink-0" />
              <div>
                <strong className="block mb-1">Compilation stopped on line 8.</strong>
                <span>Undefined control sequence <code className="rounded bg-danger/20 px-1 py-0.5 font-mono text-xs">\\badcommand</code>.</span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─── Mobile Tabs ─────────────────────────────────── */}
      <div className="no-print flex shrink-0 border-b bg-canvas lg:hidden" role="tablist">
        <button
          className={`relative min-h-11 flex-1 px-4 text-sm font-semibold transition-colors ${
            mobilePane === 'source' ? 'text-ink' : 'text-muted hover:bg-surface'
          }`}
          onClick={() => setMobilePane('source')}
        >
          LaTeX Source
          {mobilePane === 'source' && (
            <motion.div layoutId="mobilePaneTab" className="absolute inset-x-0 bottom-0 h-0.5 bg-accent" />
          )}
        </button>
        <button
          className={`relative min-h-11 flex-1 px-4 text-sm font-semibold transition-colors ${
            mobilePane === 'preview' ? 'text-ink' : 'text-muted hover:bg-surface'
          }`}
          onClick={() => setMobilePane('preview')}
        >
          PDF Preview
          {mobilePane === 'preview' && (
            <motion.div layoutId="mobilePaneTab" className="absolute inset-x-0 bottom-0 h-0.5 bg-accent" />
          )}
        </button>
      </div>

      {/* ─── Main Editor Area ────────────────────────────── */}
      <div className="relative flex min-h-0 flex-1 flex-col lg:flex-row overflow-hidden">
        
        {/* Source Pane */}
        <section
          aria-label="LaTeX source editor"
          className={`${
            mobilePane === 'source' ? 'flex' : 'hidden'
          } min-h-0 flex-1 flex-col border-r bg-canvas lg:flex relative`}
        >
          <Editor
            height="100%"
            defaultLanguage="latex"
            value={source}
            onChange={(v) => setSource(v ?? '')}
            theme={theme === 'dark' ? 'vs-dark' : 'vs'}
            options={{
              minimap: { enabled: false },
              fontFamily: '"IBM Plex Mono", monospace',
              fontSize: 13,
              lineHeight: 1.7,
              wordWrap: 'on',
              padding: { top: 20, bottom: 20 },
              scrollBeyondLastLine: false,
              automaticLayout: true,
              renderLineHighlight: 'all',
              cursorBlinking: 'smooth',
              cursorSmoothCaretAnimation: 'on',
              formatOnPaste: true,
            }}
          />
          <div className="absolute bottom-4 right-4 pointer-events-none">
            <kbd className="hidden rounded-md border border-line bg-surface/80 px-2 py-1 font-mono text-[10px] text-muted shadow-sm backdrop-blur-sm sm:block">
              Cmd+Enter to compile
            </kbd>
          </div>
        </section>

        {/* Preview Pane */}
        <section
          aria-label="PDF preview"
          className={`${
            mobilePane === 'preview' ? 'flex' : 'hidden'
          } relative min-h-0 flex-1 flex-col items-center overflow-auto bg-raised p-4 md:p-8 lg:flex lg:bg-subtle/10`}
          style={{
            backgroundImage: `radial-gradient(var(--line-soft) 1px, transparent 1px)`,
            backgroundSize: '20px 20px',
          }}
        >
          <ResumePreview />
        </section>

        {/* History Sidebar */}
        <AnimatePresence>
          {history && (
            <motion.aside
              initial={{ x: '100%', opacity: 0.5 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: '100%', opacity: 0.5 }}
              transition={{ duration: DURATION.normal, ease: EASE.outExpo }}
              className="absolute inset-y-0 right-0 z-30 w-full max-w-sm border-l bg-canvas shadow-elevated flex flex-col"
            >
              <div className="flex shrink-0 items-center justify-between border-b px-5 py-4">
                <h2 className="section-title text-lg">Version history</h2>
                <button className="button-ghost !px-2" onClick={() => setHistory(false)} aria-label="Close history">
                  <X size={18} />
                </button>
              </div>
              <div className="flex-1 overflow-y-auto p-5">
                <ol className="relative border-l border-line ml-3 space-y-6">
                  {versions.map((v, i) => (
                    <li key={v.id} className="pl-6 relative">
                      <div className={`absolute -left-[5px] top-1 h-2.5 w-2.5 rounded-full border-2 border-canvas ${i === 0 ? 'bg-accent' : 'bg-line'}`} />
                      <button className="group w-full text-left">
                        <div className="flex items-baseline justify-between gap-2">
                          <strong className={`text-sm transition-colors ${i === 0 ? 'text-ink' : 'text-muted group-hover:text-ink'}`}>
                            {i === 0 ? 'Current draft' : `Version ${versions.length - i}`}
                          </strong>
                          <span className="font-mono text-xs text-muted shrink-0">{v.updatedAt}</span>
                        </div>
                        <div className="mt-2 flex items-center gap-2">
                          <span className="inline-flex items-center gap-1 rounded bg-raised px-1.5 py-0.5 text-xs text-muted">
                            <FileCheck size={12} /> ATS: {v.atsScore}%
                          </span>
                        </div>
                      </button>
                    </li>
                  ))}
                </ol>
              </div>
            </motion.aside>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

function ResumePreview() {
  return (
    <div className="relative w-full max-w-[42rem]">
      {/* Paper drop shadow effect */}
      <div className="absolute inset-0 translate-y-2 scale-[0.98] bg-black/10 blur-xl rounded-sm" />
      
      <div className="relative min-h-[54rem] w-full bg-white p-[clamp(2rem,7vw,4.5rem)] text-black shadow-sm ring-1 ring-black/5 selection:bg-accent/20">
        <header className="border-b border-black/30 pb-4 text-center">
          <h2 className="font-serif text-2xl font-bold tracking-tight">Dhruv Sharma</h2>
          <p className="mt-1 font-serif text-[11px] text-black/70">
            Bengaluru, India · dhruv@example.com · github.com/dhruv
          </p>
        </header>
        
        <PreviewSection title="Experience">
          <p className="font-serif text-sm font-bold">
            Product Engineer <span className="float-right font-normal text-black/80">2023—Present</span>
          </p>
          <p className="font-serif text-xs italic text-black/80">Northstar Labs, Bengaluru</p>
          <ul className="mt-2 list-disc space-y-1 pl-4 font-serif text-[11px] leading-[1.55] text-black/90">
            <li>Owned a cross-functional React and TypeScript release workflow, reducing median deployment setup from 18 minutes to 6 minutes.</li>
            <li>Architected a PostgreSQL audit-log pipeline processing 2.4M monthly events with traceable retention controls.</li>
          </ul>
        </PreviewSection>
        
        <PreviewSection title="Projects">
          <p className="font-serif text-sm font-bold">
            Papertrail <span className="font-normal text-black/70">— React, FastAPI, Python</span>
          </p>
          <ul className="mt-2 list-disc pl-4 font-serif text-[11px] leading-[1.55] text-black/90">
            <li>Built a local-first document index with conflict-safe sync and full-text search across 12,000 notes.</li>
          </ul>
        </PreviewSection>

        <div className="no-print mt-16 flex justify-center opacity-0 transition-opacity hover:opacity-100 focus-within:opacity-100 absolute bottom-12 inset-x-0">
          <button className="button-secondary bg-white/90 backdrop-blur text-black shadow-md border-black/10">
            <Download size={15} /> Download PDF
          </button>
        </div>
      </div>
    </div>
  )
}

function PreviewSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-5">
      <h3 className="mb-2 border-b border-black/60 pb-1 font-serif text-sm font-bold uppercase tracking-wider text-black/90">
        {title}
      </h3>
      {children}
    </section>
  )
}
