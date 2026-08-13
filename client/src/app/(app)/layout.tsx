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
import { useEffect } from 'react'

const nav = [
  ['/dashboard', 'Dashboard', LayoutDashboard],
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
  
  const api = useApi()
  const queryClient = useQueryClient()
  const refreshing = useIsFetching() > 0

  useEffect(() => {
    if (!loading && !session) {
      router.replace('/auth')
    }
  }, [loading, session, router])

  const { data: llmSettings, error: llmError } = useQuery({
    queryKey: ['llm-settings'],
    queryFn: api.llmSettings.get,
    retry: (count, error) =>
      error instanceof ApiError && error.status === 404 ? false : count < 1,
    enabled: !!session,
  })

  if (loading || !session) {
    return (
      <div className="grid min-h-screen place-items-center text-sm text-muted" role="status">
        Checking your session…
      </div>
    )
  }

  const missing = !llmSettings && llmError instanceof ApiError && llmError.status === 404
  const name =
    user?.user_metadata.full_name ??
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
          <div className="mt-2 flex items-center gap-3 rounded-md px-3 py-2">
            <div
              className="grid size-8 shrink-0 place-items-center rounded-full bg-accent-soft text-xs font-bold text-accent"
              aria-hidden="true"
            >
              {String(name).slice(0, 1).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">{String(name)}</p>
              <p className="truncate text-xs text-muted">{email}</p>
            </div>
            <button
              className="text-muted transition-colors hover:text-ink"
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
    </div>
  )
}
