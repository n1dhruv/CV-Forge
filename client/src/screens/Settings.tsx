import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, KeyRound, Save, Trash2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ModelProviderPicker, type ModelSelection } from '../components/ModelProviderPicker'
import { PageHeader } from '../components/PageHeader'
import { ScreenState } from '../components/ScreenState'
import { useApi } from '../hooks/useApi'
import { ApiError } from '../lib/api'
import type { LLMSettings, LLMSettingsInput, SupportedModels } from '../lib/types'

export function Settings() {
  const api = useApi()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [testResult, setTestResult] = useState<{ kind: 'chat' | 'embedding'; success: boolean; error: string | null } | null>(null)
  const [confirmRemove, setConfirmRemove] = useState(false)
  const supported = useQuery({ queryKey: ['supported-models'], queryFn: api.llmSettings.supportedModels })
  const supportedEmbeddings = useQuery({ queryKey: ['supported-embedding-models'], queryFn: api.llmSettings.supportedEmbeddingModels })
  const current = useQuery({
    queryKey: ['llm-settings'],
    queryFn: api.llmSettings.get,
    retry: (count, error) => error instanceof ApiError && error.status === 404 ? false : count < 1,
  })
  const notConfigured = current.error instanceof ApiError && current.error.status === 404
  const save = useMutation({
    mutationFn: api.llmSettings.save,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['llm-settings'] })
      setEditing(false)
      setTestResult(null)
    },
  })
  const remove = useMutation({
    mutationFn: api.llmSettings.remove,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['llm-settings'] })
      setConfirmRemove(false)
      setEditing(false)
      setTestResult(null)
    },
  })
  const test = useMutation({
    mutationFn: api.llmSettings.test,
    onSuccess: result => setTestResult({ kind: 'chat', ...result }),
    onError: error => setTestResult({ kind: 'chat', success: false, error: error.message }),
  })
  const testEmbedding = useMutation({
    mutationFn: api.llmSettings.testEmbedding,
    onSuccess: result => setTestResult({ kind: 'embedding', ...result }),
    onError: error => setTestResult({ kind: 'embedding', success: false, error: error.message }),
  })

  if (current.isPending) return <div className="px-5 py-8 md:px-10 xl:px-16"><ScreenState kind="loading" title="Loading Provider Settings…" detail="Checking your saved configuration."/></div>
  if (!notConfigured && current.isError) return <div className="px-5 py-8 md:px-10 xl:px-16"><ScreenState kind="error" title="Settings Unavailable" detail={current.error.message || 'Try loading settings again.'} onRetry={() => void current.refetch()}/></div>

  const configured = current.data
  return <div className="page-enter px-5 py-8 md:px-10 md:py-12 xl:px-16">
    <PageHeader eyebrow="Bring your own key" title="LLM Settings" description="ResumeForge has no shared AI budget. Your provider bills only your usage, and your saved key is never shown again."/>
    {configured && !editing ? <SavedSettings
      settings={configured}
      testPending={test.isPending}
      embeddingTestPending={testEmbedding.isPending}
      testResult={testResult}
      onTest={() => test.mutate()}
      onTestEmbedding={() => testEmbedding.mutate()}
      onEdit={() => setEditing(true)}
      confirmRemove={confirmRemove}
      onConfirmRemove={() => setConfirmRemove(true)}
      onCancelRemove={() => setConfirmRemove(false)}
      onRemove={() => remove.mutate()}
      removePending={remove.isPending}
    /> : <SettingsForm
      supported={supported.data ?? {}}
      supportedPending={supported.isPending}
      supportedError={supported.error?.message}
      onRetrySupported={() => void supported.refetch()}
      supportedEmbeddings={supportedEmbeddings.data ?? {}}
      embeddingsPending={supportedEmbeddings.isPending}
      embeddingsError={supportedEmbeddings.error?.message}
      onRetryEmbeddings={() => void supportedEmbeddings.refetch()}
      current={configured}
      pending={save.isPending}
      error={save.error?.message}
      onCancel={configured ? () => setEditing(false) : undefined}
      onSave={values => save.mutate(values)}
    />}
  </div>
}

