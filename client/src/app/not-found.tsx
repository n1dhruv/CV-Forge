"use client"

import Link from 'next/link'
import { ArrowRight, Home } from 'lucide-react'
import { Logo } from '@/components/Logo'

export default function NotFound() {
  return (
    <main className="min-h-screen bg-canvas">
      <header className="container-wide flex h-20 items-center border-b">
        <Link href="/" aria-label="MakeMyResume home">
          <Logo />
        </Link>
      </header>

      <section className="container-normal grid min-h-[calc(100vh-5rem)] items-center gap-10 py-16 md:grid-cols-[minmax(0,.8fr)_minmax(20rem,1fr)] md:py-24">
        <p className="select-none font-display text-[clamp(8rem,24vw,18rem)] font-medium leading-none tracking-[-0.04em] text-line" aria-hidden="true">
          404
        </p>

        <div className="max-w-xl">
          <h1 className="font-display text-4xl font-medium leading-tight tracking-[-0.03em] text-ink md:text-6xl">
            This page isn’t in your workspace.
          </h1>
          <p className="mt-6 max-w-lg text-base leading-7 text-muted md:text-lg">
            The address may be outdated, or the page may have moved while your resume work stayed safely stored.
          </p>
          <div className="mt-9 flex flex-wrap gap-3">
            <Link className="button-primary" href="/dashboard">
              Return to workspace <ArrowRight size={16} aria-hidden="true" />
            </Link>
            <Link className="button-secondary" href="/">
              <Home size={16} aria-hidden="true" /> Home
            </Link>
          </div>
        </div>
      </section>
    </main>
  )
}
