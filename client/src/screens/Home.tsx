import { ArrowRight, Check, FileCheck2, Layers3, PenLine } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Logo } from '../components/Logo'
import { useAuth } from '../hooks/useAuth'

const benefits = [
  ['One source of truth', 'Keep verified experience, projects, skills, and education in one structured bank.', Layers3],
  ['Tailored with control', 'Match evidence to a role and approve every suggested rewrite before it reaches a resume.', FileCheck2],
  ['Ready to refine', 'Edit the generated LaTeX and track ATS coverage without losing your original facts.', PenLine],
] as const

export function Home() {
  const {session}=useAuth()
  return <div className="min-h-screen bg-canvas">
    <header className="border-b">
      <nav aria-label="Main navigation" className="mx-auto flex h-20 max-w-7xl items-center justify-between px-5 md:px-10">
        <Link to="/" aria-label="ResumeForge home"><Logo/></Link>
        <div className="flex items-center gap-2">
          {!session&&<>
            <Link className="button-ghost" to="/sign-in">Log in</Link>
            <Link className="button-primary" to="/sign-up">Create account</Link>
          </>}
          {session&&<>
            <Link className="button-primary" to="/dashboard">Open workspace <ArrowRight size={16}/></Link>
          </>}
        </div>
      </nav>
    </header>

    <main>
      <section className="mx-auto grid max-w-7xl gap-14 px-5 py-20 md:px-10 md:py-28 lg:grid-cols-[1.2fr_.8fr] lg:items-end">
        <div className="page-enter">
          <p className="eyebrow mb-6">Evidence-first resume tailoring</p>
          <h1 className="display max-w-4xl">Build from what you’ve done.<br/><em className="font-normal text-accent">Tailor for where you’re going.</em></h1>
          <p className="mt-8 max-w-2xl text-lg text-muted">ResumeForge turns your real career evidence into focused, job-aware resumes—without inventing claims or applying AI edits behind your back.</p>
          <div className="mt-9 flex flex-wrap gap-3">
            {!session&&<><Link className="button-accent" to="/sign-up">Start building <ArrowRight size={17}/></Link><Link className="button-secondary" to="/sign-in">I have an account</Link></>}
            {session&&<Link className="button-accent" to="/dashboard">Continue to your workspace <ArrowRight size={17}/></Link>}
          </div>
        </div>
        <aside className="border-y py-7 lg:border lg:p-8" aria-label="ResumeForge principles">
          <p className="eyebrow">Built around your approval</p>
          <ul className="mt-8 space-y-5">
            {['Your source bullets stay intact','Inferred skills remain clearly labeled','Every rewrite waits for your review'].map(item=><li className="flex gap-3 text-sm font-medium" key={item}><span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-accent-soft text-accent"><Check size={13}/></span>{item}</li>)}
          </ul>
        </aside>
      </section>

      <section className="border-y bg-surface" aria-labelledby="workflow-heading">
        <div className="mx-auto max-w-7xl px-5 py-16 md:px-10 md:py-20">
          <p className="eyebrow mb-3">Phase 1 foundation</p>
          <h2 id="workflow-heading" className="section-title max-w-xl">A trustworthy workspace before the automation begins.</h2>
          <div className="mt-12 grid gap-px border bg-line md:grid-cols-3">
            {benefits.map(([title,body,Icon],index)=><article className="bg-surface p-7 md:p-8" key={title}><div className="flex items-center justify-between"><Icon className="text-accent" size={22}/><span className="font-mono text-xs text-muted">0{index+1}</span></div><h3 className="mt-10 font-display text-2xl font-medium">{title}</h3><p className="mt-3 text-sm leading-6 text-muted">{body}</p></article>)}
          </div>
        </div>
      </section>
    </main>
    <footer className="mx-auto flex max-w-7xl flex-col gap-3 px-5 py-8 text-sm text-muted md:flex-row md:items-center md:justify-between md:px-10"><Logo/><p>Your evidence. Your approval. Your resume.</p></footer>
  </div>
}