interface SavedSettingsProps {
  settings: LLMSettings
  testPending: boolean
  embeddingTestPending: boolean
  testResult: { kind: 'chat' | 'embedding'; success: boolean; error: string | null } | null
  onTest: () => void
  onTestEmbedding: () => void
  onEdit: () => void
  confirmRemove: boolean
  onConfirmRemove: () => void
  onCancelRemove: () => void
  onRemove: () => void
  removePending: boolean
}

function SavedSettings({ settings, testPending, embeddingTestPending, testResult, onTest, onTestEmbedding, onEdit, confirmRemove, onConfirmRemove, onCancelRemove, onRemove, removePending }: SavedSettingsProps) {
  return <section className="max-w-3xl border-y py-7">
    <div className="grid gap-8 md:grid-cols-2">
      <SavedConfiguration title="Chat & Completions" provider={settings.provider} model={settings.model} maskedKey={settings.masked_key} onTest={onTest} testPending={testPending}/>
      <SavedConfiguration title="Embedding provider (for matching)" provider={settings.embedding_provider} model={settings.embedding_model} maskedKey={settings.masked_embedding_key} onTest={onTestEmbedding} testPending={embeddingTestPending}/>
    </div>
    <div className="mt-8 flex flex-wrap gap-2">
      <button className="button-secondary" onClick={onEdit}>Update Settings</button>
      {confirmRemove ? <><button className="button-ghost text-danger" onClick={onRemove} disabled={removePending}><Trash2 size={16} aria-hidden="true"/>{removePending ? 'Removing…' : 'Confirm Remove'}</button><button className="button-ghost" onClick={onCancelRemove}>Keep Settings</button></> : <button className="button-ghost text-danger" onClick={onConfirmRemove}><Trash2 size={16} aria-hidden="true"/>Remove Settings</button>}
    </div>
    {testResult ? <p className={`mt-5 flex items-start gap-2 text-sm ${testResult.success ? 'text-success' : 'text-danger'}`} role="status" aria-live="polite">{testResult.success ? <Check size={16} className="mt-0.5 shrink-0" aria-hidden="true"/> : <X size={16} className="mt-0.5 shrink-0" aria-hidden="true"/>}{testResult.success ? `${testResult.kind === 'embedding' ? 'Embedding' : 'Chat'} connection works.` : testResult.error || 'The provider rejected the connection. Check the model and API key.'}</p> : null}
  </section>
}

function SavedConfiguration({ title, provider, model, maskedKey, onTest, testPending }: { title: string; provider?: string | null; model?: string | null; maskedKey?: string | null; onTest: () => void; testPending: boolean }) {
  return <div>
    <p className="eyebrow">{title}</p>
    {provider && model ? <div className="mt-3 border-l-2 border-accent bg-raised p-4"><p className="font-semibold capitalize">{provider}</p><p className="mt-1 break-words font-mono text-sm" translate="no">{model}</p><p className="mt-3 font-mono text-xs text-muted" translate="no">{maskedKey}</p></div> : <p className="mt-3 text-sm text-muted">Not configured. ResumeForge will try the chat provider and key; this fails for providers without embeddings, such as Anthropic.</p>}
    <button className="button-secondary mt-4" onClick={onTest} disabled={testPending}><KeyRound size={16} aria-hidden="true"/>{testPending ? 'Testing…' : 'Test Connection'}</button>
  </div>
}

interface SettingsFormProps {
  supported: SupportedModels
  supportedPending: boolean
  supportedError?: string
  onRetrySupported: () => void
  supportedEmbeddings: SupportedModels
  embeddingsPending: boolean
  embeddingsError?: string
  onRetryEmbeddings: () => void
  current?: LLMSettings
  pending: boolean
  error?: string
  onCancel?: () => void
  onSave: (value: LLMSettingsInput) => void
}

