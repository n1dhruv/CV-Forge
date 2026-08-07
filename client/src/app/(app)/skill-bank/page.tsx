"use client"

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, ChevronUp, Pencil, Plus, Save, Trash2, X } from 'lucide-react'
import { useState, useMemo } from 'react'
import Link from 'next/link'
import { usePathname, useSearchParams, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { PageHeader } from '@/components/PageHeader'
import { ScreenState } from '@/components/ScreenState'
import { useApi } from '@/hooks/useApi'
import { Reveal } from '@/components/motion/Reveal'
import { Stagger, StaggerItem } from '@/components/motion/Stagger'
import { DURATION, EASE } from '@/lib/motion'
import type { BulletPoint, BulletPointInput, ItemType, SkillBankItem, SkillBankItemInput } from '@/lib/types'

const labels: Record<ItemType, string> = { experience: 'Experience', project: 'Projects', skill: 'Skills', education: 'Education', certification: 'Certifications' }
const singular: Record<ItemType, string> = { experience: 'experience', project: 'project', skill: 'skill', education: 'education', certification: 'certification' }
const formCopy: Record<ItemType, { titleLabel: string; titlePlaceholder: string; orgLabel: string; orgPlaceholder: string; notesPlaceholder: string; ongoingLabel: string }> = {
  experience: { titleLabel: 'Role / title', titlePlaceholder: 'Product Engineer', orgLabel: 'Organization', orgPlaceholder: 'Company or team', notesPlaceholder: 'Scope, responsibilities, and verified outcomes…', ongoingLabel: 'I currently work here' },
  project: { titleLabel: 'Project name', titlePlaceholder: 'ResumeForge', orgLabel: 'Organization', orgPlaceholder: 'Company, client, or independent', notesPlaceholder: 'Problem, contribution, stack, and verified outcomes…', ongoingLabel: 'This project is active' },
  skill: { titleLabel: 'Skill name', titlePlaceholder: 'Python', orgLabel: '', orgPlaceholder: '', notesPlaceholder: 'Where you used this skill and the evidence that supports it…', ongoingLabel: '' },
  education: { titleLabel: 'Qualification', titlePlaceholder: 'B.Tech, Computer Science', orgLabel: 'School / institution', orgPlaceholder: 'University or institution', notesPlaceholder: 'Relevant coursework, honours, or focus areas…', ongoingLabel: 'I am currently studying here' },
  certification: { titleLabel: 'Certification', titlePlaceholder: 'AWS Solutions Architect', orgLabel: 'Issuer', orgPlaceholder: 'Issuing organization', notesPlaceholder: 'Credential ID, focus, or verification details…', ongoingLabel: 'This credential does not expire' },
}
const types = Object.keys(labels) as ItemType[]
const date = new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short' })
const formatDate = (value: string | null) => (value ? date.format(new Date(`${value}T00:00:00`)) : 'Present')

export default function SkillBank() {
  const api = useApi()
  const queryClient = useQueryClient()
  const pathname = usePathname()
  const params = useSearchParams()
  const router = useRouter()
  const [expanded, setExpanded] = useState<string | null>(null)
  const [editing, setEditing] = useState<SkillBankItem | 'new' | null>(null)

  const importedCountStr = params.get('importedCount')
  const imported = importedCountStr ? { importedCount: parseInt(importedCountStr, 10), importedIds: [] as string[] } : null
  const requestedType = params.get('type')
  const tab = types.includes(requestedType as ItemType) ? (requestedType as ItemType) : 'experience'

  const items = useQuery({ queryKey: ['skill-bank'], queryFn: () => api.skillBank.list() })

  const create = useMutation({
    mutationFn: api.skillBank.create,
    onSuccess: async (item) => {
      await queryClient.invalidateQueries({ queryKey: ['skill-bank'] })
      setEditing(null)
      setExpanded(item.id)
    },
  })

  const update = useMutation({
    mutationFn: ({ id, value }: { id: string; value: SkillBankItemInput }) => api.skillBank.update(id, value),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['skill-bank'] })
      setEditing(null)
    },
  })

  if (items.isPending) {
    return (
      <div className="container-normal py-10 md:py-12">
        <ScreenState kind="loading" title="Loading your skill bank…" detail="Gathering your saved evidence." />
      </div>
    )
  }

  if (items.isError) {
    return (
      <div className="container-normal py-10 md:py-12">
        <ScreenState kind="error" title="Skill bank unavailable" detail={items.error.message} onRetry={() => void items.refetch()} />
      </div>
    )
  }

  const visible = items.data.filter((item) => item.type === tab)

  return (
    <div className="container-normal py-10 md:py-12">
      <PageHeader
        eyebrow="Evidence library"
        title="Skill Bank"
        description="Store the facts once. Tag each proof point so matching stays precise."
        action={
          <button className="button-primary" onClick={() => setEditing('new')}>
            <Plus size={16} aria-hidden="true" />
            Add {singular[tab]}
          </button>
        }
      />

      <Reveal variant="down" delay={0.1}>
        <AnimatePresence>
          {imported?.importedCount && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="mb-8 overflow-hidden"
            >
              <div className="border-l-2 border-success bg-success/5 px-5 py-4 text-sm text-success" role="status">
                <strong>{imported.importedCount} {imported.importedCount === 1 ? 'item' : 'items'} imported.</strong> Your reviewed evidence is now in the Skill Bank.
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </Reveal>

      {/* Tabs */}
      <Reveal variant="fade" delay={0.15}>
        <div role="tablist" aria-label="Skill bank sections" className="mb-8 flex gap-2 overflow-x-auto no-scrollbar border-b pb-1">
          {types.map((type) => {
            const active = tab === type
            return (
              <button
                key={type}
                role="tab"
                aria-selected={active}
                onClick={() => {
                  router.replace(`/skill-bank?type=${type}`)
                  setExpanded(null)
                }}
                className={`relative min-h-11 shrink-0 px-4 text-sm font-semibold transition-colors ${
                  active ? 'text-ink' : 'text-muted hover:text-ink'
                }`}
              >
                {labels[type]}
                <span className="ml-1.5 font-mono text-[11px] tabular-nums bg-surface px-1.5 py-0.5 rounded-full">
                  {items.data.filter((item) => item.type === type).length}
                </span>
                {active && (
                  <motion.div
                    layoutId="activeTab"
                    className="absolute inset-x-0 -bottom-[5px] h-0.5 bg-accent"
                    transition={{ duration: DURATION.fast, ease: EASE.outExpo }}
                  />
                )}
              </button>
            )
          })}
        </div>
      </Reveal>

      <AnimatePresence>
        {editing && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 md:p-12">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="absolute inset-0 bg-canvas/80 backdrop-blur-sm"
              onClick={() => setEditing(null)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ duration: 0.2, ease: EASE.outExpo }}
              className="relative w-full max-w-2xl max-h-full overflow-y-auto"
            >
              <ItemForm
                initial={editing === 'new' ? undefined : editing}
                type={tab}
                pending={create.isPending || update.isPending}
                error={(create.error ?? update.error)?.message}
                onClose={() => setEditing(null)}
                onSave={(value) => (editing === 'new' ? create.mutate(value) : update.mutate({ id: editing.id, value }))}
              />
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      <Reveal delay={0.2} className="min-h-[50vh]">
        {!visible.length ? (
          <div className="grid min-h-72 place-items-center rounded-xl border border-dashed bg-surface/50 text-center">
            <div className="p-8">
              <p className="font-display text-2xl md:text-3xl">No {labels[tab].toLowerCase()} yet.</p>
              <p className="mt-3 text-sm text-muted">Add the source material that future resumes can draw from.</p>
              <div className="mt-6 flex flex-wrap justify-center gap-3">
                <button className="button-primary" onClick={() => setEditing('new')}>
                  <Plus size={16} aria-hidden="true" /> Create First Entry
                </button>
                <Link className="button-secondary" href="/resume-import">
                  Import Existing Resume
                </Link>
              </div>
            </div>
          </div>
        ) : (
          <Stagger className="space-y-3" staggerDelay={0.05}>
            {visible.map((item) => (
              <StaggerItem key={item.id}>
                <ItemRow
                  item={item}
                  highlighted={imported?.importedIds?.includes(item.id) ?? false}
                  open={expanded === item.id}
                  onToggle={() => setExpanded(expanded === item.id ? null : item.id)}
                  onEdit={() => setEditing(item)}
                />
              </StaggerItem>
            ))}
          </Stagger>
        )}
      </Reveal>
    </div>
  )
}

