import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
type Theme = 'light'|'dark'
interface UIContextValue { theme: Theme; toggleTheme:()=>void; mobileNav:boolean; setMobileNav:(open:boolean)=>void }
const UIContext=createContext<UIContextValue|null>(null)
export function UIProvider({children}:{children:ReactNode}) { const [theme,setTheme]=useState<Theme>(()=>(localStorage.getItem('rf-theme') as Theme)||((matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light')); const [mobileNav,setMobileNav]=useState(false); useEffect(()=>{document.documentElement.dataset.theme=theme;localStorage.setItem('rf-theme',theme)},[theme]); const value=useMemo(()=>({theme,toggleTheme:()=>setTheme(t=>t==='light'?'dark':'light'),mobileNav,setMobileNav}),[theme,mobileNav]); return <UIContext.Provider value={value}>{children}</UIContext.Provider> }
// Context hooks intentionally live with their provider to keep the theme contract local.
// eslint-disable-next-line react-refresh/only-export-components
export function useUI(){const value=useContext(UIContext);if(!value)throw new Error('useUI must be used within UIProvider');return value}