function SettingsForm({ supported, supportedPending, supportedError, onRetrySupported, supportedEmbeddings, embeddingsPending, embeddingsError, onRetryEmbeddings, current, pending, error, onCancel, onSave }: SettingsFormProps) {
  const [chat, setChat] = useState<ModelSelection | null>(current ? { provider: current.provider, model: current.model } : null)
  const [embedding, setEmbedding] = useState<ModelSelection | null>(current?.embedding_provider && current.embedding_model ? { provider: current.embedding_provider, model: current.embedding_model } : null)
  const [apiKey, setApiKey] = useState('')
  const [embeddingApiKey, setEmbeddingApiKey] = useState('')
  const [selectionError, setSelectionError] = useState('')

  useEffect(() => {
    if (chat || supportedPending) return
    const provider = Object.keys(supported)[0]
    const model = provider ? supported[provider]?.[0] : undefined
    if (provider && model) setChat({ provider, model })
  }, [chat, supported, supportedPending])

  return <form className="max-w-3xl border-y py-7" onSubmit={event => {
    event.preventDefault()
    if (!chat) {
      setSelectionError('Choose a chat provider and model before saving.')
      document.getElementById('chat-model-trigger')?.focus()
      return
    }
    const values: LLMSettingsInput = { provider: chat.provider, model: chat.model, api_key: apiKey }
    if (embedding && embeddingApiKey) Object.assign(values, {
      embedding_provider: embedding.provider,
      embedding_model: embedding.model,
      embedding_api_key: embeddingApiKey,
    })
    onSave(values)
  }}>
    <section aria-labelledby="chat-settings-title">
      <div className="mb-5"><p className="eyebrow">Required</p><h2 id="chat-settings-title" className="mt-2 section-title">Chat & Completions</h2><p className="mt-2 text-sm text-muted">Used to analyze job descriptions and generate grounded suggestions.</p></div>
      <ModelProviderPicker id="chat-model" label="Provider & Model" description="Choose the language model used for completion requests." purpose="chat" value={chat} supportedModels={supported} loading={supportedPending} error={supportedError} validationError={selectionError} onRetry={onRetrySupported} onChange={selection => { setChat(selection); setSelectionError('') }}/>
      <label className="mt-5 block text-sm font-semibold" htmlFor="api-key">API Key<input id="api-key" name="api-key" className="field mt-2 font-mono" type="password" required autoComplete="new-password" spellCheck={false} value={apiKey} onChange={event => setApiKey(event.target.value)} placeholder={current ? 'Enter a new key to update…' : 'Paste your provider API key…'}/></label>
    </section>

    <section className="mt-10 border-t pt-8" aria-labelledby="embedding-settings-title">
      <div className="mb-5"><p className="eyebrow">Optional</p><h2 id="embedding-settings-title" className="mt-2 section-title">Embedding provider (for matching)</h2><p className="mt-2 text-sm text-muted">Matching needs vector embeddings, which can come from a different provider than chat. Anthropic, for example, offers Claude for text generation but no embedding model.</p></div>
      <ModelProviderPicker id="embedding-model" label="Provider & Model" description="Choose the model used to compare your evidence with job requirements." purpose="embedding" value={embedding} supportedModels={supportedEmbeddings} loading={embeddingsPending} error={embeddingsError} onRetry={onRetryEmbeddings} onChange={setEmbedding}/>
      <label className="mt-5 block text-sm font-semibold" htmlFor="embedding-api-key">Embedding API Key <span className="font-normal text-muted">(required after choosing a model)</span><input id="embedding-api-key" name="embedding-api-key" className="field mt-2 font-mono" type="password" required={!!embedding} autoComplete="new-password" spellCheck={false} value={embeddingApiKey} onChange={event => setEmbeddingApiKey(event.target.value)} placeholder={current?.masked_embedding_key ? 'Enter a new embedding key to update…' : 'Paste an embedding provider key…'}/></label>
      {!embedding ? <p className="mt-4 border-l-2 border-line pl-4 text-sm text-muted">Leave this unset to reuse your chat provider’s key. That fallback will fail when the chat provider does not support embeddings, such as Anthropic.</p> : null}
    </section>

    {error ? <p className="mt-5 text-sm text-danger" role="alert">{error} Check both provider configurations and try again.</p> : null}
    <div className="mt-8 flex flex-wrap justify-end gap-2">{onCancel ? <button type="button" className="button-ghost" onClick={onCancel}>Cancel</button> : null}<button className="button-primary" disabled={pending}><Save size={16} aria-hidden="true"/>{pending ? 'Saving…' : 'Save API Keys'}</button></div>
  </form>
}