function ItemRow({ item, highlighted, open, onToggle, onEdit }: { item: SkillBankItem; highlighted: boolean; open: boolean; onToggle: () => void; onEdit: () => void }) {
  const api = useApi()
  const queryClient = useQueryClient()
  const [confirmDelete, setConfirmDelete] = useState(false)

  const detail = useQuery({
    queryKey: ['skill-bank', item.id],
    queryFn: () => api.skillBank.get(item.id),
    enabled: open,
  })

  const remove = useMutation({
    mutationFn: () => api.skillBank.delete(item.id),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['skill-bank'] }),
  })

  return (
    <article
      className={`rounded-xl border bg-surface transition-all ${
        highlighted ? 'border-success ring-1 ring-success/20' : 'hover:border-accent'
      }`}
    >
      <button
        className="grid min-h-20 w-full grid-cols-[1fr_auto] items-center gap-4 px-5 py-4 text-left transition-colors sm:px-6 hover:bg-raised rounded-xl"
        aria-expanded={open}
        onClick={onToggle}
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="section-title text-[1.1rem] break-words">{item.title}</h2>
            {highlighted && <span className="tag !border-success/30 !text-success !bg-success/5">Just imported</span>}
            {!item.end_date && item.type !== 'skill' && <span className="tag !border-success/30 !text-success !bg-success/5">Current</span>}
          </div>
          <p className="mt-1 text-sm text-muted">
            {item.org || (item.type === 'skill' ? '' : 'Independent')}
            {item.start_date ? ` · ${formatDate(item.start_date)}—${formatDate(item.end_date)}` : ''}
          </p>
        </div>
        <motion.div animate={{ rotate: open ? 180 : 0 }} transition={{ duration: DURATION.fast }}>
          <ChevronDown aria-hidden="true" className="text-muted" />
        </motion.div>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: DURATION.normal, ease: EASE.outExpo }}
            className="overflow-hidden"
          >
            <div className="border-t px-5 pb-6 pt-5 sm:px-6">
              {detail.isPending ? (
                <div className="space-y-4">
                  <div className="h-4 w-3/4 animate-pulse rounded bg-raised" />
                  <div className="h-4 w-1/2 animate-pulse rounded bg-raised" />
                </div>
              ) : detail.isError ? (
                <div className="rounded-lg border border-danger/30 bg-danger/5 p-4">
                  <p className="text-sm font-semibold text-danger">Failed to load details</p>
                  <button className="button-ghost mt-2 !px-0 text-danger" onClick={() => void detail.refetch()}>Try again</button>
                </div>
              ) : (
                <>
                  <p className="mb-8 max-w-3xl whitespace-pre-wrap text-sm leading-relaxed text-muted">
                    {detail.data.raw_text || 'No supporting notes.'}
                  </p>
                  
                  <BulletList itemId={item.id} bullets={[...detail.data.bullet_points].sort((a, b) => a.display_order - b.display_order)} />
                  
                  <div className="mt-10 flex flex-wrap items-center justify-between gap-4 border-t pt-6">
                    <button className="button-secondary" onClick={onEdit}>
                      <Pencil size={15} aria-hidden="true" /> Edit Entry
                    </button>
                    
                    <div className="flex gap-2">
                      {confirmDelete ? (
                        <>
                          <button className="button-ghost" onClick={() => setConfirmDelete(false)}>Cancel</button>
                          <button className="button-primary !bg-danger" onClick={() => remove.mutate()} disabled={remove.isPending}>
                            <Trash2 size={15} aria-hidden="true" /> {remove.isPending ? 'Deleting…' : 'Confirm Delete'}
                          </button>
                        </>
                      ) : (
                        <button className="button-ghost text-danger hover:!bg-danger/10" onClick={() => setConfirmDelete(true)}>
                          <Trash2 size={15} aria-hidden="true" /> Delete Entry
                        </button>
                      )}
                    </div>
                  </div>
                  {remove.error && <p className="mt-3 text-sm text-danger" role="alert">{remove.error.message}</p>}
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </article>
  )
}

