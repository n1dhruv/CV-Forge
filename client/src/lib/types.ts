export type ItemType = 'experience' | 'project' | 'skill' | 'education' | 'certification'
export type JobStatus = 'queued' | 'running' | 'done' | 'failed'

export interface BulletPoint {
  id: string
  item_id: string
  text: string
  tags: string[]
  metrics: string | null
  display_order: number
  created_at: string
  updated_at: string
}

export interface SkillBankItem {
  id: string
  user_id: string
  type: ItemType
  title: string
  org: string | null
  start_date: string | null
  end_date: string | null
  raw_text: string | null
  tags: string[]
  source?: 'manual' | 'resume_import' | 'github'
  created_at: string
  updated_at: string
}

export interface SkillBankItemDetail extends SkillBankItem { bullet_points: BulletPoint[] }
export type SkillBankItemInput = Pick<SkillBankItem, 'type' | 'title'> & Partial<Pick<SkillBankItem, 'org' | 'start_date' | 'end_date' | 'raw_text' | 'tags'>>
export type BulletPointInput = Pick<BulletPoint, 'text'> & Partial<Pick<BulletPoint, 'tags' | 'metrics' | 'display_order'>>

export interface JDParsed {
  required_skills: string[]
  nice_to_have_skills: string[]
  responsibilities: string[]
  seniority: 'junior' | 'mid' | 'senior' | 'staff' | 'unspecified'
  ats_keywords: string[]
  action_verbs?: string[] | null
}

export interface JDRequirement { id: string; skill: string; importance: 'required' | 'nice_to_have'; category: string | null }
export interface JobDescription { id: string; status: JobStatus; parsed_json: JDParsed | null; requirements: JDRequirement[]; action_verbs?: string[] | null }
export interface JobDescriptionListItem { id: string; excerpt: string; status: JobStatus; created_at: string }
export interface JDParseQueued { job_description_id: string; background_job_id: string }
export interface BackgroundJob { status: JobStatus; result: Record<string, unknown> | null; error: string | null }
export interface LLMSettings {
  provider: string
  model: string
  masked_key: string
  embedding_provider?: string | null
  embedding_model?: string | null
  masked_embedding_key?: string | null
}
export interface LLMSettingsInput {
  provider: string
  model: string
  api_key: string
  embedding_provider?: string
  embedding_model?: string
  embedding_api_key?: string
}
export interface LLMSettingsSaved {
  provider: string
  model: string
  embedding_provider?: string | null
  embedding_model?: string | null
}
export interface LLMTestResult { success: boolean; error: string | null }
export type SupportedModels = Record<string, string[]>

export interface MatchedRequirement { id: string; text: string; score: number }
export interface MatchedBullet { id: string; text: string; score: number; requirements: MatchedRequirement[] }
export interface MatchedItem {
  id: string
  type: string
  title: string
  org: string | null
  start_date: string | null
  end_date: string | null
  bullets: MatchedBullet[]
}
export interface MatchResult { jd_id: string; pending_embeddings: boolean; items: MatchedItem[] }

export type ResumeImportItemType = 'experience' | 'project' | 'education' | 'certification'
export interface ResumeImportItem {
  type: ResumeImportItemType
  title: string
  org: string | null
  start_date: string | null
  end_date: string | null
  bullets: string[]
}
export interface ParsedResumeImport { items: ResumeImportItem[]; skills: string[] }
export interface ResumeImport {
  id: string
  status: JobStatus
  parsed_json: ParsedResumeImport | null
  created_at: string
  committed_at: string | null
}
export interface ResumeImportListItem { id: string; excerpt: string; status: JobStatus; created_at: string }
export interface ResumeImportQueued { resume_import_id: string; background_job_id: string }
export interface ResumeImportCommit { items: ResumeImportItem[]; skills: string[] }
export interface ResumeImportCommitResult { items: SkillBankItemDetail[] }

// Demo-only types retained for later-phase screens that already exist but are out of scope here.
export type JobState = JobStatus
export interface DemoTag { id: string; name: string; source: 'self_reported' | 'github' | 'leetcode' }
export interface DemoBullet { id: string; text: string; tags: DemoTag[]; metrics?: string[] }
export interface DemoSkillBankItem { id: string; type: Exclude<ItemType, 'certification'>; title: string; organization?: string; location?: string; startDate?: string; endDate?: string; description?: string; bullets: DemoBullet[]; skills: DemoTag[] }
export interface DemoParsedJobDescription { id: string; company: string; role: string; seniority: string; requiredSkills: string[]; niceToHaveSkills: string[]; atsKeywords: string[]; responsibilities: string[]; rawText: string }
export interface AsyncJob<T> { id: string; state: JobState; progress: number; stage: string; result?: T; error?: string }
export interface ResumeVersion { id: string; name: string; company: string; role: string; updatedAt: string; atsScore: number; texSource: string; pdfUrl?: string }
export interface RewriteSuggestion { id: string; section: string; sourceBullet: DemoBullet; tailoredText: string; relevance: number; matchedKeywords: string[]; decision: 'pending' | 'approved' | 'rejected' }
export interface Integration { provider: 'github' | 'leetcode'; connected: boolean; handle?: string; lastSyncedAt?: string; inferredSkills: DemoTag[]; state: JobState }
