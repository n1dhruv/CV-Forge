"use client"

import { AlertTriangle, Check, Info, Pencil, RotateCcw, Save, X } from 'lucide-react'
import { useState } from 'react'
import type { GuardrailFlag, ResumeBulletSelection, ResumeBulletSelectionUpdate } from '@/lib/types'

function highlighted(text: string, flags: GuardrailFlag[]) {
  const terms = flags.map(flag => flag.term).filter(term => term && text.toLocaleLowerCase().includes(term.toLocaleLowerCase()))
  if (!terms.length) return text
  const escaped = terms.map(term => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const pattern = new RegExp(`(${escaped.join('|')})`, 'gi')
  return text.split(pattern).map((part, index) =>
    terms.some(term => term.toLocaleLowerCase() === part.toLocaleLowerCase())
      ? <mark className="rounded-sm bg-warning/25 px-0.5 text-ink" key={`${part}-${index}`}>{part}</mark>
      : part,
  )
}

export function RewriteBulletCard({
  bullet,
  busy,
  readOnly = false,
  onUpdate,
  onEditingChange,
}: {
  bullet: ResumeBulletSelection
  busy: boolean
  readOnly?: boolean
  onUpdate: (id: string, payload: ResumeBulletSelectionUpdate) => Promise<void>
  onEditingChange: (id: string, editing: boolean) => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(bullet.rewritten_text ?? bullet.original_text)
  const [editError, setEditError] = useState('')
  const flagged = bullet.flagged_terms.length > 0
  const reverted = bullet.resolved && !bullet.approved

  function cancelEdit() {
    setDraft(bullet.rewritten_text ?? bullet.original_text)
    setEditError('')
    setEditing(false)
    onEditingChange(bullet.id, false)
  }

  async function saveEdit() {
    setEditError('')
    try {
      await onUpdate(bullet.id, { rewritten_text: draft.trim() })
      setEditing(false)
      onEditingChange(bullet.id, false)
    } catch (error) {
      setEditError(error instanceof Error ? error.message : 'The edit could not be saved.')
    }
  }

  function beginEdit() {
    setEditError('')
    setDraft(bullet.rewritten_text ?? bullet.original_text)
    setEditing(true)
    onEditingChange(bullet.id, true)
  }

  return (
    <article className="border-b py-8 last:border-b-0" aria-labelledby={`bullet-${bullet.id}`}>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h2 id={`bullet-${bullet.id}`} className="font-display text-xl font-medium">Bullet {bullet.section_order + 1}</h2>
        <span className={`text-xs font-semibold uppercase tracking-wider ${
          editing ? 'text-accent' : bullet.approved ? 'text-success' : reverted ? 'text-muted' : flagged ? 'text-warning' : 'text-accent'
        }`}>
          {editing ? 'Editing — not approved' : bullet.approved ? 'Approved' : reverted ? 'Original retained' : flagged ? 'Review required' : 'Awaiting your decision'}
        </span>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <section className="rounded-xl bg-raised p-5" aria-label="Original bullet">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">Original — source truth</p>
          <p className="leading-relaxed text-ink/90">{bullet.original_text}</p>
        </section>
        <section className={`rounded-xl border p-5 ${flagged && !bullet.resolved ? 'border-warning/50 bg-warning/5' : 'bg-surface'}`} aria-label="Proposed rewrite">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">
            {editing ? 'Edited draft' : bullet.approved ? 'Approved wording' : reverted ? 'Original retained' : 'Proposed — not approved'}
          </p>
          {editing ? (
            <textarea
              className="min-h-36 w-full rounded-lg border bg-canvas px-4 py-3 leading-relaxed text-ink"
              value={draft}
              onChange={event => setDraft(event.target.value)}
              aria-label="Edit rewritten bullet"
            />
          ) : (
            <>
              {bullet.rewritten_text === bullet.original_text && flagged && !bullet.resolved ? (
                <div className="mb-4 rounded-md bg-warning/20 px-3 py-2 text-sm font-medium text-warning-dark">
                  AI rewrite discarded — it introduced a number not in your original text.
                </div>
              ) : null}
              <p className="leading-relaxed text-ink/90">{highlighted(bullet.rewritten_text ?? bullet.original_text, bullet.flagged_terms)}</p>
            </>
          )}
        </section>
      </div>

      {bullet.low_effort_rewrite && !editing && !reverted ? (
        <div className="mt-4 flex gap-3 rounded-lg bg-raised px-4 py-3 text-sm text-muted" role="note">
          <Info className="mt-0.5 shrink-0 text-accent" size={17} aria-hidden="true" />
          <p>
            AI made only minor changes here — consider editing manually if you want it more tailored.
          </p>
        </div>
      ) : null}

      {flagged ? (
        <div className="mt-4 flex gap-3 rounded-lg bg-warning/10 px-4 py-3 text-sm text-ink">
          <AlertTriangle className="mt-0.5 shrink-0 text-warning" size={17} aria-hidden="true" />
          <div>
            <p className="font-semibold">{bullet.resolved ? 'Flag reviewed individually.' : 'This proposal needs individual review.'}</p>
            <ul className="mt-1 space-y-1 text-muted">
              {bullet.flagged_terms.map((flag, index) => <li key={`${flag.reason}-${flag.term}-${index}`}>{flag.term ? `${flag.term}: ` : ''}{flag.message}</li>)}
            </ul>
          </div>
        </div>
      ) : null}

      {editError ? <p className="mt-4 text-sm font-medium text-danger" role="alert">{editError}</p> : null}
      {!readOnly ? <div className="mt-5 flex flex-wrap gap-2">
        {editing ? (
          <>
            <button className="button-primary" type="button" disabled={busy || !draft.trim()} onClick={() => void saveEdit()}>
              <Save size={15} aria-hidden="true" /> Save edit
            </button>
            <button className="button-ghost" type="button" disabled={busy} onClick={cancelEdit}>
              <X size={15} aria-hidden="true" /> Cancel
            </button>
          </>
        ) : (
          <>
            <button className="button-primary" type="button" disabled={busy || bullet.approved} onClick={() => void onUpdate(bullet.id, { approved: true })}>
              <Check size={15} aria-hidden="true" /> Approve
            </button>
            <button className="button-secondary" type="button" disabled={busy} onClick={beginEdit}>
              <Pencil size={15} aria-hidden="true" /> Edit
            </button>
            <button className="button-ghost" type="button" disabled={busy || reverted} onClick={() => void onUpdate(bullet.id, { revert: true })}>
              <RotateCcw size={15} aria-hidden="true" /> Revert to original
            </button>
          </>
        )}
      </div> : null}
    </article>
  )
}
