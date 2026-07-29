import type { Integration, ParsedJobDescription, ResumeVersion, RewriteSuggestion, SkillBankItem } from './types'
const self = (name: string) => ({ id: name.toLowerCase().replace(/ /g, '-'), name, source: 'self_reported' as const })
export const skillBank: SkillBankItem[] = [
  { id:'exp-1', type:'experience', title:'Product Engineer', organization:'Northstar Labs', location:'Bengaluru', startDate:'2023', endDate:'Present', description:'Developer infrastructure for high-growth product teams.', skills:[self('React'),self('TypeScript'),self('PostgreSQL')], bullets:[
    {id:'b1', text:'Rebuilt the release workflow in React and TypeScript, cutting median deployment setup from 18 minutes to 6 minutes.', tags:[self('React'),self('TypeScript')], metrics:['18 → 6 min']},
    {id:'b2', text:'Designed an audit-log pipeline backed by PostgreSQL that processed 2.4M monthly events with traceable retention controls.', tags:[self('PostgreSQL'),self('System Design')], metrics:['2.4M events/mo']},
    {id:'b3', text:'Partnered with design and support to reduce failed onboarding sessions by 31% across three enterprise cohorts.', tags:[self('Product Strategy')], metrics:['31% reduction']}
  ]},
  { id:'proj-1', type:'project', title:'Papertrail', organization:'Open source', startDate:'2024', endDate:'Active', description:'A local-first research library for technical teams.', skills:[self('React'),self('FastAPI'),self('Python')], bullets:[
    {id:'b4', text:'Built a local-first document index with conflict-safe sync and full-text search across 12,000 notes.', tags:[self('React'),self('FastAPI')], metrics:['12,000 notes']},
    {id:'b5', text:'Published a typed Python SDK and migration guide adopted by 140+ developers.', tags:[self('Python'),self('Developer Experience')], metrics:['140+ developers']}
  ]},
  { id:'edu-1', type:'education', title:'B.Tech, Computer Science', organization:'PES University', startDate:'2019', endDate:'2023', description:'Coursework in distributed systems, databases, and human-computer interaction.', skills:[], bullets:[] }
]
export const jd: ParsedJobDescription = { id:'jd-1', company:'Fathom', role:'Senior Product Engineer', seniority:'Senior', requiredSkills:['React','TypeScript','API design','PostgreSQL'], niceToHaveSkills:['Python','Developer tooling','Design systems'], atsKeywords:['cross-functional','performance','accessibility','distributed systems','observability','React','TypeScript'], responsibilities:['Own product features from discovery through delivery','Design reliable APIs and data models','Raise the quality bar for frontend architecture'], rawText:'We are looking for a Senior Product Engineer to own cross-functional product work...' }
export const versions: ResumeVersion[] = [
 {id:'v4',name:'Fathom · Senior Product Engineer',company:'Fathom',role:'Senior Product Engineer',updatedAt:'Today, 10:42',atsScore:86,texSource:''},
 {id:'v3',name:'Linear · Product Engineer',company:'Linear',role:'Product Engineer',updatedAt:'25 Jul',atsScore:79,texSource:''},
 {id:'v2',name:'Razorpay · Frontend Engineer',company:'Razorpay',role:'Frontend Engineer',updatedAt:'18 Jul',atsScore:74,texSource:''}
]
export const suggestions: RewriteSuggestion[] = skillBank.slice(0,2).flatMap((item,i)=>item.bullets.slice(0,2).map((b,j)=>({ id:`r${i}${j}`, section:item.title, sourceBullet:b, tailoredText:j===0?'Owned a cross-functional React and TypeScript release workflow, reducing median deployment setup from 18 minutes to 6 minutes.':b.text.replace('Designed','Architected').replace('Built','Shipped'), relevance:94-(i*8+j*5), matchedKeywords:j===0?['React','TypeScript','cross-functional']:['API design','PostgreSQL'], decision:'pending' as const })))
export const integrations: Integration[] = [
 {provider:'github',connected:true,handle:'dhruv-dev',lastSyncedAt:'Today, 09:18',state:'done',inferredSkills:[{id:'rust',name:'Rust',source:'github'},{id:'actions',name:'GitHub Actions',source:'github'},{id:'docker',name:'Docker',source:'github'}]},
 {provider:'leetcode',connected:false,state:'done',inferredSkills:[]}
]
export const tex = String.raw`\documentclass[10pt]{article}
\usepackage[margin=0.65in]{geometry}
\usepackage{enumitem,hyperref}
\pagestyle{empty}
\begin{document}
\begin{center}
  {\Large \textbf{Dhruv Sharma}}\\
  Bengaluru, India $\cdot$ dhruv@example.com $\cdot$ github.com/dhruv
\end{center}

\section*{Experience}
\textbf{Product Engineer} \hfill 2023--Present\\
\textit{Northstar Labs, Bengaluru}
\begin{itemize}[leftmargin=*,nosep]
  \item Owned a cross-functional React and TypeScript release workflow, reducing median deployment setup from 18 minutes to 6 minutes.
  \item Architected a PostgreSQL audit-log pipeline processing 2.4M monthly events with traceable retention controls.
\end{itemize}

\section*{Projects}
\textbf{Papertrail} — React, FastAPI, Python
\begin{itemize}[leftmargin=*,nosep]
  \item Built a local-first document index with conflict-safe sync and full-text search across 12,000 notes.
\end{itemize}
\end{document}`
