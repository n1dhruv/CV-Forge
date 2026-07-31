import { SignIn, SignUp } from '@clerk/react'
import { ArrowLeft, Check } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Logo } from '../components/Logo'

interface AuthPageProps { mode: 'sign-in' | 'sign-up' }

const appearance = {
  variables: {
    colorPrimary: 'var(--accent)',
    colorBackground: 'var(--raised)',
    colorText: 'var(--ink)',
    colorTextSecondary: 'var(--muted)',
    colorInputBackground: 'var(--raised)',
    colorInputText: 'var(--ink)',
    borderRadius: '0.5rem',
    fontFamily: '"Instrument Sans", "Avenir Next", sans-serif',
  },
  elements: {
    rootBox: 'w-full',
    cardBox: 'w-full shadow-none',
    card: 'w-full border border-line shadow-none',
    headerTitle: 'font-display font-medium',
    formButtonPrimary: 'bg-ink text-canvas hover:bg-ink hover:opacity-85',
    footerActionLink: 'text-accent hover:text-accent',
  },
} as const

export function AuthPage({mode}:AuthPageProps) {
  const signingIn=mode==='sign-in'
  return <main className="grid min-h-screen lg:grid-cols-[.85fr_1.15fr]">
    <section className="hidden border-r bg-ink p-12 text-canvas lg:flex lg:flex-col dark:bg-surface dark:text-ink">
      <Link to="/" className="w-fit"><Logo/></Link>
      <div className="my-auto max-w-md">
        <p className="eyebrow !text-canvas/60 dark:!text-muted">ResumeForge</p>
        <h1 className="mt-5 font-display text-5xl font-medium leading-[1.02]">One trusted record.<br/><em className="font-normal text-accent">A sharper application.</em></h1>
        <p className="mt-6 text-canvas/70 dark:text-muted">Build a reliable skill bank, then shape it for each opportunity with every change under your control.</p>
        <ul className="mt-10 space-y-4 text-sm">{['Evidence stays grounded in your real work','AI suggestions always require approval','Career data remains organized and reusable'].map(item=><li className="flex items-center gap-3" key={item}><Check className="text-accent" size={16}/>{item}</li>)}</ul>
      </div>
      <p className="text-xs text-canvas/50 dark:text-muted">Phase 1 · Secure account access</p>
    </section>
    <section className="flex min-h-screen flex-col px-5 py-6 md:px-10 md:py-8">
      <div className="flex items-center justify-between lg:justify-end"><Link to="/" className="lg:hidden"><Logo/></Link><Link className="button-ghost" to="/"><ArrowLeft size={16}/>Back home</Link></div>
      <div className="my-auto flex w-full justify-center py-10">
        <div className="w-full max-w-md">
          {signingIn
            ? <SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" fallbackRedirectUrl="/dashboard" appearance={appearance}/>
            : <SignUp routing="path" path="/sign-up" signInUrl="/sign-in" fallbackRedirectUrl="/dashboard" appearance={appearance}/>
          }
        </div>
      </div>
    </section>
  </main>
}
