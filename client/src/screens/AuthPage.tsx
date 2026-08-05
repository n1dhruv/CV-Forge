import { ArrowLeft, Check, Github } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { Logo } from '../components/Logo'
import { useAuth } from '../hooks/useAuth'
import { supabase } from '../lib/supabase'

interface AuthPageProps { mode: 'sign-in' | 'sign-up' }

function GoogleIcon() {
  return <svg aria-hidden="true" fill="currentColor" viewBox="0 0 24 24" width="18" height="18"><path d="M12.48 10.92v3.28h7.84c-.24 1.84-.85 3.19-1.79 4.13-1.15 1.15-2.93 2.4-6.05 2.4-4.83 0-8.6-3.89-8.6-8.72s3.77-8.72 8.6-8.72c2.6 0 4.51 1.03 5.91 2.35l2.31-2.31C18.75 1.44 16.13 0 12.48 0 5.87 0 .31 5.39.31 12s5.56 12 12.17 12c3.57 0 6.27-1.17 8.37-3.36 2.16-2.16 2.84-5.21 2.84-7.67 0-.76-.05-1.47-.17-2.05z"/></svg>
}

export function AuthPage({mode}:AuthPageProps) {
  const signingIn=mode==='sign-in',navigate=useNavigate(),{session,loading:sessionLoading}=useAuth()
  const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('')
  useEffect(()=>{setError('');setNotice('')},[mode])
  if(!sessionLoading&&session)return <Navigate to="/dashboard" replace/>

  async function submit(event:FormEvent){
    event.preventDefault();setBusy(true);setError('');setNotice('')
    const result=signingIn
      ?await supabase.auth.signInWithPassword({email,password})
      :await supabase.auth.signUp({email,password,options:{emailRedirectTo:`${window.location.origin}/dashboard`}})
    setBusy(false)
    if(result.error){setError(result.error.message);return}
    if(result.data.session)navigate('/dashboard',{replace:true})
    else setNotice('Check your email to confirm your account, then sign in.')
  }

  async function oauth(provider:'google'|'github'){
    setBusy(true);setError('')
    const {error:oauthError}=await supabase.auth.signInWithOAuth({provider,options:{redirectTo:`${window.location.origin}/dashboard`}})
    if(oauthError){setError(oauthError.message);setBusy(false)}
  }

  return <main className="grid min-h-screen lg:grid-cols-[.85fr_1.15fr]">
    <section className="hidden border-r bg-ink p-12 text-canvas lg:flex lg:flex-col dark:bg-surface dark:text-ink">
      <Link to="/" className="w-fit"><Logo/></Link>
      <div className="my-auto max-w-md"><p className="eyebrow !text-canvas/60 dark:!text-muted">ResumeForge</p><h1 className="mt-5 font-display text-5xl font-medium leading-[1.02]">One trusted record.<br/><em className="font-normal text-accent">A sharper application.</em></h1><p className="mt-6 text-canvas/70 dark:text-muted">Build a reliable skill bank, then shape it for each opportunity with every change under your control.</p><ul className="mt-10 space-y-4 text-sm">{['Evidence stays grounded in your real work','AI suggestions always require approval','Career data remains organized and reusable'].map(item=><li className="flex items-center gap-3" key={item}><Check className="text-accent" size={16} aria-hidden="true"/>{item}</li>)}</ul></div>
      <p className="text-xs text-canvas/50 dark:text-muted">Secure account access</p>
    </section>
    <section className="flex min-h-screen flex-col px-5 py-6 md:px-10 md:py-8">
      <div className="flex items-center justify-between lg:justify-end"><Link to="/" className="lg:hidden"><Logo/></Link><Link className="button-ghost" to="/"><ArrowLeft size={16} aria-hidden="true"/>Back Home</Link></div>
      <div className="my-auto flex w-full justify-center py-10"><div className="w-full max-w-md border border-line bg-raised p-6 md:p-8">
        <div className="mb-6 text-center"><h1 className="section-title">{signingIn?'Sign In to ResumeForge':'Create Your ResumeForge Account'}</h1><p className="mt-2 text-sm text-muted">{signingIn?'Welcome back. Continue to your evidence workspace.':'Start your private career evidence workspace.'}</p></div>
        <div className="grid grid-cols-2 gap-3"><button className="button-secondary justify-center" disabled={busy} onClick={()=>void oauth('google')}><GoogleIcon/>Google</button><button className="button-secondary justify-center" disabled={busy} onClick={()=>void oauth('github')}><Github aria-hidden="true" size={18}/>GitHub</button></div>
        <div className="my-6 flex items-center gap-3 text-xs text-muted"><span className="h-px flex-1 bg-line"/><span>or use email</span><span className="h-px flex-1 bg-line"/></div>
        <form className="space-y-4" onSubmit={event=>void submit(event)}>
          <label className="block text-sm font-semibold" htmlFor="email">Email<input className="field mt-2" id="email" type="email" autoComplete="email" required value={email} onChange={event=>setEmail(event.target.value)}/></label>
          <label className="block text-sm font-semibold" htmlFor="password">Password<input className="field mt-2" id="password" type="password" autoComplete={signingIn?'current-password':'new-password'} minLength={8} required value={password} onChange={event=>setPassword(event.target.value)}/></label>
          {error&&<p className="text-sm text-danger" role="alert">{error}</p>}{notice&&<p className="text-sm text-success" role="status">{notice}</p>}
          <button className="button-primary w-full justify-center" disabled={busy} type="submit">{busy?'Please wait…':signingIn?'Sign in':'Create account'}</button>
        </form>
        <p className="mt-6 text-center text-sm text-muted">{signingIn?'New to ResumeForge?':'Already have an account?'} <Link className="font-semibold text-accent underline underline-offset-4" to={signingIn?'/sign-up':'/sign-in'}>{signingIn?'Create one':'Sign in'}</Link></p>
      </div></div>
    </section>
  </main>
}
