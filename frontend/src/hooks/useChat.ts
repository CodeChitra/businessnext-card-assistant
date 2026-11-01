import { useCallback, useRef, useState } from 'react'

import { api } from '../api/client'
import type { AgentResponse, ProgressEvent, Simulate } from '../api/types'

export interface CustomerTurn {
  id: string
  role: 'customer'
  text: string
}

export interface AgentTurn {
  id: string
  role: 'agent'
  status: 'streaming' | 'done' | 'error'
  steps: ProgressEvent[]
  response?: AgentResponse
  error?: string
  simulate?: Simulate | null
  /** The answer arrived live in this session, so its text is revealed progressively. */
  animate?: boolean
}

export type Turn = CustomerTurn | AgentTurn

let counter = 0
const nextId = () => `t${++counter}`

/** Customer turns before `index` that the server has completed (answered). */
export function completedBefore(turns: readonly Turn[], index: number): number {
  let n = 0
  for (let i = 0; i < index; i++) {
    const t = turns[i]
    const next = turns[i + 1]
    if (t?.role === 'customer' && next?.role === 'agent' && next.status === 'done') n++
  }
  return n
}

/** One conversation per selected customer; switching customer starts a new thread. */
export function useChat(customerId: string | null) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [busy, setBusy] = useState(false)
  const threadId = useRef<string | null>(null)
  const abort = useRef<AbortController | null>(null)

  const reset = useCallback(() => {
    abort.current?.abort()
    threadId.current = null
    setTurns([])
    setBusy(false)
  }, [])

  const updateAgent = (id: string, patch: (t: AgentTurn) => AgentTurn) =>
    setTurns((all) => all.map((t) => (t.id === id && t.role === 'agent' ? patch(t) : t)))

  // `keep` set = fork: drop turns[keep:] (the edited/replayed message and everything after it)
  // and ask the server to rewind its thread to the same point.
  const run = useCallback(
    async (text: string, simulate: Simulate | null, keep?: number) => {
      const message = text.trim()
      if (!customerId || !message || busy) return
      const forking = keep !== undefined
      // Only completed turns exist on the server; a thread must exist to rewind it.
      const rewindTo = forking && threadId.current ? completedBefore(turns, keep) : undefined
      const agentId = nextId()
      setTurns((all) => [
        ...(forking ? all.slice(0, keep) : all),
        { id: nextId(), role: 'customer', text: message },
        { id: agentId, role: 'agent', status: 'streaming', steps: [], simulate },
      ])
      setBusy(true)
      const controller = new AbortController()
      abort.current = controller
      try {
        const response = await api.streamChat(
          {
            customer_id: customerId,
            message,
            thread_id: threadId.current,
            simulate,
            ...(rewindTo !== undefined ? { rewind_to: rewindTo } : {}),
          },
          (step) => updateAgent(agentId, (t) => ({ ...t, steps: [...t.steps, step] })),
          controller.signal,
        )
        threadId.current = response.meta.thread_id // after a fork this is the new thread
        updateAgent(agentId, (t) => ({ ...t, status: 'done', response, animate: true }))
      } catch (err) {
        if (controller.signal.aborted) return
        const error = err instanceof Error ? err.message : 'Something went wrong.'
        updateAgent(agentId, (t) => ({ ...t, status: 'error', error }))
      } finally {
        if (abort.current === controller) setBusy(false)
      }
    },
    [customerId, busy, turns],
  )

  const send = useCallback(
    (text: string, simulate: Simulate | null = null) => run(text, simulate),
    [run],
  )

  /** Edit or replay: re-ask from the customer message at `turnIndex`, discarding it and all after. */
  const rewind = useCallback(
    (turnIndex: number, text: string) => run(text, null, turnIndex),
    [run],
  )

  return { turns, busy, send, rewind, reset }
}
