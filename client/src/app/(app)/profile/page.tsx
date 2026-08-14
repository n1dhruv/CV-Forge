"use client"

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, LoaderCircle, Save } from 'lucide-react'
import { FormEvent, useEffect, useRef, useState } from 'react'
import { PageHeader } from '@/components/PageHeader'
import { ScreenState } from '@/components/ScreenState'
import { useApi } from '@/hooks/useApi'
import { profileLinkError } from '@/lib/task4'
import type { Profile, ProfileUpdate } from '@/lib/types'

const emptyProfile: Profile = {
  full_name: null,
  contact_email: '',
  phone: null,
  location: null,
  linkedin_url: null,
  github_url: null,
  leetcode_url: null,
  portfolio_url: null,
}

const fields: Array<{
  name: keyof Profile
  label: string
  type?: 'email' | 'tel' | 'url'
  autoComplete?: string
  placeholder?: string
}> = [
  { name: 'full_name', label: 'Full name', autoComplete: 'name' },
  { name: 'contact_email', label: 'Contact email', type: 'email', autoComplete: 'email' },
  { name: 'phone', label: 'Phone', type: 'tel', autoComplete: 'tel' },
  { name: 'location', label: 'Location', autoComplete: 'address-level2' },
  { name: 'linkedin_url', label: 'LinkedIn URL', type: 'url', placeholder: 'https://linkedin.com/in/…' },
  { name: 'github_url', label: 'GitHub URL', type: 'url', placeholder: 'https://github.com/…' },
  { name: 'leetcode_url', label: 'LeetCode URL', type: 'url', placeholder: 'https://leetcode.com/u/…' },
  { name: 'portfolio_url', label: 'Portfolio URL', type: 'url', placeholder: 'https://…' },
]

export default function ProfilePage() {
  const api = useApi()
  const queryClient = useQueryClient()
  const initialized = useRef(false)
  const [form, setForm] = useState<Profile>(emptyProfile)
  const profile = useQuery({ queryKey: ['profile'], queryFn: api.profile.get })

  useEffect(() => {
    if (!profile.data || initialized.current) return
    initialized.current = true
    setForm(profile.data)
  }, [profile.data])

  const save = useMutation({
    mutationFn: (payload: ProfileUpdate) => api.profile.update(payload),
    onSuccess: saved => {
      setForm(saved)
      queryClient.setQueryData(['profile'], saved)
    },
  })

  const linkErrors = Object.fromEntries(
    fields.filter(field => field.type === 'url').map(field => [field.name, profileLinkError(form[field.name] ?? '')]),
  ) as Partial<Record<keyof Profile, string>>
  const invalidLinks = Object.values(linkErrors).some(Boolean)
  const changed = !!profile.data && fields.some(field => (form[field.name] ?? '') !== (profile.data?.[field.name] ?? ''))

  function submit(event: FormEvent) {
    event.preventDefault()
    if (invalidLinks) return
    save.mutate(Object.fromEntries(fields.map(field => [field.name, form[field.name]?.trim() || null])))
  }

  if (profile.isPending) return <div className="container-normal py-12"><ScreenState kind="loading" title="Loading profile…" detail="Opening the contact details used in your resumes." /></div>
  if (profile.isError) return <div className="container-normal py-12"><ScreenState kind="error" title="Profile unavailable" detail={profile.error.message} onRetry={() => void profile.refetch()} /></div>

  return (
    <div className="container-normal py-10 md:py-12">
      <PageHeader eyebrow="Resume identity" title="Profile" description="These contact details can appear in tailored resumes. Only fields you save here are used." />
      <form className="max-w-3xl" onSubmit={submit}>
        <fieldset className="grid gap-6 rounded-xl border bg-surface p-6 shadow-sm sm:grid-cols-2 sm:p-8" disabled={save.isPending}>
          {fields.map(field => {
            const error = linkErrors[field.name]
            return (
              <label className="text-sm font-semibold text-ink" htmlFor={`profile-${field.name}`} key={field.name}>
                {field.label}
                <input
                  id={`profile-${field.name}`}
                  className="field mt-2.5 bg-canvas font-normal"
                  type={field.type ?? 'text'}
                  autoComplete={field.autoComplete}
                  placeholder={field.placeholder}
                  value={form[field.name] ?? ''}
                  aria-describedby={error ? `profile-${field.name}-error` : undefined}
                  aria-invalid={!!error}
                  onChange={event => setForm(current => ({ ...current, [field.name]: event.target.value }))}
                />
                {error ? <span className="mt-2 block font-normal text-danger" id={`profile-${field.name}-error`}>{error}</span> : null}
              </label>
            )
          })}
        </fieldset>

        <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
          <p className={`text-sm ${save.isError ? 'text-danger' : 'text-muted'}`} role={save.isError ? 'alert' : 'status'} aria-live="polite">
            {save.isPending ? 'Saving profile…' : save.isError ? save.error.message : save.isSuccess && !changed ? 'Profile saved.' : changed ? 'You have unsaved changes.' : 'Profile is up to date.'}
          </p>
          <button className="button-primary" disabled={!changed || invalidLinks || save.isPending} type="submit">
            {save.isPending ? <LoaderCircle className="animate-spin" size={16} aria-hidden="true" /> : save.isSuccess && !changed ? <Check size={16} aria-hidden="true" /> : <Save size={16} aria-hidden="true" />}
            {save.isPending ? 'Saving…' : 'Save profile'}
          </button>
        </div>
      </form>
    </div>
  )
}
