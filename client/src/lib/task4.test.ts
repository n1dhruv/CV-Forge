import assert from 'node:assert/strict'
import test from 'node:test'
import { assistantProposalIsStale, assistantUndoIsAvailable, orderedSelections, profileLinkError } from './task4.ts'
import type { MatchedItem, MatchedRequirement, RequirementMatch } from './types.ts'

type Equal<Left, Right> = (<Value>() => Value extends Left ? 1 : 2) extends (<Value>() => Value extends Right ? 1 : 2) ? true : false
type Expect<Value extends true> = Value
type _MatchedImportanceIsExact = Expect<Equal<MatchedRequirement['importance'], 'required' | 'nice_to_have'>>
type _RequirementImportanceIsExact = Expect<Equal<RequirementMatch['importance'], 'required' | 'nice_to_have'>>

const requirement: MatchedRequirement = {
  id: 'requirement-1',
  text: 'Python',
  importance: 'required',
  score: 0.9,
  confidence: 'strong',
  technology_evidence: ['Python'],
}

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
        requirements: [requirement],
      },
      {
        bullet_point_id: null,
        skill_bank_item_id: 'skill-1',
        text: 'Python',
        score: 0.7,
        confidence: 'moderate',
        recommended: false,
        requirements: [requirement],
      },
      {
        bullet_point_id: 'bullet-2',
        skill_bank_item_id: null,
        text: 'Improved reliability',
        score: 0.8,
        confidence: 'moderate',
        recommended: true,
        requirements: [requirement],
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

test('assistant undo is available only while the applied buffer is unchanged', () => {
  assert.equal(assistantUndoIsAvailable('assistant output', 'assistant output'), true)
  assert.equal(assistantUndoIsAvailable('assistant output', 'manual edit after apply'), false)
  assert.equal(assistantUndoIsAvailable(undefined, 'assistant output'), false)
})

test('match importance fixtures preserve the server literals', () => {
  const topLevel: RequirementMatch = {
    id: 'requirement-1',
    text: 'Python',
    importance: 'nice_to_have',
    named_technologies: ['Python'],
    technology_match_mode: 'any',
    technology_evidence: ['Python'],
    no_match: false,
  }
  assert.equal(requirement.importance, 'required')
  assert.equal(topLevel.importance, 'nice_to_have')
})