function ItemForm({ initial, type, pending, error, onClose, onSave }: { initial?: SkillBankItem; type: ItemType; pending: boolean; error?: string; onClose: () => void; onSave: (value: SkillBankItemInput) => void }) {
  const [itemType, setItemType] = useState(initial?.type ?? type)
  const [title, setTitle] = useState(initial?.title ?? '')
  const [org, setOrg] = useState(initial?.org ?? '')
  const [startDate, setStartDate] = useState(initial?.start_date ?? '')
  const [endDate, setEndDate] = useState(initial?.end_date ?? '')
  const [ongoing, setOngoing] = useState(initial ? !initial.end_date : false)
  const [rawText, setRawText] = useState(initial?.raw_text ?? '')

  const copy = formCopy[itemType]
  const compact = itemType === 'skill'

  return (
    <form
      aria-labelledby="item-form-title"
      className="rounded-xl border bg-surface shadow-2xl"
      onSubmit={(event) => {
        event.preventDefault()
        onSave({ type: itemType, title: title.trim(), org: compact ? null : org.trim() || null, start_date: compact ? null : startDate || null, end_date: compact || ongoing ? null : endDate || null, raw_text: rawText.trim() || null, tags: initial?.tags ?? [] })
      }}
    >
      <header className="flex items-center justify-between border-b px-5 py-4 sm:px-6">
        <div>
          <p className="eyebrow !mb-1">{initial ? 'Editing evidence' : 'New evidence'}</p>
          <h2 id="item-form-title" className="font-display text-2xl font-medium">
            {initial ? 'Edit' : 'Add'} {singular[itemType]}
          </h2>
        </div>
        <button type="button" className="button-ghost !px-2.5" onClick={onClose} aria-label="Close editor">
          <X size={18} aria-hidden="true" />
        </button>
      </header>

      <div className="grid gap-6 px-5 py-6 sm:grid-cols-2 sm:px-6">
        <label className="text-sm font-semibold" htmlFor="item-type">
          Evidence type
          <select id="item-type" name="type" className="field mt-2" value={itemType} onChange={(event) => setItemType(event.target.value as ItemType)}>
            {types.map((value) => (
              <option value={value} key={value}>{labels[value]}</option>
            ))}
          </select>
        </label>
        <label className="text-sm font-semibold" htmlFor="item-title">
          {copy.titleLabel}
          <input id="item-title" name="title" className="field mt-2" value={title} required autoComplete="off" onChange={(event) => setTitle(event.target.value)} placeholder={copy.titlePlaceholder} />
        </label>

        {!compact && (
          <>
            <label className="text-sm font-semibold sm:col-span-2" htmlFor="item-org">
              {copy.orgLabel}
              <input id="item-org" name="organization" className="field mt-2" value={org} autoComplete="organization" onChange={(event) => setOrg(event.target.value)} placeholder={copy.orgPlaceholder} />
            </label>
            <label className="text-sm font-semibold" htmlFor="start-date">
              Start date
              <input id="start-date" name="start-date" type="date" className="field mt-2" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
            </label>
            <label className="text-sm font-semibold" htmlFor="end-date">
              End date
              <input id="end-date" name="end-date" type="date" className="field mt-2 text-muted" value={endDate} disabled={ongoing} onChange={(event) => setEndDate(event.target.value)} />
            </label>
            <label className="flex min-h-11 items-center gap-3 text-sm font-semibold sm:col-span-2">
              <input type="checkbox" className="size-4 rounded border-line text-accent focus:ring-accent" name="ongoing" checked={ongoing} onChange={(event) => setOngoing(event.target.checked)} />
              {copy.ongoingLabel}
            </label>
          </>
        )}

        <label className="text-sm font-semibold sm:col-span-2" htmlFor="raw-text">
          Source notes <span className="font-normal text-muted">(optional)</span>
          <textarea id="raw-text" name="raw-text" className="field mt-2 min-h-24 resize-y py-3 leading-relaxed" value={rawText} onChange={(event) => setRawText(event.target.value)} placeholder={copy.notesPlaceholder} />
        </label>
        
        {error && <p className="text-sm text-danger sm:col-span-2" role="alert">{error}</p>}
      </div>

      <footer className="flex flex-wrap justify-end gap-3 border-t bg-raised/50 px-5 py-4 sm:px-6 rounded-b-xl">
        <button type="button" className="button-ghost" onClick={onClose}>Cancel</button>
        <button className="button-primary" disabled={pending || !title.trim()}>
          <Save size={16} aria-hidden="true" /> {pending ? 'Saving…' : `Save ${singular[itemType]}`}
        </button>
      </footer>
    </form>
  )
}

