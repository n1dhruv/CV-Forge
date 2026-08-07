import { Check, ChevronRight, Search, Settings2, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import type { SupportedModels } from '@/lib/types'

export interface ModelSelection {
  provider: string
  model: string
}

interface ModelProviderPickerProps {
  id: string
  label: string
  description: string
  purpose: 'chat' | 'embedding'
  value: ModelSelection | null
  supportedModels: SupportedModels
  loading: boolean
  error?: string
  validationError?: string
  onRetry: () => void
  onChange: (selection: ModelSelection) => void
}

const preferredProviders = ['openai', 'anthropic', 'google']

const providerDetails: Record<string, { name: string; detail: string }> = {
  openai: { name: 'OpenAI', detail: 'GPT & embedding models' },
  anthropic: { name: 'Anthropic', detail: 'Claude language models' },
  google: { name: 'Google', detail: 'Gemini models' },
  custom: { name: 'Custom', detail: 'Any supported provider' },
}

function providerName(provider: string) {
  return providerDetails[provider]?.name ?? provider.charAt(0).toUpperCase() + provider.slice(1)
}

function modelHint(model: string, provider: string) {
  const value = model.toLowerCase()
  if (value.includes('embedding')) return 'Designed for vector representations.'
  if (/(mini|haiku|flash)/.test(value)) return 'Lighter-weight model option.'
  if (/(pro|sonnet|4o)/.test(value)) return 'General-purpose model option.'
  return `Available from ${providerName(provider)}.`
}

function fuzzyMatch(value: string, query: string) {
  const source = value.toLowerCase()
  const needle = query.trim().toLowerCase()
  if (!needle || source.includes(needle)) return true
  let cursor = 0
  for (const character of source) if (character === needle[cursor]) cursor += 1
  return cursor === needle.length
}

export function ModelProviderPicker({
  id,
  label,
  description,
  purpose,
  value,
  supportedModels,
  loading,
  error,
  validationError,
  onRetry,
  onChange,
}: ModelProviderPickerProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const customProviderRef = useRef<HTMLInputElement>(null)
  const [open, setOpen] = useState(false)
  const [provider, setProvider] = useState('openai')
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const [customProvider, setCustomProvider] = useState('')
  const [customModel, setCustomModel] = useState('')

  const providers = useMemo(() => {
    const extras = Object.keys(supportedModels).filter(item => !preferredProviders.includes(item))
    return [...preferredProviders, ...extras, 'custom']
  }, [supportedModels])
  const filteredModels = useMemo(
    () => (supportedModels[provider] ?? []).filter(model => fuzzyMatch(model, query)),
    [provider, query, supportedModels],
  )
  const embeddingUnavailable = purpose === 'embedding' && provider === 'anthropic'

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (open) {
      document.body.style.overflow = 'hidden'
      if (!dialog.open) {
        const curated = !!value && supportedModels[value.provider]?.includes(value.model)
        const initialProvider = value ? (curated ? value.provider : 'custom') : preferredProviders[0]
        setProvider(initialProvider)
        setQuery('')
        setActiveIndex(0)
        setCustomProvider(value && !curated ? value.provider : '')
        setCustomModel(value && !curated ? value.model : '')
        dialog.showModal()
        window.setTimeout(() => {
          if (window.matchMedia('(min-width: 640px)').matches) searchRef.current?.focus()
        })
      }
    } else if (!open && dialog.open) {
      dialog.close()
    }
    return () => { document.body.style.overflow = '' }
  }, [open, supportedModels, value])

  useEffect(() => {
    setActiveIndex(0)
  }, [provider, query])

  useEffect(() => {
    if (!open || provider === 'custom') return
    document.getElementById(`${id}-model-${activeIndex}`)?.scrollIntoView({ block: 'nearest' })
  }, [activeIndex, id, open, provider])

  function close() {
    setOpen(false)
    document.body.style.overflow = ''
  }

  function chooseModel(model: string) {
    onChange({ provider, model })
    close()
  }

  function handleKeys(event: KeyboardEvent<HTMLDialogElement>) {
    const target = event.target as HTMLElement
    const typing = target.tagName === 'INPUT'
    if (event.key === '/' && !typing) {
      event.preventDefault()
      searchRef.current?.focus()
      return
    }
    if (provider === 'custom' || embeddingUnavailable || !filteredModels.length) return
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const direction = event.key === 'ArrowDown' ? 1 : -1
      setActiveIndex(index => (index + direction + filteredModels.length) % filteredModels.length)
      searchRef.current?.focus()
    }
    if (event.key === 'Enter' && target === searchRef.current) {
      event.preventDefault()
      chooseModel(filteredModels[activeIndex])
    }
  }

  const selectedProvider = value ? providerName(value.provider) : 'No model selected'

  return <div>
    <div className="mb-2 flex items-end justify-between gap-4">
      <div><p className="text-sm font-semibold">{label}</p><p className="mt-1 text-sm text-muted">{description}</p></div>
    </div>
    <button
      id={`${id}-trigger`}
      type="button"
      className="flex min-h-16 w-full touch-manipulation items-center justify-between gap-4 rounded-lg border bg-raised px-4 py-3 text-left transition-colors hover:border-accent hover:bg-surface"
      aria-haspopup="dialog"
      aria-expanded={open}
      aria-describedby={validationError ? `${id}-validation` : undefined}
      onClick={() => setOpen(true)}
    >
      <span className="min-w-0"><span className="block text-xs font-semibold uppercase tracking-[.14em] text-muted">{selectedProvider}</span><span className="mt-1 block truncate font-mono text-sm" translate="no">{value?.model ?? 'Choose a provider and model'}</span></span>
      <span className="flex shrink-0 items-center gap-1 text-sm font-semibold text-accent">{value ? 'Change' : 'Choose'}<ChevronRight size={16} aria-hidden="true"/></span>
    </button>
    {validationError ? <p id={`${id}-validation`} className="mt-2 text-sm text-danger" role="alert">{validationError}</p> : null}

    <dialog
      ref={dialogRef}
      className="m-0 h-[100dvh] max-h-none w-full max-w-none overflow-hidden bg-raised p-0 text-ink shadow-quiet backdrop:bg-ink/50 sm:m-auto sm:h-auto sm:max-h-[min(44rem,calc(100dvh-3rem))] sm:w-[min(56rem,calc(100vw-3rem))] sm:rounded-xl sm:border"
      aria-labelledby={`${id}-title`}
      onCancel={close}
      onClose={() => setOpen(false)}
      onKeyDown={handleKeys}
    >
      <div className="flex h-full max-h-[inherit] flex-col overscroll-contain">
        <header className="flex items-start justify-between gap-4 border-b px-5 py-4 sm:px-6">
          <div><p className="eyebrow">{purpose === 'chat' ? 'Chat Configuration' : 'Embedding Configuration'}</p><h2 id={`${id}-title`} className="mt-1 font-display text-2xl font-medium">Choose a Model</h2></div>
          <button type="button" className="button-ghost -mr-2 touch-manipulation" aria-label="Close model picker" onClick={close}><X size={20} aria-hidden="true"/></button>
        </header>

        <div className="grid min-h-0 flex-1 grid-rows-[auto_minmax(0,1fr)] sm:grid-cols-[13rem_1fr] sm:grid-rows-1">
          <nav className="flex gap-2 overflow-x-auto border-b bg-surface p-3 sm:flex-col sm:overflow-visible sm:border-b-0 sm:border-r" aria-label="Model providers">
            {providers.map(item => {
              const details = providerDetails[item] ?? { name: providerName(item), detail: 'Curated models' }
              const unavailable = purpose === 'embedding' && item === 'anthropic'
              return <button
                type="button"
                key={item}
                className={`min-w-max touch-manipulation rounded-lg border px-3 py-2 text-left transition-colors sm:min-w-0 ${provider === item ? 'border-accent bg-accent-soft text-ink' : 'border-transparent text-muted hover:border-line hover:bg-raised hover:text-ink'}`}
                aria-pressed={provider === item}
                onClick={() => { setProvider(item); if (item === 'custom') window.setTimeout(() => customProviderRef.current?.focus()) }}
              >
                <span className="block text-sm font-semibold">{details.name}</span>
                <span className="mt-0.5 hidden text-xs sm:block">{unavailable ? 'No embedding support' : details.detail}</span>
              </button>
            })}
          </nav>

          <section className="flex min-h-0 flex-col">
            {provider === 'custom' ? <div className="overflow-y-auto p-5 sm:p-6">
              <div className="mb-6"><p className="eyebrow">Advanced</p><h3 className="mt-2 section-title">Use a Custom Provider</h3><p className="mt-2 max-w-lg text-sm text-muted">Enter the provider identifier and exact model string accepted by your API gateway.</p></div>
              <div className="grid gap-5 sm:grid-cols-2">
                <label className="text-sm font-semibold" htmlFor={`${id}-custom-provider`}>Provider Name<input ref={customProviderRef} id={`${id}-custom-provider`} name={`${id}-custom-provider`} className="field mt-2" autoComplete="off" spellCheck={false} value={customProvider} onChange={event => setCustomProvider(event.target.value)} placeholder="mistral…"/></label>
                <label className="text-sm font-semibold" htmlFor={`${id}-custom-model`}>Model String<input id={`${id}-custom-model`} name={`${id}-custom-model`} className="field mt-2 font-mono" autoComplete="off" spellCheck={false} value={customModel} onChange={event => setCustomModel(event.target.value)} placeholder="mistral-large-latest…"/></label>
              </div>
              <button type="button" className="button-primary mt-6" disabled={!customProvider.trim() || !customModel.trim()} onClick={() => { onChange({ provider: customProvider.trim(), model: customModel.trim() }); close() }}><Settings2 size={16} aria-hidden="true"/>Use Custom Model</button>
            </div> : <>
              <div className="border-b p-4 sm:px-5">
                <label className="sr-only" htmlFor={`${id}-search`}>Search {providerName(provider)} models</label>
                <div className="flex items-center gap-3 rounded-lg border bg-surface px-3 focus-within:border-accent">
                  <Search size={17} className="shrink-0 text-muted" aria-hidden="true"/>
                  <input
                    ref={searchRef}
                    id={`${id}-search`}
                    name={`${id}-model-search`}
                    className="min-h-11 min-w-0 flex-1 bg-transparent text-sm text-ink placeholder:text-muted focus:outline-none"
                    role="combobox"
                    aria-autocomplete="list"
                    aria-expanded="true"
                    aria-controls={`${id}-models`}
                    aria-activedescendant={filteredModels.length ? `${id}-model-${activeIndex}` : undefined}
                    autoComplete="off"
                    spellCheck={false}
                    value={query}
                    onChange={event => setQuery(event.target.value)}
                    placeholder={`Search ${providerName(provider)} models…`}
                  />
                  <kbd className="hidden rounded border px-1.5 py-0.5 font-mono text-[10px] text-muted sm:block">/</kbd>
                </div>
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-3 sm:p-4">
                {loading ? <div className="space-y-2" role="status"><p className="sr-only">Loading supported models…</p>{[0, 1, 2].map(item => <div key={item} className="h-[4.5rem] animate-pulse rounded-lg border bg-surface"/>)}</div>
                  : error ? <div className="mx-auto max-w-sm py-12 text-center" role="alert"><p className="font-semibold">Models Couldn’t Load</p><p className="mt-2 text-sm text-muted">{error}</p><button type="button" className="button-secondary mt-5" onClick={onRetry}>Try Again</button></div>
                  : embeddingUnavailable ? <div className="mx-auto max-w-sm py-12 text-center" role="status"><p className="font-semibold">Anthropic Doesn’t Offer Embeddings</p><p className="mt-2 text-sm text-muted">Choose OpenAI, Google, or a custom provider for this configuration.</p></div>
                  : filteredModels.length ? <div id={`${id}-models`} role="listbox" aria-label={`${providerName(provider)} models`}>
                    {filteredModels.map((model, index) => {
                      const selected = value?.provider === provider && value.model === model
                      const active = index === activeIndex
                      return <button
                        type="button"
                        role="option"
                        aria-selected={selected}
                        id={`${id}-model-${index}`}
                        key={model}
                        className={`flex w-full touch-manipulation items-center justify-between gap-4 rounded-lg border px-4 py-3 text-left transition-colors ${active ? 'border-accent bg-accent-soft' : 'border-transparent hover:border-line hover:bg-surface'}`}
                        onMouseEnter={() => setActiveIndex(index)}
                        onClick={() => chooseModel(model)}
                      >
                        <span className="min-w-0"><span className="block break-words font-mono text-sm font-medium" translate="no">{model}</span><span className="mt-1 block text-xs text-muted">{modelHint(model, provider)}</span></span>
                        {selected ? <Check size={17} className="shrink-0 text-accent" aria-hidden="true"/> : null}
                      </button>
                    })}
                  </div> : <div className="mx-auto max-w-sm py-12 text-center" role="status"><p className="font-semibold">No Matching Models</p><p className="mt-2 text-sm text-muted">Try a different search or use a custom provider and model.</p></div>}
              </div>
            </>}
          </section>
        </div>

        <footer className="hidden border-t px-6 py-3 text-xs text-muted sm:flex sm:justify-between"><span>↑↓ Navigate · Enter Select</span><span>Esc Close</span></footer>
        <div className="border-t [padding-bottom:env(safe-area-inset-bottom)] sm:hidden"/>
      </div>
    </dialog>
  </div>
}
