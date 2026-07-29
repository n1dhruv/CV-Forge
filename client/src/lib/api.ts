import type { AsyncJob, Integration, ParsedJobDescription, ResumeVersion, SkillBankItem } from './types'
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
class ApiError extends Error { constructor(public status: number, message: string) { super(message) } }
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers: { ...(init?.body instanceof FormData ? {} : {'Content-Type':'application/json'}), ...init?.headers } })
  if (!response.ok) throw new ApiError(response.status, (await response.text()) || 'The server could not complete this request.')
  return response.json() as Promise<T>
}
export const api = {
  skillBank: { list: () => request<SkillBankItem[]>('/api/skill-bank'), create: (item: Omit<SkillBankItem,'id'>) => request<SkillBankItem>('/api/skill-bank',{method:'POST',body:JSON.stringify(item)}), update: (item: SkillBankItem) => request<SkillBankItem>(`/api/skill-bank/${item.id}`,{method:'PUT',body:JSON.stringify(item)}), delete: (id:string)=>request<void>(`/api/skill-bank/${id}`,{method:'DELETE'}) },
  jd: { parseText: (rawText:string)=>request<AsyncJob<ParsedJobDescription>>('/api/jd/parse',{method:'POST',body:JSON.stringify({raw_text:rawText})}), upload: (file:File)=>{const body=new FormData();body.append('file',file);return request<AsyncJob<ParsedJobDescription>>('/api/jd/upload',{method:'POST',body})} },
  jobs: { get: <T>(id:string)=>request<AsyncJob<T>>(`/api/jobs/${id}`) },
  resumes: { list:()=>request<ResumeVersion[]>('/api/resume'), compile:(id:string,texSource:string)=>request<AsyncJob<ResumeVersion>>(`/api/editor/${id}/compile`,{method:'POST',body:JSON.stringify({tex_source:texSource})}) },
  integrations: { list:()=>request<Integration[]>('/api/integrations') }
}
