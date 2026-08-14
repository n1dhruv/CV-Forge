import assert from 'node:assert/strict'
import test from 'node:test'
import { assistantProposalIsStale, orderedSelections, profileLinkError } from './task4.ts'
import type { MatchedItem } from './types.ts'

const items: MatchedItem[] = [
  {
    id: 'experience-1',
    type: 'experience',
    title: 'Engineer',
    org: 'Example',
    start_date: null,
    end_date: null,
    bullets: [
      {
        bullet_point_id: 'bullet-1',
        skill_bank_item_id: null,
        text: 'Built an API',
        score: 0.9,
        confidence: 'strong',
        recommended: true,
        requirements: [],
      },
      {
        bullet_point_id: null,
        skill_bank_item_id: 'skill-1',
        text: 'Python',
        score: 0.7,
        confidence: 'moderate',
        recommended: false,
        requirements: [],
      },
      {
        bullet_point_id: 'bullet-2',
        skill_bank_item_id: null,
        text: 'Improved reliability',
        score: 0.8,
        confidence: 'moderate',
        recommended: true,
        requirements: [],
      },
    ],
  },
]

test('recommended selection includes bullet and skill evidence in match order', () => {
  items[0].bullets[1].recommended = true
  assert.deepEqual(orderedSelections(items), [
    { kind: 'bullet', id: 'bullet-1' },
    { kind: 'skill', id: 'skill-1' },
    { kind: 'bullet', id: 'bullet-2' },
  ])
  items[0].bullets[1].recommended = false
})

test('manual overrides retain server match order in the rewrite payload', () => {
  assert.deepEqual(
    orderedSelections(items, new Set(['skill:skill-1', 'bullet:bullet-2'])),
    [
      { kind: 'skill', id: 'skill-1' },
      { kind: 'bullet', id: 'bullet-2' },
    ],
  )
})

test('profile links use the same http and https boundary as the server', () => {
  assert.equal(profileLinkError(''), '')
  assert.equal(profileLinkError('https://example.com/profile'), '')
  assert.equal(profileLinkError('ftp://example.com/profile'), 'Use a complete http:// or https:// URL.')
  assert.equal(profileLinkError('linkedin.com/in/example'), 'Use a complete http:// or https:// URL.')
})

test('assistant proposals become stale when the editor changes from the captured source', () => {
  assert.equal(assistantProposalIsStale('before', 'before'), false)
  assert.equal(assistantProposalIsStale('before', 'edited while pending'), true)
})
