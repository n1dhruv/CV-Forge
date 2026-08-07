"use client"

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, KeyRound, Save, Trash2, X, AlertCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ModelProviderPicker, type ModelSelection } from '@/components/ModelProviderPicker'
import { PageHeader } from '@/components/PageHeader'
import { ScreenState } from '@/components/ScreenState'
import { useApi } from '@/hooks/useApi'
import { ApiError } from '@/lib/api'
import { Reveal } from '@/components/motion/Reveal'
import { DURATION, EASE } from '@/lib/motion'
import type { LLMSettings, LLMSettingsInput, SupportedModels } from '@/lib/types'

export default function Settings() {
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
    retry: (count, error) => (error instanceof ApiError && error.status === 404 ? false : count < 1),
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
    onSuccess: (result) => setTestResult({ kind: 'chat', ...result }),
    onError: (error) => setTestResult({ kind: 'chat', success: false, error: error.message }),
  })

  const testEmbedding = useMutation({
    mutationFn: api.llmSettings.testEmbedding,
    onSuccess: (result) => setTestResult({ kind: 'embedding', ...result }),
    onError: (error) => setTestResult({ kind: 'embedding', success: false, error: error.message }),
  })

  if (current.isPending) {
    return (
      <div className="container-normal py-10 md:py-12">
        <ScreenState kind="loading" title="Loading Provider Settings…" detail="Checking your saved configuration." />
      </div>
    )
  }

  if (!notConfigured && current.isError) {
    return (
      <div className="container-normal py-10 md:py-12">
        <ScreenState kind="error" title="Settings Unavailable" detail={current.error.message || 'Try loading settings again.'} onRetry={() => void current.refetch()} />
      </div>
    )
  }

  const configured = current.data

  return (
    <div className="container-normal py-10 md:py-12">
      <PageHeader
        eyebrow="Bring your own key"
        title="LLM Settings"
        description="ResumeForge has no shared AI budget. Your provider bills only your usage, and your saved key is never shown again."
      />

      <Reveal variant="up" delay={0.1}>
        <AnimatePresence mode="wait">
          {configured && !editing ? (
            <motion.div
              key="saved"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: DURATION.normal }}
            >
              <SavedSettings
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
              />
            </motion.div>
          ) : (
            <motion.div
              key="form"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: DURATION.normal }}
            >
              <SettingsForm
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
                onSave={(values: LLMSettingsInput) => save.mutate(values)}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </Reveal>
    </div>
  )
}

