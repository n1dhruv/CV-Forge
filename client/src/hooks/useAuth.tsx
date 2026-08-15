import type { Session, User } from '@supabase/supabase-js'
import { useQueryClient } from '@tanstack/react-query'
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { supabase } from '@/lib/supabase'
import { recoverSession } from '@/lib/authSession'

type AuthContextValue={session:Session|null;user:User|null;loading:boolean;signOut:()=>Promise<void>}
const AuthContext=createContext<AuthContextValue|null>(null)

export function AuthProvider({children}:{children:ReactNode}){
  const queryClient=useQueryClient(),[session,setSession]=useState<Session|null>(null),[loading,setLoading]=useState(true)
  useEffect(()=>{
    let active=true
    void recoverSession(() => supabase.auth.getSession()).then(next=>{
      if(active){setSession(next);setLoading(false)}
    })
    const {data:{subscription}}=supabase.auth.onAuthStateChange((event,next)=>{
      if(event==='SIGNED_OUT')queryClient.clear()
      setSession(next);setLoading(false)
    })
    return()=>{active=false;subscription.unsubscribe()}
  },[queryClient])
  const value=useMemo<AuthContextValue>(()=>({session,user:session?.user??null,loading,signOut:async()=>{await supabase.auth.signOut()}}),[session,loading])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(){const value=useContext(AuthContext);if(!value)throw new Error('useAuth must be used inside AuthProvider');return value}
