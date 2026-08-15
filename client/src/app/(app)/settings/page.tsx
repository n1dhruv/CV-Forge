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
  const [testResult, setTestResult] = useState<{ success: boolean; error: string | null } | null>(null)
  const [confirmRemove, setConfirmRemove] = useState(false)

  const supported = useQuery({ queryKey: ['supported-models'], queryFn: api.llmSettings.supportedModels })
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
    onSuccess: setTestResult,
    onError: (error) => setTestResult({ success: false, error: error.message }),
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
        description="Your model stays primary. If it is unavailable—or you do not configure one—MakeMyResume uses its NVIDIA fallback."
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
                testResult={testResult}
                onTest={() => test.mutate()}
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
  testResult,
  onTest,
  onEdit,
  confirmRemove,
  onConfirmRemove,
  onCancelRemove,
  onRemove,
  removePending,
}: any) {
  return (
    <section className="max-w-3xl">
      <div className="max-w-xl">
        <SavedConfiguration title="Chat & Completions" provider={settings.provider} model={settings.model} maskedKey={settings.masked_key} onTest={onTest} testPending={testPending} />
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
                  ? 'Chat connection works.'
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
        ) : null}
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
  current,
  pending,
  error,
  onCancel,
  onSave,
}: any) {
  const [chat, setChat] = useState<ModelSelection | null>(current ? { provider: current.provider, model: current.model } : null)
  const [apiKey, setApiKey] = useState('')
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
        const values: LLMSettingsInput = { provider: chat.provider, model: chat.model }
        if (apiKey.trim()) values.api_key = apiKey.trim()
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
              value={chat}
              supportedModels={supported}
              loading={supportedPending}
              error={supportedError}
              validationError={selectionError}
              onRetry={onRetrySupported}
              onChange={(selection) => { setChat(selection); setSelectionError('') }}
            />
            
            <label className="block text-sm font-semibold" htmlFor="api-key">
              {current ? 'New API Key (optional)' : 'API Key'}
              <input
                id="api-key"
                name="api-key"
                className="field mt-2 bg-canvas font-mono"
                type="password"
                required={!current?.masked_key}
                autoComplete="new-password"
                spellCheck={false}
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder={current ? 'Enter a new key to update…' : 'Paste your provider API key…'}
              />
              {current?.masked_key && (
                <span className="mt-2 block font-normal text-muted">
                  Leave blank to keep the current key ({current.masked_key}).
                </span>
              )}
            </label>
          </div>
        </section>

        {error && (
          <div className="mt-8 flex items-start gap-3 rounded-md border border-danger/30 bg-danger/5 p-4 text-sm text-danger" role="alert">
            <AlertCircle size={16} className="mt-0.5 shrink-0" />
            <p>{error} Check the provider configuration and try again.</p>
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
          {pending ? 'Saving…' : 'Save Changes'}
        </button>
      </footer>
    </form>
  )
}