function SavedSettings({
  settings,
  testPending,
  embeddingTestPending,
  testResult,
  onTest,
  onTestEmbedding,
  onEdit,
  confirmRemove,
  onConfirmRemove,
  onCancelRemove,
  onRemove,
  removePending,
}: any) {
  return (
    <section className="max-w-3xl">
      <div className="grid gap-6 md:grid-cols-2">
        <SavedConfiguration title="Chat & Completions" provider={settings.provider} model={settings.model} maskedKey={settings.masked_key} onTest={onTest} testPending={testPending} />
        <SavedConfiguration title="Embedding provider (for matching)" provider={settings.embedding_provider} model={settings.embedding_model} maskedKey={settings.masked_embedding_key} onTest={onTestEmbedding} testPending={embeddingTestPending} />
      </div>

      <div className="mt-8 flex flex-wrap items-center justify-between gap-4 border-t pt-8">
        <div className="flex flex-wrap gap-3">
          <button className="button-secondary" onClick={onEdit}>
            Update Settings
          </button>
          {confirmRemove ? (
            <div className="flex gap-2">
              <button className="button-ghost" onClick={onCancelRemove}>Cancel</button>
              <button className="button-primary !bg-danger" onClick={onRemove} disabled={removePending}>
                <Trash2 size={16} aria-hidden="true" />
                {removePending ? 'Removing…' : 'Confirm Remove'}
              </button>
            </div>
          ) : (
            <button className="button-ghost text-danger hover:!bg-danger/10" onClick={onConfirmRemove}>
              <Trash2 size={16} aria-hidden="true" /> Remove
            </button>
          )}
        </div>

        <AnimatePresence>
          {testResult && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className={`flex max-w-sm items-start gap-2.5 rounded-lg border p-3 text-sm shadow-sm ${
                testResult.success ? 'border-success/30 bg-success/5 text-success' : 'border-danger/30 bg-danger/5 text-danger'
              }`}
              role="status"
              aria-live="polite"
            >
              {testResult.success ? <Check size={18} className="mt-0.5 shrink-0" aria-hidden="true" /> : <AlertCircle size={18} className="mt-0.5 shrink-0" aria-hidden="true" />}
              <span className="leading-relaxed">
                {testResult.success
                  ? `${testResult.kind === 'embedding' ? 'Embedding' : 'Chat'} connection works.`
                  : testResult.error || 'The provider rejected the connection. Check the model and API key.'}
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </section>
  )
}

function SavedConfiguration({ title, provider, model, maskedKey, onTest, testPending }: any) {
  return (
    <div className="flex h-full flex-col rounded-xl border bg-surface p-5 shadow-sm transition-colors hover:border-line hover:bg-raised">
      <p className="eyebrow !mb-1">{title}</p>
      
      <div className="flex-1 mt-4">
        {provider && model ? (
          <div className="space-y-4">
            <div>
              <p className="text-xs font-semibold text-muted">PROVIDER</p>
              <p className="font-semibold capitalize text-ink">{provider}</p>
            </div>
            <div>
              <p className="text-xs font-semibold text-muted">MODEL</p>
              <p className="font-mono text-sm text-ink bg-canvas px-2 py-1 rounded inline-block border mt-1" translate="no">{model}</p>
            </div>
            <div>
              <p className="text-xs font-semibold text-muted">API KEY</p>
              <p className="font-mono text-xs text-muted" translate="no">{maskedKey}</p>
            </div>
          </div>
        ) : (
          <div className="flex h-full items-center justify-center rounded-lg border border-dashed p-4 text-center">
            <p className="text-sm text-muted">Not configured. ResumeForge will fallback to the chat provider key.</p>
          </div>
        )}
      </div>

      <div className="mt-6 border-t pt-5">
        <button className="button-secondary w-full justify-center" onClick={onTest} disabled={testPending}>
          <KeyRound size={16} aria-hidden="true" className={testPending ? 'animate-pulse text-accent' : ''} />
          {testPending ? 'Testing connection…' : 'Test Connection'}
        </button>
      </div>
    </div>
  )
}

function SettingsForm({
  supported,
  supportedPending,
  supportedError,
  onRetrySupported,
  supportedEmbeddings,
  embeddingsPending,
  embeddingsError,
  onRetryEmbeddings,
  current,
  pending,
  error,
  onCancel,
  onSave,
}: any) {
  const [chat, setChat] = useState<ModelSelection | null>(current ? { provider: current.provider, model: current.model } : null)
  const [embedding, setEmbedding] = useState<ModelSelection | null>(
    current?.embedding_provider && current.embedding_model ? { provider: current.embedding_provider, model: current.embedding_model } : null
  )
  const [apiKey, setApiKey] = useState('')
  const [embeddingApiKey, setEmbeddingApiKey] = useState('')
  const [selectionError, setSelectionError] = useState('')

  useEffect(() => {
    if (chat || supportedPending) return
    const provider = Object.keys(supported)[0]
    const model = provider ? supported[provider]?.[0] : undefined
    if (provider && model) setChat({ provider, model })
  }, [chat, supported, supportedPending])

  return (
    <form
      className="max-w-3xl rounded-xl border bg-surface shadow-sm"
      onSubmit={(event) => {
        event.preventDefault()
        if (!chat) {
          setSelectionError('Choose a chat provider and model before saving.')
          document.getElementById('chat-model-trigger')?.focus()
          return
        }
        const values: LLMSettingsInput = { provider: chat.provider, model: chat.model, api_key: apiKey }
        if (embedding && embeddingApiKey) {
          Object.assign(values, {
            embedding_provider: embedding.provider,
            embedding_model: embedding.model,
            embedding_api_key: embeddingApiKey,
          })
        }
        onSave(values)
      }}
    >
      <div className="p-6 sm:p-8">
        <section aria-labelledby="chat-settings-title">
          <div className="mb-6">
            <p className="eyebrow !text-accent">Required</p>
            <h2 id="chat-settings-title" className="mt-1 section-title">Chat & Completions</h2>
            <p className="mt-2 text-sm text-muted">Used to analyze job descriptions and generate grounded suggestions.</p>
          </div>
          
          <div className="rounded-lg border bg-raised p-5 space-y-6">
            <ModelProviderPicker
              id="chat-model"
              label="Provider & Model"
              description="Choose the language model used for completion requests."
              purpose="chat"
              value={chat}
              supportedModels={supported}
              loading={supportedPending}
              error={supportedError}
              validationError={selectionError}
              onRetry={onRetrySupported}
              onChange={(selection) => { setChat(selection); setSelectionError('') }}
            />
            
            <label className="block text-sm font-semibold" htmlFor="api-key">
              API Key
              <input
                id="api-key"
                name="api-key"
                className="field mt-2 bg-canvas font-mono"
                type="password"
                required
                autoComplete="new-password"
                spellCheck={false}
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder={current ? 'Enter a new key to update…' : 'Paste your provider API key…'}
              />
            </label>
          </div>
        </section>

        <section className="mt-10 border-t pt-10" aria-labelledby="embedding-settings-title">
          <div className="mb-6">
            <p className="eyebrow">Optional</p>
            <h2 id="embedding-settings-title" className="mt-1 section-title">Embedding provider (for matching)</h2>
            <p className="mt-2 text-sm text-muted max-w-2xl leading-relaxed">
              Matching needs vector embeddings, which can come from a different provider than chat. 
              Anthropic, for example, offers Claude for text generation but no embedding model.
            </p>
          </div>
          
          <div className="rounded-lg border bg-raised p-5 space-y-6">
            <ModelProviderPicker
              id="embedding-model"
              label="Provider & Model"
              description="Choose the model used to compare your evidence with job requirements."
              purpose="embedding"
              value={embedding}
              supportedModels={supportedEmbeddings}
              loading={embeddingsPending}
              error={embeddingsError}
              onRetry={onRetryEmbeddings}
              onChange={setEmbedding}
            />
            
            <label className="block text-sm font-semibold" htmlFor="embedding-api-key">
              Embedding API Key <span className="font-normal text-muted">(required after choosing a model)</span>
              <input
                id="embedding-api-key"
                name="embedding-api-key"
                className="field mt-2 bg-canvas font-mono"
                type="password"
                required={!!embedding}
                autoComplete="new-password"
                spellCheck={false}
                value={embeddingApiKey}
                onChange={(event) => setEmbeddingApiKey(event.target.value)}
                placeholder={current?.masked_embedding_key ? 'Enter a new embedding key to update…' : 'Paste an embedding provider key…'}
              />
            </label>
            
            {!embedding && (
              <div className="flex items-start gap-3 rounded-md bg-canvas p-4 text-sm text-muted border border-line">
                <AlertCircle size={16} className="mt-0.5 shrink-0" />
                <p>Leave this unset to reuse your chat provider&apos;s key. That fallback will fail when the chat provider does not support embeddings.</p>
              </div>
            )}
          </div>
        </section>

        {error && (
          <div className="mt-8 flex items-start gap-3 rounded-md border border-danger/30 bg-danger/5 p-4 text-sm text-danger" role="alert">
            <AlertCircle size={16} className="mt-0.5 shrink-0" />
            <p>{error} Check both provider configurations and try again.</p>
          </div>
        )}
      </div>

      <footer className="flex flex-wrap justify-end gap-3 border-t bg-raised/50 px-6 py-4 rounded-b-xl">
        {onCancel && (
          <button type="button" className="button-ghost" onClick={onCancel}>
            Cancel
          </button>
        )}
        <button className="button-primary" disabled={pending}>
          <Save size={16} aria-hidden="true" />
          {pending ? 'Saving…' : 'Save API Keys'}
        </button>
      </footer>
    </form>
  )
}
