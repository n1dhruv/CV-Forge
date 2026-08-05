import type { Session, User } from '@supabase/supabase-js'
import { useQueryClient } from '@tanstack/react-query'
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { supabase } from '../lib/supabase'

type AuthContextValue={session:Session|null;user:User|null;loading:boolean;signOut:()=>Promise<void>}
const AuthContext=createContext<AuthContextValue|null>(null)

export function AuthProvider({children}:{children:ReactNode}){
  const queryClient=useQueryClient(),[session,setSession]=useState<Session|null>(null),[loading,setLoading]=useState(true)
  useEffect(()=>{
    void supabase.auth.getSession().then(({data})=>{setSession(data.session);setLoading(false)})
    const {data:{subscription}}=supabase.auth.onAuthStateChange((event,next)=>{
      if(event==='SIGNED_IN'||event==='SIGNED_OUT')queryClient.clear()
      setSession(next);setLoading(false)
    })
    return()=>subscription.unsubscribe()
  },[queryClient])
  const value=useMemo<AuthContextValue>(()=>({session,user:session?.user??null,loading,signOut:async()=>{await supabase.auth.signOut()}}),[session,loading])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(){const value=useContext(AuthContext);if(!value)throw new Error('useAuth must be used inside AuthProvider');return value}
