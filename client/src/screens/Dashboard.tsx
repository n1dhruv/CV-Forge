import { useQuery } from '@tanstack/react-query'
import { ArrowRight, BriefcaseBusiness, FolderKanban, Plus, Shapes } from 'lucide-react'
import { Link } from 'react-router-dom'
import { ScreenState } from '../components/ScreenState'
import { useApi } from '../hooks/useApi'
import type { ItemType } from '../lib/types'

const date = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' })
const labels: Record<ItemType, string> = { experience:'Experience', project:'Project', skill:'Skill', education:'Education', certification:'Certification' }

export function Dashboard(){
  const api=useApi()
  const items=useQuery({queryKey:['skill-bank'],queryFn:()=>api.skillBank.list()})
  const jds=useQuery({queryKey:['jds'],queryFn:api.jd.list})
  if(items.isPending||jds.isPending)return <div className="px-5 py-8 md:px-10 xl:px-16"><ScreenState kind="loading" title="Loading your workspace…" detail="Gathering your evidence and job descriptions."/></div>
  if(items.isError||jds.isError)return <div className="px-5 py-8 md:px-10 xl:px-16"><ScreenState kind="error" title="Workspace unavailable" detail={(items.error??jds.error)?.message??'Try loading the workspace again.'} onRetry={()=>{void items.refetch();void jds.refetch()}}/></div>
  const counts={experience:items.data.filter(x=>x.type==='experience').length,project:items.data.filter(x=>x.type==='project').length,skill:items.data.filter(x=>x.type==='skill').length,jd:jds.data.length}
  const recentItems=[...items.data].sort((a,b)=>b.updated_at.localeCompare(a.updated_at)).slice(0,3)
  return <div className="page-enter px-5 py-8 md:px-10 md:py-12 xl:px-16 xl:py-14">
    <header className="mb-12 grid gap-8 border-b pb-9 xl:grid-cols-[1.35fr_.65fr] xl:items-end"><div><p className="eyebrow mb-5">Career evidence ledger</p><h1 className="display max-w-4xl text-balance">Your record is ready<br/><em className="font-normal text-accent">when opportunity arrives.</em></h1></div><p className="max-w-md text-pretty text-muted xl:justify-self-end">Keep the facts current, then parse each role against evidence you can stand behind.</p></header>
    <section aria-labelledby="overview" className="mb-14"><div className="mb-5 flex items-end justify-between"><h2 id="overview" className="section-title">Overview</h2><Link className="button-ghost" to="/skill-bank">Open skill bank <ArrowRight size={16} aria-hidden="true"/></Link></div><div className="grid border-y sm:grid-cols-2 xl:grid-cols-4">{[{Icon:BriefcaseBusiness,label:'Experiences',value:counts.experience},{Icon:FolderKanban,label:'Projects',value:counts.project},{Icon:Shapes,label:'Skills',value:counts.skill},{Icon:Shapes,label:'JDs parsed',value:counts.jd}].map(({Icon,label,value},index)=><div className={`py-6 sm:px-5 ${index?'sm:border-l':''}`} key={label}><Icon size={17} className="mb-5 text-muted" aria-hidden="true"/><p className="font-mono text-4xl tabular-nums">{value}</p><p className="mt-2 text-sm text-muted">{label}</p></div>)}</div></section>
    {!items.data.length?<section className="mb-14 border-l-4 border-accent bg-surface px-6 py-8"><p className="eyebrow">Start with source material</p><h2 className="mt-3 section-title">Your skill bank is empty.</h2><p className="mt-2 max-w-xl text-sm text-muted">Add one experience or project. Its proof points become the trusted source for later resume work.</p><Link className="button-primary mt-5" to="/skill-bank"><Plus size={16} aria-hidden="true"/>Add first entry</Link></section>:null}
    <section aria-labelledby="recent" className="grid gap-10 xl:grid-cols-2"><div><h2 id="recent" className="section-title">Recent skill bank edits</h2><div className="mt-5 divide-y border-y">{recentItems.length?recentItems.map(item=><Link key={item.id} to="/skill-bank" className="block py-5 hover:text-accent"><div className="flex items-center justify-between gap-4"><div className="min-w-0"><p className="truncate font-semibold">{item.title}</p><p className="mt-1 text-sm text-muted">{labels[item.type]}{item.org?` · ${item.org}`:''}</p></div><time className="shrink-0 font-mono text-xs text-muted" dateTime={item.updated_at}>{date.format(new Date(item.updated_at))}</time></div></Link>):<p className="py-6 text-sm text-muted">No edits yet.</p>}</div></div><div><h2 className="section-title">Recent job descriptions</h2><div className="mt-5 divide-y border-y">{jds.data.slice(0,3).map(jd=><Link key={jd.id} to={`/job-description?jd=${jd.id}`} className="block py-5 hover:text-accent"><div className="flex items-center justify-between gap-4"><p className="min-w-0 truncate font-semibold">{jd.excerpt||'PDF job description'}</p><span className="tag capitalize">{jd.status}</span></div><time className="mt-2 block font-mono text-xs text-muted" dateTime={jd.created_at}>{date.format(new Date(jd.created_at))}</time></Link>)}{!jds.data.length?<p className="py-6 text-sm text-muted">No job descriptions parsed yet.</p>:null}</div></div></section>
  </div>
}
