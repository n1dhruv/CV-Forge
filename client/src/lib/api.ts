import type {
  BackgroundJob, BulletPoint, BulletPointInput, JobDescription, JobDescriptionListItem,
  JDParseQueued, LLMSettings, LLMSettingsInput, LLMSettingsSaved, LLMTestResult, SkillBankItem,
  SkillBankItemDetail, SkillBankItemInput, SupportedModels,
} from './types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
type GetToken = () => Promise<string | null>

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

export function createApiClient(getToken: GetToken) {
  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const token = await getToken()
    const response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: {
        ...(init.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    })
    if (!response.ok) {
      const body = await response.json().catch(() => null) as { detail?: string } | null
      throw new ApiError(response.status, body?.detail ?? 'The server could not complete this request.')
    }
    if (response.status === 204) return undefined as T
    return response.json() as Promise<T>
  }

  return {
    skillBank: {
      list: (type?: string) => request<SkillBankItem[]>(`/api/skill_bank/items${type ? `?type=${encodeURIComponent(type)}` : ''}`),
      get: (id: string) => request<SkillBankItemDetail>(`/api/skill_bank/items/${id}`),
      create: (item: SkillBankItemInput) => request<SkillBankItem>('/api/skill_bank/items', { method: 'POST', body: JSON.stringify(item) }),
      update: (id: string, item: Partial<SkillBankItemInput>) => request<SkillBankItem>(`/api/skill_bank/items/${id}`, { method: 'PUT', body: JSON.stringify(item) }),
      delete: (id: string) => request<void>(`/api/skill_bank/items/${id}`, { method: 'DELETE' }),
      createBullet: (itemId: string, bullet: BulletPointInput) => request<BulletPoint>(`/api/skill_bank/items/${itemId}/bullets`, { method: 'POST', body: JSON.stringify(bullet) }),
      updateBullet: (id: string, bullet: Partial<BulletPointInput>) => request<BulletPoint>(`/api/skill_bank/bullets/${id}`, { method: 'PUT', body: JSON.stringify(bullet) }),
      deleteBullet: (id: string) => request<void>(`/api/skill_bank/bullets/${id}`, { method: 'DELETE' }),
    },
    llmSettings: {
      get: () => request<LLMSettings>('/api/settings/llm'),
      save: (settings: LLMSettingsInput) => request<LLMSettingsSaved>('/api/settings/llm', { method: 'POST', body: JSON.stringify(settings) }),
      remove: () => request<void>('/api/settings/llm', { method: 'DELETE' }),
      test: () => request<LLMTestResult>('/api/settings/llm/test', { method: 'POST' }),
      supportedModels: () => request<SupportedModels>('/api/settings/llm/supported-models'),
    },
    jd: {
      parseText: (rawText: string) => request<JDParseQueued>('/api/jd/parse', { method: 'POST', body: JSON.stringify({ raw_text: rawText }) }),
      parsePdf: (file: File) => { const body = new FormData(); body.append('file', file); return request<JDParseQueued>('/api/jd/parse', { method: 'POST', body }) },
      list: () => request<JobDescriptionListItem[]>('/api/jd'),
      get: (id: string) => request<JobDescription>(`/api/jd/${id}`),
      getStatus: (id: string) => request<BackgroundJob>(`/api/background_jobs/${id}`),
    },
  }
}