function BulletList({ itemId, bullets }: { itemId: string; bullets: BulletPoint[] }) {
  const api = useApi()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<BulletPoint | 'new' | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['skill-bank', itemId] })

  const create = useMutation({
    mutationFn: (value: BulletPointInput) => api.skillBank.createBullet(itemId, { ...value, display_order: Math.max(-1, ...bullets.map((b) => b.display_order)) + 1 }),
    onSuccess: async () => { await refresh(); setEditing(null) },
  })

  const update = useMutation({
    mutationFn: ({ id, value }: { id: string; value: BulletPointInput }) => api.skillBank.updateBullet(id, value),
    onSuccess: async () => { await refresh(); setEditing(null) },
  })

  const remove = useMutation({
    mutationFn: api.skillBank.deleteBullet,
    onSuccess: async () => { await refresh(); setConfirmDelete(null) },
  })

  const reorder = useMutation({
    mutationFn: async ({ bullet, index, direction }: { bullet: BulletPoint; index: number; direction: -1 | 1 }) => {
      const other = bullets[index + direction]
      await Promise.all([
        api.skillBank.updateBullet(bullet.id, { display_order: other.display_order }),
        api.skillBank.updateBullet(other.id, { display_order: bullet.display_order }),
      ])
    },
    onSuccess: refresh,
  })

  return (
    <div>
      <div className="mb-5 flex items-center justify-between">
        <h3 className="section-title text-base">Proof Points</h3>
        <button className="button-secondary !min-h-9 !px-3 text-xs" onClick={() => setEditing('new')}>
          <Plus size={14} aria-hidden="true" /> Add Point
        </button>
      </div>

      <AnimatePresence mode="wait">
        {editing && (
          <motion.div
            key="bullet-form"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: DURATION.fast }}
          >
            <BulletForm
              initial={editing === 'new' ? undefined : editing}
              pending={create.isPending || update.isPending}
              error={(create.error ?? update.error)?.message}
              onClose={() => setEditing(null)}
              onSave={(value) => (editing === 'new' ? create.mutate(value) : update.mutate({ id: editing.id, value }))}
            />
          </motion.div>
        )}
      </AnimatePresence>

      <div className="space-y-3">
        {bullets.map((bullet, index) => (
          <div className="group grid gap-4 rounded-lg border bg-surface p-4 sm:grid-cols-[1fr_auto] transition-colors hover:border-line hover:bg-raised" key={bullet.id}>
            <div className="min-w-0">
              <p className="text-sm leading-relaxed text-ink">
                <span className="mr-3 font-mono text-xs font-bold text-muted select-none">{String(index + 1).padStart(2, '0')}</span>
                {bullet.text}
              </p>
              {bullet.tags.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {bullet.tags.map((tag) => (
                    <span className="tag break-all bg-canvas" key={tag}>{tag}</span>
                  ))}
                  {bullet.metrics && (
                    <span className="tag !border-accent/30 !text-accent !bg-accent-soft break-all">{bullet.metrics}</span>
                  )}
                </div>
              )}
            </div>
            
            <div className="flex items-start opacity-0 group-hover:opacity-100 transition-opacity focus-within:opacity-100">
              <div className="flex rounded-md border bg-canvas shadow-sm">
                <button className="grid size-8 place-items-center text-muted hover:text-ink disabled:opacity-30" aria-label={`Move up`} disabled={index === 0 || reorder.isPending} onClick={() => reorder.mutate({ bullet, index, direction: -1 })}>
                  <ChevronUp size={14} />
                </button>
                <div className="w-px bg-line" />
                <button className="grid size-8 place-items-center text-muted hover:text-ink disabled:opacity-30" aria-label={`Move down`} disabled={index === bullets.length - 1 || reorder.isPending} onClick={() => reorder.mutate({ bullet, index, direction: 1 })}>
                  <ChevronDown size={14} />
                </button>
                <div className="w-px bg-line" />
                <button className="grid size-8 place-items-center text-muted hover:text-ink" aria-label={`Edit`} onClick={() => setEditing(bullet)}>
                  <Pencil size={13} />
                </button>
                <div className="w-px bg-line" />
                {confirmDelete === bullet.id ? (
                  <button className="grid size-8 place-items-center bg-danger text-white rounded-r-md" aria-label={`Confirm delete`} onClick={() => remove.mutate(bullet.id)}>
                    <Trash2 size={13} />
                  </button>
                ) : (
                  <button className="grid size-8 place-items-center text-danger hover:bg-danger/10 rounded-r-md" aria-label={`Delete`} onClick={() => setConfirmDelete(bullet.id)}>
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}

        {!bullets.length && (
          <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted">
            No proof points yet. Break down this evidence into specific, measurable achievements.
          </div>
        )}
      </div>
    </div>
  )
}

function BulletForm({ initial, pending, error, onClose, onSave }: { initial?: BulletPoint; pending: boolean; error?: string; onClose: () => void; onSave: (value: BulletPointInput) => void }) {
  const [text, setText] = useState(initial?.text ?? '')
  const [tags, setTags] = useState(initial?.tags.join(', ') ?? '')
  const [metrics, setMetrics] = useState(initial?.metrics ?? '')

  return (
    <form
      className="mb-6 rounded-lg border bg-raised p-5 shadow-sm"
      onSubmit={(event) => {
        event.preventDefault()
        onSave({ text: text.trim(), tags: tags.split(',').map((tag) => tag.trim()).filter(Boolean), metrics: metrics.trim() || null, display_order: initial?.display_order })
      }}
    >
      <label className="text-sm font-semibold" htmlFor="bullet-text">
        Proof Point
        <textarea id="bullet-text" name="bullet-text" className="field mt-2 min-h-24 resize-y py-3 leading-relaxed bg-surface" required autoComplete="off" value={text} onChange={(e) => setText(e.target.value)} placeholder="Describe the action and outcome…" />
      </label>
      <div className="mt-5 grid gap-5 sm:grid-cols-2">
        <label className="text-sm font-semibold" htmlFor="bullet-tags">
          Tags
          <input id="bullet-tags" name="bullet-tags" className="field mt-2 bg-surface" autoComplete="off" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="React, TypeScript…" />
          <span className="mt-1.5 block text-xs font-normal text-muted">Separate tags with commas.</span>
        </label>
        <label className="text-sm font-semibold" htmlFor="bullet-metrics">
          Metric
          <input id="bullet-metrics" name="bullet-metrics" className="field mt-2 bg-surface" autoComplete="off" value={metrics} onChange={(e) => setMetrics(e.target.value)} placeholder="31% reduction…" />
        </label>
      </div>
      {error && <p className="mt-4 text-sm text-danger" role="alert">{error}</p>}
      <div className="mt-6 flex justify-end gap-3">
        <button type="button" className="button-ghost" onClick={onClose}>Cancel</button>
        <button className="button-primary" disabled={pending || !text.trim()}>
          <Save size={15} aria-hidden="true" /> {pending ? 'Saving…' : 'Save Proof Point'}
        </button>
      </div>
    </form>
  )
}
