import assert from 'node:assert/strict'
import test from 'node:test'
import type { Session } from '@supabase/supabase-js'
import { recoverSession } from './authSession.ts'

const session = { access_token: 'token' } as Session

test('session recovery returns the restored session', async () => {
  assert.equal(
    await recoverSession(async () => ({ data: { session } })),
    session,
  )
})

test('session recovery resolves signed out when storage fails', async () => {
  assert.equal(
    await recoverSession(async () => { throw new Error('storage unavailable') }),
    null,
  )
})

test('session recovery cannot leave the application loading forever', async () => {
  const never = () => new Promise<{ data: { session: Session | null } }>(() => {})

  assert.equal(await recoverSession(never, 5), null)
})
