export type Source = 'self_reported' | 'github' | 'leetcode'
export type ItemType = 'experience' | 'project' | 'skill' | 'education'
export type JobState = 'queued' | 'running' | 'done' | 'failed'
export interface SkillTag { id: string; name: string; source: Source }
export interface BulletPoint { id: string; text: string; tags: SkillTag[]; metrics?: string[] }
export interface SkillBankItem { id: string; type: ItemType; title: string; organization?: string; location?: string; startDate?: string; endDate?: string; description?: string; bullets: BulletPoint[]; skills: SkillTag[] }
export interface ParsedJobDescription { id: string; company: string; role: string; seniority: string; requiredSkills: string[]; niceToHaveSkills: string[]; atsKeywords: string[]; responsibilities: string[]; rawText: string }
export interface AsyncJob<T> { id: string; state: JobState; progress: number; stage: string; result?: T; error?: string }
export interface ResumeVersion { id: string; name: string; company: string; role: string; updatedAt: string; atsScore: number; texSource: string; pdfUrl?: string }
export interface RewriteSuggestion { id: string; section: string; sourceBullet: BulletPoint; tailoredText: string; relevance: number; matchedKeywords: string[]; decision: 'pending' | 'approved' | 'rejected' }
export interface AtsScore { versionId: string; score: number; matched: string[]; missing: string[] }
export interface Integration { provider: 'github' | 'leetcode'; connected: boolean; handle?: string; lastSyncedAt?: string; inferredSkills: SkillTag[]; state: JobState }
