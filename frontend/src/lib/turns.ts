import type { Turn } from '../hooks/useChat'

/** Ids of requests already raised in the turns from `from` on: what an edit or replay discards. */
export function raisedFrom(turns: readonly Turn[], from: number): string[] {
  return turns.slice(from).flatMap((t) => {
    const sr = t.role === 'agent' ? t.response?.service_request : null
    return sr ? [sr.request_id] : []
  })
}
