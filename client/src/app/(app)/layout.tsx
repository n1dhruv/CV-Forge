"use client"

import { useIsFetching, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  BookOpen,
  FileInput,
  Files,
  FileUp,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  RefreshCw,
  Settings,
  Sun,
  UserRound,
  X,
} from 'lucide-react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { Logo } from '@/components/Logo'
import { useUI } from '@/store/ui'
import { ApiError } from '@/lib/api'
import { useApi } from '@/hooks/useApi'
import { useAuth } from '@/hooks/useAuth'
import { DURATION, EASE } from '@/lib/motion'
import { ProfileEditor } from '@/components/ProfileEditor'
import { useEffect, useState } from 'react'

const nav = [
  ['/dashboard', 'Dashboard', LayoutDashboard],
  ['/profile', 'Profile', UserRound],
  ['/skill-bank', 'Skill bank', BookOpen],
  ['/resume-import', 'Import resume', FileUp],
  ['/job-description', 'Job descriptions', FileInput],
  ['/resumes', 'Resumes', Files],
  ['/settings', 'Settings', Settings],
] as const

export default function AppLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const { theme, toggleTheme, mobileNav, setMobileNav } = useUI()
  const { user, session, loading, signOut } = useAuth()
  const router = useRouter()
  const pathname = usePathname()
  const [profileOpen, setProfileOpen] = useState(false)
  
  const api = useApi()
  const queryClient = useQueryClient()
  const refreshing = useIsFetching() > 0

  useEffect(() => {
    if (!loading && !session) {
      router.replace('/sign-in')
    }
  }, [loading, session, router])

  const { data: llmSettings, error: llmError } = useQuery({
    queryKey: ['llm-settings'],
    queryFn: api.llmSettings.get,
    retry: (count, error) =>
      error instanceof ApiError && error.status === 404 ? false : count < 1,
    enabled: !!session,
  })
  const { data: profile } = useQuery({
    queryKey: ['profile'],
    queryFn: api.profile.get,
    enabled: !!session,
  })

  useEffect(() => {
    if (!profileOpen) return
    const close = (event: KeyboardEvent) => event.key === 'Escape' && setProfileOpen(false)
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [profileOpen])

  if (loading || !session) {
    return (
      <div className="grid min-h-screen place-items-center text-sm text-muted" role="status">
        Checking your session…
      </div>
    )
  }

  const missing = !llmSettings && llmError instanceof ApiError && llmError.status === 404
  const name =
    profile?.full_name ?? user?.user_metadata.full_name ??
    user?.user_metadata.name ??
    user?.user_metadata.user_name ??
    'Your workspace'
  const email = user?.email ?? 'Personal workspace'

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[15.5rem_1fr]">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      {/* ─── Mobile Header ────────────────────────── */}
      <header className="no-print sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-canvas/95 px-4 backdrop-blur-lg lg:hidden">
        <Logo />
        <button
          className="button-ghost !px-2"
          aria-label={mobileNav ? 'Close navigation' : 'Open navigation'}
          onClick={() => setMobileNav(!mobileNav)}
        >
          {mobileNav ? (
            <X size={20} aria-hidden="true" />
          ) : (
            <Menu size={20} aria-hidden="true" />
          )}
        </button>
      </header>

      {/* ─── Sidebar ──────────────────────────────── */}
      <aside
        className={`no-print fixed inset-y-0 left-0 z-40 flex w-[15.5rem] flex-col border-r bg-canvas pb-4 pt-6 transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 ${
          mobileNav ? 'translate-x-0' : '-translate-x-full'
        }`}
        style={{
          transitionDuration: 'var(--duration-normal)',
          transitionTimingFunction: 'var(--ease-out-expo)',
        }}
      >
        <div className="mb-10 px-5">
          <Logo />
        </div>

        <nav className="flex-1 px-3" aria-label="Primary">
          <ul className="space-y-0.5">
            {nav.map(([to, label, Icon]) => {
              const isActive = pathname === to || pathname.startsWith(to + '/')
              return (
                <li key={to}>
                  <Link
                    href={to}
                    onClick={() => setMobileNav(false)}
                    className={`group flex min-h-10 items-center gap-3 rounded-md px-3 text-sm font-medium transition-all ${
                      isActive
                        ? 'bg-surface text-ink'
                        : 'text-muted hover:bg-surface/60 hover:text-ink'
                    }`}
                    style={{ transitionDuration: 'var(--duration-fast)' }}
                  >
                    <span
                      className={`flex size-5 items-center justify-center transition-colors ${
                        isActive ? 'text-accent' : 'text-muted group-hover:text-subtle'
                      }`}
                    >
                      <Icon size={16} aria-hidden="true" />
                    </span>
                    {label}
                  </Link>
                </li>
              )
            })}

            {/* Refresh */}
            <li>
              <button
                className="flex min-h-10 w-full items-center gap-3 rounded-md px-3 text-sm font-medium text-muted transition-colors hover:bg-surface/60 hover:text-ink"
                disabled={refreshing}
                onClick={() => void queryClient.invalidateQueries({ type: 'active' })}
              >
                <span className="flex size-5 items-center justify-center">
                  <RefreshCw
                    size={16}
                    className={refreshing ? 'animate-spin' : ''}
                    aria-hidden="true"
                  />
                </span>
                {refreshing ? 'Refreshing…' : 'Refresh data'}
              </button>
            </li>
          </ul>
        </nav>

        {/* ─── Bottom section ─────────────────────── */}
        <div className="mt-auto border-t px-3 pt-3">
          {/* Theme toggle */}
          <button
            className="flex min-h-10 w-full items-center gap-3 rounded-md px-3 text-sm text-muted transition-colors hover:bg-surface/60 hover:text-ink"
            onClick={toggleTheme}
          >
            <span className="flex size-5 items-center justify-center">
              {theme === 'light' ? (
                <Moon size={16} aria-hidden="true" />
              ) : (
                <Sun size={16} aria-hidden="true" />
              )}
            </span>
            {theme === 'light' ? 'Dark' : 'Light'} appearance
          </button>

          {/* User info */}
          <div className="mt-2 flex items-center gap-1 rounded-md px-1 py-1">
            <button className="flex min-w-0 flex-1 items-center gap-3 rounded-md px-2 py-1 text-left transition-colors hover:bg-surface" aria-haspopup="dialog" onClick={() => setProfileOpen(true)}>
              <span className="grid size-8 shrink-0 place-items-center rounded-full bg-accent-soft text-xs font-bold text-accent" aria-hidden="true">
                {String(name).slice(0, 1).toUpperCase()}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold">{String(name)}</span>
                <span className="block truncate text-xs text-muted">{email}</span>
              </span>
            </button>
            <button
              className="button-ghost !px-2 text-muted"
              aria-label="Sign out"
              title="Sign out"
              onClick={() => void signOut()}
            >
              <LogOut size={16} aria-hidden="true" />
            </button>
          </div>
        </div>
      </aside>

      {/* ─── Mobile overlay ───────────────────────── */}
      <AnimatePresence>
        {mobileNav && (
          <motion.button
            className="fixed inset-0 z-30 bg-ink/25 backdrop-blur-sm lg:hidden"
            aria-label="Close navigation"
            onClick={() => setMobileNav(false)}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DURATION.normal }}
          />
        )}
      </AnimatePresence>

      {/* ─── Main content ─────────────────────────── */}
      <main id="main-content" className="min-w-0">
        {missing && (
          <div
            className="no-print flex flex-wrap items-center justify-between gap-3 border-b bg-accent-soft px-5 py-3 text-sm"
            role="status"
            style={{ borderColor: 'color-mix(in oklch, var(--accent) 25%, transparent)' }}
          >
            <p>
              <strong>AI provider needed.</strong> Add your own provider key before
              parsing job descriptions.
            </p>
            <Link
              className="font-semibold text-accent underline underline-offset-4"
              href="/settings"
            >
              Open Settings
            </Link>
          </div>
        )}
        {children}
      </main>

      <AnimatePresence>
        {profileOpen ? (
          <div className="fixed inset-0 z-50 grid place-items-center p-4 sm:p-8">
            <motion.button className="absolute inset-0 bg-ink/35" aria-label="Close profile" onClick={() => setProfileOpen(false)} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
            <motion.section
              aria-labelledby="profile-dialog-title"
              aria-modal="true"
              className="relative max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-xl bg-surface shadow-2xl"
              initial={{ opacity: 0, y: 14, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.99 }}
              role="dialog"
              transition={{ duration: DURATION.normal, ease: EASE.outExpo }}
            >
              <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b bg-surface px-5 py-4 sm:px-7">
                <div>
                  <h2 className="font-display text-2xl font-medium" id="profile-dialog-title">Resume profile</h2>
                  <p className="mt-1 text-sm text-muted">Choose the name and contact links shown in your resume header.</p>
                </div>
                <button className="button-ghost !px-2.5" aria-label="Close profile" onClick={() => setProfileOpen(false)}><X size={18} aria-hidden="true" /></button>
              </header>
              <div className="p-5 sm:p-7"><ProfileEditor autoFocus onSaved={() => setProfileOpen(false)} /></div>
            </motion.section>
          </div>
        ) : null}
      </AnimatePresence>
    </div>
  )
}
