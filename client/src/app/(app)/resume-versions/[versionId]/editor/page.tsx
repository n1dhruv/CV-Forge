"use client"

import type { OnMount } from '@monaco-editor/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ArrowLeft, Check, CopyPlus, Download, History, LoaderCircle, Play, Save, X } from 'lucide-react'
import dynamic from 'next/dynamic'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { useCallback, useEffect, useRef, useState } from 'react'
import { ScreenState } from '@/components/ScreenState'
import { useApi } from '@/hooks/useApi'
import { useBackgroundJobStatus } from '@/hooks/useBackgroundJobStatus'
import { useUI } from '@/store/ui'
import { downloadPdf, shouldShowCompileDiagnostics, validDiagnosticLine } from '@/lib/resume-editor'
import type { CompileDiagnostic, ResumeMetadataUpdate, ResumeVersionDetail } from '@/lib/types'

const MonacoEditor = dynamic(() => import('@monaco-editor/react'), { ssr: false })
const PdfPreview = dynamic(() => import('@/components/resume/PdfPreview'), { ssr: false })

export default function ResumeEditorPage() {
  const { versionId } = useParams<{ versionId: string }>()
  const searchParams = useSearchParams()
  const initialJobId = searchParams.get('job') ?? undefined
  const fromResumes = searchParams.get('from') === 'resumes'
  const router = useRouter()
  const api = useApi()
  const queryClient = useQueryClient()
  const { theme } = useUI()
  const [source, setSource] = useState('')
  const [savedSource, setSavedSource] = useState('')
  const [loadedVersion, setLoadedVersion] = useState<string>()
  const [compileJobId, setCompileJobId] = useState(initialJobId)
  const [diagnostics, setDiagnostics] = useState<CompileDiagnostic[]>([])
  const [mobilePane, setMobilePane] = useState<'source' | 'preview'>('source')
  const [historyOpen, setHistoryOpen] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string>()
  const [previewError, setPreviewError] = useState<string>()
  const [versionLabel, setVersionLabel] = useState('')
  const [resumeName, setResumeName] = useState('')
  const [downloadError, setDownloadError] = useState<Error>()
  const [downloading, setDownloading] = useState(false)
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null)
  const monacoRef = useRef<Parameters<OnMount>[1] | null>(null)

  const detail = useQuery({
    queryKey: ['resume-version-detail', versionId],
    queryFn: () => api.resumeVersions.get(versionId),
    refetchInterval: current => ['assembling', 'compiling'].includes(current.state.data?.status ?? '') ? 2_000 : false,
  })
  const compileJob = useBackgroundJobStatus(compileJobId)
  const dirty = source !== savedSource
  const compiling = !!compileJobId && !['done', 'failed'].includes(compileJob.data?.status ?? '')
  const stalePreview = dirty || compiling || detail.data?.status !== 'compiled'

  useEffect(() => {
    if (!detail.data || loadedVersion === detail.data.id) return
    const nextSource = detail.data.tex_source ?? ''
    setSource(nextSource)
    setSavedSource(nextSource)
    setVersionLabel(detail.data.version_label)
    setResumeName(detail.data.name)
    setLoadedVersion(detail.data.id)
  }, [detail.data, loadedVersion])

  useEffect(() => {
    const preventClose = (event: BeforeUnloadEvent) => {
      if (!dirty) return
      event.preventDefault()
    }
    window.addEventListener('beforeunload', preventClose)
    return () => window.removeEventListener('beforeunload', preventClose)
  }, [dirty])

  useEffect(() => {
    if (!compileJob.data || !compileJobId) return
    if (shouldShowCompileDiagnostics(detail.data?.status, compileJob.data.status)) {
      setDiagnostics(compileJob.data.result?.errors ?? [{ kind: 'internal', message: compileJob.data.error ?? 'Compilation could not finish.' }])
    }
    if (compileJob.data.status === 'done') {
      setDiagnostics([])
      void queryClient.invalidateQueries({ queryKey: ['resume-version-detail', versionId] })
      if (window.innerWidth < 1024) setMobilePane('preview')
    }
  }, [compileJob.data, compileJobId, detail.data?.status, queryClient, versionId])

  useEffect(() => {
    if (detail.data?.status === 'compiled') setDiagnostics([])
  }, [detail.data?.status])

  useEffect(() => {
    const signedUrl = detail.data?.pdf_download_url
    if (!signedUrl) {
      setPreviewUrl(undefined)
      return
    }
    const controller = new AbortController()
    let objectUrl: string | undefined
    setPreviewError(undefined)
    void fetch(signedUrl, { signal: controller.signal })
      .then(response => {
        if (!response.ok) throw new Error('The PDF preview could not be loaded.')
        return response.blob()
      })
      .then(blob => {
        objectUrl = URL.createObjectURL(blob)
        setPreviewUrl(objectUrl)
      })
      .catch(error => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setPreviewError(error instanceof Error ? error.message : 'The PDF preview could not be loaded.')
      })
    return () => {
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [detail.data?.pdf_download_url])

  useEffect(() => {
    const monaco = monacoRef.current
    const model = editorRef.current?.getModel()
    if (!monaco || !model) return
    monaco.editor.setModelMarkers(model, 'tectonic', diagnostics.flatMap(item => {
      const line = validDiagnosticLine(item.line, source)
      return line ? [{ severity: monaco.MarkerSeverity.Error, message: item.message, startLineNumber: line, endLineNumber: line, startColumn: 1, endColumn: model.getLineMaxColumn(line) }] : []
    }))
  }, [diagnostics, source])

  const save = useMutation({
    mutationFn: () => api.resumeVersions.updateTex(versionId, source),
    onSuccess: saved => {
      setSavedSource(saved.tex_source ?? source)
      queryClient.setQueryData(['resume-version-detail', versionId], saved)
    },
  })

  const compile = useMutation({
    mutationFn: async () => {
      if (dirty) await save.mutateAsync()
      return api.resumeVersions.compile(versionId)
    },
    onSuccess: queued => {
      setDiagnostics([])
      setCompileJobId(queued.background_job_id)
    },
  })

  const snapshot = useMutation({
    mutationFn: async () => {
      if (dirty) await save.mutateAsync()
      return api.resumeVersions.snapshot(versionId)
    },
    onSuccess: created => router.push(`/resume-versions/${created.id}/editor${fromResumes ? '?from=resumes' : ''}`),
  })

  const metadata = useMutation({
    mutationFn: (payload: ResumeMetadataUpdate) => api.resumeVersions.updateMetadata(versionId, payload),
    onSuccess: updated => queryClient.setQueryData(['resume-version-detail', versionId], updated),
  })

  const history = useQuery({
    queryKey: ['resume-version-history', versionId],
    queryFn: () => api.resumeVersions.history(versionId),
    enabled: historyOpen,
  })

  const saveNow = useCallback(() => {
    if (dirty && !save.isPending) save.mutate()
  }, [dirty, save])

  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault()
        saveNow()
      }
    }
    window.addEventListener('keydown', shortcut)
    return () => window.removeEventListener('keydown', shortcut)
  }, [saveNow])

  const openVersion = (id: string) => {
    if (dirty && !window.confirm('Discard unsaved changes and open another version?')) return
    router.push(`/resume-versions/${id}/editor${fromResumes ? '?from=resumes' : ''}`)
  }
  const goBack = () => {
    if (dirty && !window.confirm('Discard unsaved changes and leave the editor?')) return
    router.push(fromResumes ? '/resumes' : detail.data?.jd_id ? `/rewrite?jd=${detail.data.jd_id}&version=${versionId}` : '/rewrite')
  }
  const focusDiagnostic = (item: CompileDiagnostic) => {
    const line = validDiagnosticLine(item.line, source)
    if (!line) return
    setMobilePane('source')
    editorRef.current?.revealLineInCenter(line)
    editorRef.current?.setPosition({ lineNumber: line, column: 1 })
    editorRef.current?.focus()
  }
  const onEditorMount: OnMount = (editor, monaco) => {
    editorRef.current = editor
    monacoRef.current = monaco
  }
  const saveVersionLabel = () => {
    const nextLabel = versionLabel.trim()
    if (!nextLabel) {
      setVersionLabel(detail.data?.version_label ?? '')
      return
    }
    if (nextLabel !== detail.data?.version_label) metadata.mutate({ version_label: nextLabel })
    if (nextLabel !== versionLabel) setVersionLabel(nextLabel)
  }
  const saveResumeName = () => {
    const nextName = resumeName.trim()
    if (!nextName) {
      setResumeName(detail.data?.name ?? '')
      return
    }
    if (nextName !== detail.data?.name) metadata.mutate({ name: nextName })
    if (nextName !== resumeName) setResumeName(nextName)
  }
  const downloadCurrentPdf = async () => {
    if (!detail.data?.pdf_download_url) return
    setDownloadError(undefined)
    setDownloading(true)
    try {
      await downloadPdf(detail.data.pdf_download_url, `${detail.data.name}-${detail.data.version_label}`)
    } catch (error) {
      setDownloadError(error instanceof Error ? error : new Error('The PDF could not be downloaded.'))
    } finally {
      setDownloading(false)
    }
  }

  if (detail.isPending) return <div className="container-normal py-12"><ScreenState kind="loading" title="Opening resume editor…" detail="Loading your source and latest PDF." /></div>
  if (detail.isError) return <div className="container-normal py-12"><ScreenState kind="error" title="Resume unavailable" detail={detail.error.message} onRetry={() => void detail.refetch()} /></div>
  if (!detail.data?.tex_source) return <div className="container-normal py-12"><ScreenState kind="empty" title="Resume source is not ready" detail="Return to rewrite review and generate this resume first." /><div className="mt-6 flex justify-center"><button className="button-secondary" onClick={goBack}>Back to review</button></div></div>

  const busy = save.isPending || compile.isPending || compiling || snapshot.isPending
  const actionError = save.error ?? compile.error ?? snapshot.error ?? metadata.error ?? compileJob.error ?? downloadError

  return (
    <div className="flex h-[calc(100vh-3.5rem)] min-h-[36rem] flex-col overflow-hidden bg-surface lg:h-screen">
      <header className="no-print z-20 flex shrink-0 flex-wrap items-center justify-between gap-3 border-b bg-canvas px-3 py-2 shadow-sm md:px-5">
        <div className="flex min-w-0 items-center gap-3">
          <button className="button-ghost !px-2" type="button" onClick={goBack} aria-label="Back to rewrite review"><ArrowLeft size={18} /></button>
          <div className="min-w-0">
            <input
              aria-label="Version name"
              className="block h-6 max-w-48 truncate rounded border border-transparent bg-transparent px-1 text-sm font-semibold hover:border-line focus:border-accent focus:outline-none"
              disabled={metadata.isPending}
              maxLength={80}
              value={versionLabel}
              onBlur={saveVersionLabel}
              onChange={event => setVersionLabel(event.target.value)}
              onKeyDown={event => {
                if (event.key === 'Enter') event.currentTarget.blur()
                if (event.key === 'Escape') {
                  setVersionLabel(detail.data?.version_label ?? '')
                  event.currentTarget.blur()
                }
              }}
            />
            <p className="flex gap-3 text-xs text-muted" aria-live="polite">
              <span>{save.isPending ? 'Saving…' : dirty ? 'Unsaved changes' : 'Saved'}</span>
              <span>{compiling ? 'Compiling…' : diagnostics.length ? 'Needs attention' : stalePreview ? 'Preview out of date' : 'Ready'}</span>
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <input
            aria-label="Resume name"
            className="field !min-h-9 w-36 !px-2 text-sm md:w-48"
            disabled={metadata.isPending}
            maxLength={120}
            value={resumeName}
            onBlur={saveResumeName}
            onChange={event => setResumeName(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter') event.currentTarget.blur()
              if (event.key === 'Escape') {
                setResumeName(detail.data?.name ?? '')
                event.currentTarget.blur()
              }
            }}
          />
          <button className="button-ghost !px-2.5" type="button" onClick={() => setHistoryOpen(true)}><History size={16} /><span className="hidden sm:inline">History</span></button>
          <button className="button-secondary !px-2.5" type="button" disabled={!dirty || busy} onClick={() => save.mutate()}><Save size={16} /><span className="hidden sm:inline">Save</span></button>
          <button className="button-secondary !px-2.5" type="button" disabled={busy} onClick={() => snapshot.mutate()} title="Preserve this point in history"><CopyPlus size={16} /><span className="hidden md:inline">Save as new version</span></button>
          {detail.data.pdf_download_url ? <button className="button-secondary !px-2.5" type="button" disabled={downloading} onClick={() => void downloadCurrentPdf()}>{downloading ? <LoaderCircle className="animate-spin" size={16} /> : <Download size={16} />}<span className="hidden md:inline">{stalePreview ? 'Previous PDF' : 'Download PDF'}</span></button> : null}
          <button className="button-primary !px-3" type="button" disabled={busy} onClick={() => compile.mutate()}>{busy && (compile.isPending || compiling) ? <LoaderCircle className="animate-spin" size={16} /> : <Play size={16} />}<span className="hidden sm:inline">Recompile</span></button>
        </div>
      </header>

      {actionError ? <div className="border-b bg-danger/10 px-5 py-2 text-sm text-danger" role="alert">{actionError.message} Your source remains in the editor.</div> : null}
      {diagnostics.length ? (
        <section className="shrink-0 border-b bg-danger/10 px-5 py-3" aria-labelledby="problems-title">
          <div className="flex items-center gap-2"><AlertTriangle className="text-danger" size={17} /><h2 id="problems-title" className="text-sm font-semibold">Compilation problems</h2><span className="text-xs text-muted">from the previous attempt</span></div>
          <ul className="mt-2 max-h-24 space-y-1 overflow-auto text-sm">
            {diagnostics.map((item, index) => <li key={`${item.message}-${index}`}><button className="text-left text-danger hover:underline disabled:no-underline" type="button" disabled={!validDiagnosticLine(item.line, source)} onClick={() => focusDiagnostic(item)}>{item.line ? `Line ${item.line}: ` : ''}{item.message}</button></li>)}
          </ul>
        </section>
      ) : null}

      <div className="no-print flex shrink-0 border-b bg-canvas lg:hidden" role="tablist" aria-label="Editor panes">
        {(['source', 'preview'] as const).map(pane => <button key={pane} role="tab" aria-selected={mobilePane === pane} className={`min-h-11 flex-1 border-b-2 px-4 text-sm font-semibold ${mobilePane === pane ? 'border-accent text-ink' : 'border-transparent text-muted'}`} onClick={() => setMobilePane(pane)}>{pane === 'source' ? 'LaTeX source' : 'PDF preview'}</button>)}
      </div>

      <main className="relative flex min-h-0 flex-1 overflow-hidden">
        <section aria-label="LaTeX source editor" className={`${mobilePane === 'source' ? 'flex' : 'hidden'} min-w-0 flex-1 border-r bg-canvas lg:flex`}>
          <MonacoEditor height="100%" language="latex" value={source} onChange={value => setSource(value ?? '')} onMount={onEditorMount} theme={theme === 'dark' ? 'vs-dark' : 'vs'} options={{ automaticLayout: true, fontFamily: 'IBM Plex Mono, monospace', fontSize: 13, lineHeight: 22, minimap: { enabled: false }, padding: { top: 16 }, scrollBeyondLastLine: false, wordWrap: 'on' }} />
        </section>
        <section aria-label="PDF preview" className={`${mobilePane === 'preview' ? 'flex' : 'hidden'} relative min-w-0 flex-1 flex-col bg-raised lg:flex`}>
          {stalePreview && detail.data.pdf_download_url ? <div className="absolute inset-x-0 top-0 z-10 bg-warning px-4 py-1.5 text-center text-xs font-semibold text-ink">Previous preview — recompile to reflect current source</div> : null}
          {previewUrl ? <PdfPreview url={previewUrl} stale={stalePreview} /> : <div className="grid size-full place-items-center px-6 text-center"><div><p className="font-semibold">{previewError ? 'Preview unavailable' : detail.data.pdf_download_url ? 'Loading PDF…' : 'No PDF yet'}</p><p className="mt-1 text-sm text-muted">{previewError ?? (detail.data.pdf_download_url ? 'Preparing the browser preview.' : 'Recompile to create a preview.')}</p>{previewError ? <button className="button-secondary mt-4" type="button" onClick={() => void detail.refetch()}>Refresh preview</button> : null}</div></div>}
        </section>

        {historyOpen ? <aside className="absolute inset-y-0 right-0 z-30 flex w-full max-w-sm flex-col border-l bg-canvas shadow-elevated" aria-label="Version history">
          <div className="flex items-center justify-between border-b px-5 py-4"><h2 className="section-title text-xl">Version history</h2><button className="button-ghost !px-2" onClick={() => setHistoryOpen(false)} aria-label="Close history"><X size={18} /></button></div>
          <div className="flex-1 overflow-auto p-5">
            <p className="mb-5 text-sm text-muted">Normal saves update this version. A new version preserves a point in this lineage.</p>
            {history.isPending ? <p className="text-sm text-muted" role="status">Loading history…</p> : null}
            {history.isError ? <p className="text-sm text-danger" role="alert">{history.error.message}</p> : null}
            <ol className="space-y-2">{history.data?.map(item => <li key={item.id}><button className={`w-full rounded-lg border p-3 text-left hover:border-accent ${item.id === versionId ? 'bg-accent-soft' : 'bg-surface'}`} onClick={() => openVersion(item.id)}><span className="flex items-center justify-between gap-3 text-sm font-semibold"><span>{item.id === versionId ? 'Current version' : new Date(item.created_at).toLocaleString()}</span>{item.has_pdf ? <Check className="text-success" size={15} /> : null}</span><span className="mt-1 block text-xs capitalize text-muted">{item.status.replace('_', ' ')} · {item.id.slice(0, 8)}</span></button></li>)}</ol>
          </div>
        </aside> : null}
      </main>
    </div>
  )
}
