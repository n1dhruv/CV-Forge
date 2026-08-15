import type { Session } from '@supabase/supabase-js'

type SessionResponse = { data: { session: Session | null } }

export async function recoverSession(
  getSession: () => Promise<SessionResponse>,
  timeoutMs = 5_000,
): Promise<Session | null> {
  let timer: ReturnType<typeof setTimeout> | undefined
  try {
    return await Promise.race([
      getSession().then(({ data }) => data.session),
      new Promise<null>(resolve => { timer = setTimeout(() => resolve(null), timeoutMs) }),
    ])
  } catch {
    return null
  } finally {
    if (timer) clearTimeout(timer)
  }
}
