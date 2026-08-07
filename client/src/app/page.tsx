"use client"

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowRight, Menu, Moon, Sun, X, ShieldCheck } from 'lucide-react'
import { motion, AnimatePresence, useScroll, useMotionValueEvent } from 'framer-motion'
import { Logo } from '@/components/Logo'
import { useAuth } from '@/hooks/useAuth'
import { useUI } from '@/store/ui'
import { Reveal } from '@/components/motion/Reveal'
import { Stagger, StaggerItem } from '@/components/motion/Stagger'
import { Parallax } from '@/components/motion/Parallax'
import { DURATION, EASE, REDUCED_MOTION, fadeInUp } from '@/lib/motion'

/* ═══════════════════════════════════════════════════════
   Data
   ═══════════════════════════════════════════════════════ */

const benefits = [
  {
    number: '01',
    title: 'One source of truth',
    body: 'Keep verified experience, projects, skills, and education in one structured bank — version-controlled and always audit-ready.',
  },
  {
    number: '02',
    title: 'Tailored with control',
    body: 'Match evidence to a role and approve every suggested rewrite before it reaches a resume. Nothing is auto-applied.',
  },
  {
    number: '03',
    title: 'Ready to refine',
    body: 'Edit the generated LaTeX, track ATS keyword coverage, and iterate without losing your original facts.',
  },
] as const

const steps = [
  {
    number: '01',
    title: 'Build your skill bank',
    body: 'Add experiences, projects, and skills with tagged proof points.',
  },
  {
    number: '02',
    title: 'Parse a job description',
    body: 'Paste or upload a JD. AI extracts requirements, keywords, and seniority.',
  },
  {
    number: '03',
    title: 'Match & tailor',
    body: 'See which evidence fits. Approve rewrites one by one, then compile your resume.',
  },
] as const

const principles = [
  'Your source bullets stay intact',
  'Inferred skills remain clearly labeled',
  'Every rewrite waits for your review',
] as const

/* ═══════════════════════════════════════════════════════
   Navbar
   ═══════════════════════════════════════════════════════ */

