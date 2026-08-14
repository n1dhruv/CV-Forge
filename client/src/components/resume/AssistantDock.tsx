"use client"

import { ChevronDown, ChevronUp, LoaderCircle, RotateCcw, Sparkles, X } from 'lucide-react'
import dynamic from 'next/dynamic'
import { FormEvent } from 'react'
import type { AssistantProposal } from '@/lib/types'

const DiffEditor = dynamic(
  () => import('@monaco-editor/react').then(module => module.DiffEditor),
  { ssr: false, loading: () => <div className="grid h-52 place-items-center text-sm text-muted" role="status">Loading comparison…</div> },
)

interface AssistantDockProps {
  expanded: boolean
  instruction: string
  pending: boolean
  error?: Error | null
  proposal?: (AssistantProposal & { baseSource: string }) | null
  stale: boolean
  applied: boolean
  undoAvailable: boolean
  theme: 'light' | 'dark'
  disabled?: boolean
  onToggle: () => void
  onInstructionChange: (value: string) => void
  onSubmit: () => void
  onApply: () => void
  onDiscard: () => void
  onUndo: () => void
}

export function AssistantDock(props: AssistantDockProps) {
  function submit(event: FormEvent) {
    event.preventDefault()
    props.onSubmit()
  }

  return (
    <section className="no-print shrink-0 border-t bg-canvas" aria-labelledby="assistant-title">
      <button className="flex min-h-12 w-full items-center justify-between gap-4 px-4 text-left hover:bg-surface md:px-5" type="button" aria-expanded={props.expanded} aria-controls="assistant-panel" onClick={props.onToggle}>
        <span className="flex items-center gap-2 text-sm font-semibold"><Sparkles className="text-accent" size={16} aria-hidden="true" /><span id="assistant-title">Resume assistant</span></span>
        <span className="flex items-center gap-2 text-xs text-muted">Preview changes before applying {props.expanded ? <ChevronDown size={16} aria-hidden="true" /> : <ChevronUp size={16} aria-hidden="true" />}</span>
      </button>

      {props.expanded ? (
        <div id="assistant-panel" className="max-h-[48vh] overflow-auto border-t">
          <form className="flex flex-col gap-3 p-4 sm:flex-row sm:items-end md:px-5" onSubmit={submit}>
            <label className="min-w-0 flex-1 text-sm font-semibold" htmlFor="assistant-command">
              What should change?
              <textarea id="assistant-command" className="field mt-2 min-h-20 resize-y py-3 font-normal" maxLength={4000} placeholder="Make the project impact clearer without adding new claims." value={props.instruction} onChange={event => props.onInstructionChange(event.target.value)} />
            </label>
            <button className="button-primary shrink-0" type="submit" disabled={!props.instruction.trim() || props.pending || props.disabled}>
              {props.pending ? <LoaderCircle className="animate-spin" size={16} aria-hidden="true" /> : <Sparkles size={16} aria-hidden="true" />}
              {props.pending ? 'Preparing…' : 'Preview proposal'}
            </button>
          </form>

          <div className="px-4 pb-4 md:px-5" aria-live="polite">
            {props.pending ? <p className="text-sm text-muted" role="status">Saving current source if needed, then preparing a reviewable proposal…</p> : null}
            {props.error ? <p className="text-sm text-danger" role="alert">{props.error.message} No assistant changes were applied.</p> : null}
            {props.applied ? (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-accent-soft p-3 text-sm">
                <p><strong>Applied to the editor buffer.</strong> Save or recompile when you are ready.</p>
                {props.undoAvailable ? <button className="button-secondary !min-h-10" type="button" onClick={props.onUndo}><RotateCcw size={15} aria-hidden="true" /> Undo</button> : null}
              </div>
            ) : null}
          </div>

          {props.proposal ? (
            <div className="border-t">
              <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 md:px-5">
                <p className="max-w-3xl text-sm text-muted">{props.proposal.message}</p>
                <div className="flex gap-2">
                  <button className="button-ghost !min-h-10" type="button" onClick={props.onDiscard}><X size={15} aria-hidden="true" /> Discard</button>
                  <button className="button-primary !min-h-10" type="button" disabled={props.stale} onClick={props.onApply}>Apply to editor</button>
                </div>
              </div>
              {props.stale ? <p className="border-y bg-warning/10 px-4 py-2 text-sm font-medium text-ink md:px-5" role="alert">The source changed while this proposal was pending. Discard it and request a new proposal.</p> : null}
              <div className="h-64 min-h-52" aria-label="Proposed source comparison">
                <DiffEditor original={props.proposal.baseSource} modified={props.proposal.tex_source} language="latex" theme={props.theme === 'dark' ? 'vs-dark' : 'vs'} options={{ automaticLayout: true, fontFamily: 'IBM Plex Mono, monospace', fontSize: 12, lineHeight: 20, minimap: { enabled: false }, readOnly: true, renderSideBySide: true, scrollBeyondLastLine: false, wordWrap: 'on' }} />
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}
