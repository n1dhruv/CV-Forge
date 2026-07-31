import { UserButton, useUser } from '@clerk/react'
import { BookOpen, Braces, Cable, ChartNoAxesColumnIncreasing, FileCheck2, FileInput, LayoutDashboard, Menu, Moon, Sun, X } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { Logo } from './Logo'
import { useUI } from '../store/ui'
const nav=[['/dashboard','Overview',LayoutDashboard],['/skill-bank','Skill bank',BookOpen],['/job-description','Job description',FileInput],['/review','Match & review',FileCheck2],['/editor','LaTeX editor',Braces],['/ats','ATS score',ChartNoAxesColumnIncreasing],['/integrations','Integrations',Cable]] as const
export function AppShell(){const {theme,toggleTheme,mobileNav,setMobileNav}=useUI();const {user}=useUser();const name=user?.fullName??user?.firstName??'Your workspace';const email=user?.primaryEmailAddress?.emailAddress??'Personal workspace';return <div className="min-h-screen lg:grid lg:grid-cols-[16rem_1fr]">
  <a className="skip-link" href="#main-content">Skip to main content</a>
  <header className="no-print sticky top-0 z-30 flex h-16 items-center justify-between border-b bg-canvas/95 px-4 backdrop-blur lg:hidden"><Logo/><button className="button-ghost" aria-label={mobileNav?'Close navigation':'Open navigation'} onClick={()=>setMobileNav(!mobileNav)}>{mobileNav?<X/>:<Menu/>}</button></header>
  <aside className={`no-print fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r bg-canvas px-4 pb-5 pt-6 transition-transform duration-300 lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 ${mobileNav?'translate-x-0':'-translate-x-full'}`}>
    <div className="mb-10 px-2"><Logo/></div><nav className="flex-1" aria-label="Primary"><ul className="space-y-1">{nav.map(([to,label,Icon])=><li key={to}><NavLink to={to} onClick={()=>setMobileNav(false)} className={({isActive})=>`flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium transition ${isActive?'bg-ink text-canvas':'text-muted hover:bg-surface hover:text-ink'}`}><Icon size={17}/>{label}</NavLink></li>)}</ul></nav>
    <div className="border-t pt-4"><button className="flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-sm text-muted hover:bg-surface hover:text-ink" onClick={toggleTheme}>{theme==='light'?<Moon size={17}/>:<Sun size={17}/>} {theme==='light'?'Dark':'Light'} appearance</button><div className="mt-3 flex items-center gap-3 px-3"><UserButton/><div className="min-w-0"><p className="truncate text-sm font-semibold">{name}</p><p className="truncate text-xs text-muted">{email}</p></div></div></div>
  </aside>{mobileNav&&<button className="fixed inset-0 z-30 bg-ink/30 lg:hidden" aria-label="Close navigation" onClick={()=>setMobileNav(false)}/>}<main id="main-content" className="min-w-0"><Outlet/></main>
</div>}
