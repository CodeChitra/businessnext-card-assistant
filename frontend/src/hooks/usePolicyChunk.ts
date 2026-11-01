import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { PolicyChunk } from '../api/types'

// Policy text is immutable for a running backend, so a module-level cache is safe.
const cache = new Map<string, Promise<PolicyChunk>>()

export function fetchChunk(id: string): Promise<PolicyChunk> {
  let pending = cache.get(id)
  if (!pending) {
    pending = api.policyChunk(id)
    pending.catch(() => cache.delete(id)) // allow a retry after a failure
    cache.set(id, pending)
  }
  return pending
}

export type ChunkState =
  | { status: 'loading' }
  | { status: 'ok'; chunk: PolicyChunk }
  | { status: 'error' }

/** Callers remount per id (React key), so the initial state is always "loading". */
export function usePolicyChunk(id: string): ChunkState {
  const [state, setState] = useState<ChunkState>({ status: 'loading' })
  useEffect(() => {
    let live = true
    fetchChunk(id)
      .then((chunk) => live && setState({ status: 'ok', chunk }))
      .catch(() => live && setState({ status: 'error' }))
    return () => {
      live = false
    }
  }, [id])
  return state
}