function HomeNav() {
  const { session } = useAuth()
  const { theme, toggleTheme } = useUI()
  const [scrolled, setScrolled] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const { scrollY } = useScroll()

  useMotionValueEvent(scrollY, 'change', (latest) => {
    setScrolled(latest > 40)
  })

  const closeMobile = useCallback(() => setMobileOpen(false), [])

  return (
    <header
      className={`no-print fixed inset-x-0 top-0 z-50 transition-all ${
        scrolled
          ? 'border-b border-line/60 bg-canvas/90 backdrop-blur-lg'
          : 'bg-transparent'
      }`}
      style={{ transitionDuration: 'var(--duration-normal)' }}
    >
      <nav
        aria-label="Main navigation"
        className="container-wide flex h-16 items-center justify-between md:h-20"
      >
        <Link href="/" aria-label="ResumeForge home">
          <Logo />
        </Link>

        {/* Desktop actions */}
        <div className="hidden items-center gap-1 md:flex">
          <button
            className="button-ghost !px-2.5"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
          >
            {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
          </button>
          {!session ? (
            <>
              <Link className="button-ghost" href="/sign-in">Log in</Link>
              <Link className="button-primary" href="/sign-up">Create account</Link>
            </>
          ) : (
            <Link className="button-primary" href="/dashboard">
              Open workspace <ArrowRight size={16} />
            </Link>
          )}
        </div>

        {/* Mobile toggle */}
        <div className="flex items-center gap-1 md:hidden">
          <button
            className="button-ghost !px-2.5"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
          >
            {theme === 'light' ? <Moon size={17} /> : <Sun size={17} />}
          </button>
          <button
            className="button-ghost !px-2.5"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label={mobileOpen ? 'Close navigation' : 'Open navigation'}
          >
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </nav>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              className="fixed inset-0 top-16 z-40 bg-ink/20 backdrop-blur-sm md:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={closeMobile}
            />
            <motion.div
              className="fixed inset-x-0 top-16 z-50 border-b bg-canvas p-5 md:hidden"
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: DURATION.normal, ease: EASE.outExpo }}
            >
              <div className="flex flex-col gap-2">
                {!session ? (
                  <>
                    <Link className="button-ghost w-full justify-start" href="/sign-in" onClick={closeMobile}>
                      Log in
                    </Link>
                    <Link className="button-primary w-full justify-center" href="/sign-up" onClick={closeMobile}>
                      Create account
                    </Link>
                  </>
                ) : (
                  <Link className="button-primary w-full justify-center" href="/dashboard" onClick={closeMobile}>
                    Open workspace <ArrowRight size={16} />
                  </Link>
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </header>
  )
}

/* ═══════════════════════════════════════════════════════
   Dot Grid Background
   ═══════════════════════════════════════════════════════ */

function DotGrid() {
  return (
    <div
      className="pointer-events-none absolute inset-0 opacity-[0.35]"
      style={{
        backgroundImage: `radial-gradient(circle, var(--muted) 0.7px, transparent 0.7px)`,
        backgroundSize: '24px 24px',
        maskImage: 'radial-gradient(ellipse 70% 60% at 50% 50%, black 30%, transparent 80%)',
        WebkitMaskImage: 'radial-gradient(ellipse 70% 60% at 50% 50%, black 30%, transparent 80%)',
      }}
    />
  )
}

/* ═══════════════════════════════════════════════════════
   Page
   ═══════════════════════════════════════════════════════ */

export default function Home() {
  const { session } = useAuth()

  // Scroll indicator auto-hide
  const [showScroll, setShowScroll] = useState(true)
  const { scrollY } = useScroll()
  useMotionValueEvent(scrollY, 'change', (latest) => {
    if (latest > 100) setShowScroll(false)
  })

  // Prevent body scroll when mobile menu is open (handled by nav)
  useEffect(() => {
    return () => { document.body.style.overflow = '' }
  }, [])

  return (
    <div className="min-h-screen bg-canvas">
      <HomeNav />

      <main>
        {/* ─── Hero ─────────────────────────────────── */}
        <section className="relative flex min-h-[100dvh] items-center overflow-hidden pt-20">
          <DotGrid />

          <Parallax speed={0.08} className="pointer-events-none absolute inset-0">
            <div
              className="absolute -right-24 top-1/4 h-[32rem] w-[32rem] rounded-full opacity-20"
              style={{
                background: `radial-gradient(circle, var(--accent-soft) 0%, transparent 70%)`,
              }}
            />
            <div
              className="absolute -left-16 bottom-1/4 h-[24rem] w-[24rem] rounded-full opacity-15"
              style={{
                background: `radial-gradient(circle, var(--accent-soft) 0%, transparent 70%)`,
              }}
            />
          </Parallax>

          <div className="container-wide relative z-10 grid gap-16 py-12 lg:grid-cols-[1.25fr_0.75fr] lg:items-center lg:gap-20">
            <div>
              <Reveal variant="up">
                <p className="eyebrow mb-6">Evidence-first resume tailoring</p>
              </Reveal>

              <Reveal variant="up" delay={0.1}>
                <h1 className="display max-w-[18ch]">
                  Build from what you&apos;ve done.
                  <br />
                  <em className="font-normal text-accent">
                    Tailor for where you&apos;re going.
                  </em>
                </h1>
              </Reveal>

              <Reveal variant="up" delay={0.2}>
                <p className="mt-8 max-w-[52ch] text-lg leading-relaxed text-muted">
                  ResumeForge turns your real career evidence into focused,
                  job-aware resumes — without inventing claims or applying AI
                  edits behind your back.
                </p>
              </Reveal>

              <Reveal variant="up" delay={0.3}>
                <div className="mt-10 flex flex-wrap gap-3">
                  {!session ? (
                    <>
                      <Link className="button-accent" href="/sign-up">
                        Start building <ArrowRight size={17} />
                      </Link>
                      <Link className="button-secondary" href="/sign-in">
                        I have an account
                      </Link>
                    </>
                  ) : (
                    <Link className="button-accent" href="/dashboard">
                      Continue to your workspace <ArrowRight size={17} />
                    </Link>
                  )}
                </div>
              </Reveal>
            </div>

            {/* Principles card */}
            <Reveal variant="scale" delay={0.35}>
              <aside
                className="border border-line bg-surface/60 p-8 backdrop-blur-sm lg:p-10"
                style={{ borderRadius: 'var(--radius-lg)' }}
                aria-label="ResumeForge principles"
              >
                <div className="rounded-lg border bg-canvas p-5 sm:p-7 sm:pl-16 relative">
                  <ShieldCheck size={24} className="absolute left-6 top-7 hidden sm:block text-success/70" aria-hidden="true" />
                  <p className="font-semibold text-ink">ResumeForge doesn&apos;t connect to any servers but your own database.</p>
                  <p className="mt-2 text-sm text-muted">All AI processing happens locally in your browser through direct API calls to your chosen provider. Your resume data never passes through a middleman server.</p>
                </div>
                <ul className="mt-8 space-y-5">
                  {principles.map((item, i) => (
                    <li className="flex gap-3 text-sm font-medium" key={item}>
                      <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      </span>
                      {item}
                    </li>
                  ))}
                </ul>
              </aside>
            </Reveal>
          </div>

          {/* Scroll indicator */}
          <AnimatePresence>
            {showScroll && !REDUCED_MOTION && (
              <motion.div
                className="absolute bottom-8 left-1/2 -translate-x-1/2"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ delay: 1.2, duration: 0.6 }}
              >
                <div className="flex flex-col items-center gap-2">
                  <span className="text-[10px] font-semibold uppercase tracking-[.2em] text-muted">
                    Scroll
                  </span>
                  <motion.div
                    className="h-8 w-px bg-line"
                    animate={{ scaleY: [0, 1, 0], originY: 0 }}
                    transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        {/* ─── Benefits ─────────────────────────────── */}
        <section className="section-spacing bg-surface" aria-labelledby="workflow-heading">
          <div className="container-wide">
            <Reveal>
              <p className="eyebrow mb-3">Phase 1 foundation</p>
            </Reveal>
            <Reveal delay={0.05}>
              <h2 id="workflow-heading" className="section-title max-w-xl">
                A trustworthy workspace before the automation begins.
              </h2>
            </Reveal>

            <Stagger className="mt-14 grid gap-px border bg-line md:grid-cols-3" staggerDelay={0.1}>
              {benefits.map((item) => (
                <StaggerItem as="article" key={item.number}>
                  <div className="flex h-full flex-col bg-surface p-7 transition-colors duration-300 hover:bg-raised md:p-9">
                    <div className="flex items-center justify-between">
                      <span
                        className="grid size-10 place-items-center text-accent"
                        style={{ borderRadius: 'var(--radius-md)' }}
                      >
                        <span className="font-mono text-sm font-bold">{item.number}</span>
                      </span>
                    </div>
                    <h3 className="mt-8 font-display text-2xl font-medium tracking-tight">
                      {item.title}
                    </h3>
                    <p className="mt-3 text-sm leading-relaxed text-muted">
                      {item.body}
                    </p>
                  </div>
                </StaggerItem>
              ))}
            </Stagger>
          </div>
        </section>

        {/* ─── How It Works ─────────────────────────── */}
        <section className="section-spacing" aria-labelledby="how-heading">
          <div className="container-wide">
            <div className="grid gap-16 lg:grid-cols-[1fr_1.3fr] lg:items-start">
              <div className="lg:sticky lg:top-28">
                <Reveal>
                  <p className="eyebrow mb-3">How it works</p>
                </Reveal>
                <Reveal delay={0.05}>
                  <h2 id="how-heading" className="page-title max-w-md">
                    Three steps from evidence to a focused resume.
                  </h2>
                </Reveal>
                <Reveal delay={0.1}>
                  <p className="mt-5 max-w-md text-muted">
                    ResumeForge never invents. It selects from your verified record,
                    then waits for your approval on every change.
                  </p>
                </Reveal>
              </div>

              <Stagger className="space-y-0" staggerDelay={0.12}>
                {steps.map((step, i) => (
                  <StaggerItem key={step.number}>
                    <div
                      className={`relative grid gap-5 py-8 pl-10 sm:grid-cols-[3rem_1fr] sm:pl-0 ${
                        i < steps.length - 1 ? 'border-b border-line-soft' : ''
                      }`}
                    >
                      {/* Vertical connector line */}
                      <div className="absolute bottom-0 left-3 top-0 w-px bg-line sm:hidden" />

                      {/* Number */}
                      <div className="relative flex items-start justify-center pt-1">
                        <span className="relative z-10 grid size-8 place-items-center bg-canvas font-mono text-xs font-bold text-accent">
                          {step.number}
                        </span>
                      </div>

                      <div>
                        <h3 className="section-title">{step.title}</h3>
                        <p className="mt-2 max-w-md text-sm leading-relaxed text-muted">
                          {step.body}
                        </p>
                      </div>
                    </div>
                  </StaggerItem>
                ))}
              </Stagger>
            </div>
          </div>
        </section>

        {/* ─── CTA Band ─────────────────────────────── */}
        <section className="section-spacing bg-surface">
          <div className="container-narrow text-center">
            <Reveal>
              <p className="eyebrow mb-4">Ready to begin?</p>
            </Reveal>
            <Reveal delay={0.05}>
              <h2 className="page-title">
                Your evidence. Your approval.
                <br />
                <em className="font-normal text-accent">Your resume.</em>
              </h2>
            </Reveal>
            <Reveal delay={0.15}>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                {!session ? (
                  <>
                    <Link className="button-accent" href="/sign-up">
                      Create your workspace <ArrowRight size={17} />
                    </Link>
                    <Link className="button-secondary" href="/sign-in">
                      Sign in
                    </Link>
                  </>
                ) : (
                  <Link className="button-accent" href="/dashboard">
                    Open workspace <ArrowRight size={17} />
                  </Link>
                )}
              </div>
            </Reveal>
          </div>
        </section>
      </main>

      {/* ─── Footer ────────────────────────────────── */}
      <footer className="border-t">
        <div className="container-wide flex flex-col gap-4 py-8 text-sm text-muted md:flex-row md:items-center md:justify-between">
          <Logo />
          <p>Your evidence. Your approval. Your resume.</p>
        </div>
      </footer>
    </div>
  )
}
