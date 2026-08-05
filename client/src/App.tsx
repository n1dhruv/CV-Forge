import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { useAuth } from './hooks/useAuth'
import { AuthPage } from './screens/AuthPage'
import { ATSScore } from './screens/ATSScore'
import { Dashboard } from './screens/Dashboard'
import { LatexEditor } from './screens/Editor'
import { Integrations } from './screens/Integrations'
import { JDInput } from './screens/JDInput'
import { MatchReview } from './screens/MatchReview'
import { SkillBank } from './screens/SkillBank'
import { Settings } from './screens/Settings'
import { Home } from './screens/Home'

function ProtectedWorkspace() {
  const {session,loading}=useAuth()
  if(loading)return <div className="grid min-h-screen place-items-center text-sm text-muted" role="status">Checking your session…</div>
  return session?<AppShell/>:<Navigate to="/sign-in" replace/>
}

export default function App(){return <Routes>
  <Route path="/" element={<Home/>}/>
  <Route path="/sign-in/*" element={<AuthPage mode="sign-in"/>}/>
  <Route path="/sign-up/*" element={<AuthPage mode="sign-up"/>}/>
  <Route element={<ProtectedWorkspace/>}>
    <Route path="dashboard" element={<Dashboard/>}/>
    <Route path="skill-bank" element={<SkillBank/>}/>
    <Route path="job-description" element={<JDInput/>}/>
    <Route path="settings" element={<Settings/>}/>
    <Route path="review" element={<MatchReview/>}/>
    <Route path="editor" element={<LatexEditor/>}/>
    <Route path="integrations" element={<Integrations/>}/>
    <Route path="ats" element={<ATSScore/>}/>
  </Route>
  <Route path="*" element={<Navigate to="/" replace/>}/>
</Routes>}
