import type { MatchedBullet, MatchedItem, RewriteSelection } from './types'

export function selectionKey(selection: RewriteSelection) {
  return `${selection.kind}:${selection.id}`
}

export function matchSelection(bullet: MatchedBullet): RewriteSelection | undefined {
  return bullet.bullet_point_id
    ? { kind: 'bullet', id: bullet.bullet_point_id }
    : bullet.skill_bank_item_id
      ? { kind: 'skill', id: bullet.skill_bank_item_id }
      : undefined
}

export function orderedSelections(items: MatchedItem[], selected?: Set<string>) {
  return items.flatMap(item => item.bullets.flatMap(bullet => {
    const selection = matchSelection(bullet)
    if (!selection || (selected ? !selected.has(selectionKey(selection)) : !bullet.recommended)) return []
    return [selection]
  }))
}

export function profileLinkError(value: string) {
  if (!value) return ''
  try {
    const url = new URL(value)
    if ((url.protocol === 'http:' || url.protocol === 'https:') && url.host) return ''
  } catch {}
  return 'Use a complete http:// or https:// URL.'
}

export function assistantProposalIsStale(capturedSource: string, currentSource: string) {
  return capturedSource !== currentSource
}
