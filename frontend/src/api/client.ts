import { readSSE } from './sse'
import type {
  AgentResponse,
  ChatRequest,
  CustomerSummary,
  Health,
  PolicyChunk,
  ProgressEvent,
} from './types'

// Same-origin by default (Vite proxies in dev). Set VITE_API_BASE to call a remote API.
const BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ?? ''

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res))
  return (await res.json()) as T
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { error?: string; detail?: unknown }
    if (typeof body.detail === 'string') return body.detail
    return body.error ?? res.statusText
  } catch {
    return res.statusText
  }
}

export const api = {
  health: () => getJSON<Health>('/health'),
  customers: () => getJSON<CustomerSummary[]>('/api/customers'),
  policyChunk: (chunkId: string) => {
    const [doc, section] = chunkId.split('#')
    return getJSON<PolicyChunk>(
      `/api/policies/${encodeURIComponent(doc ?? '')}/${encodeURIComponent(section ?? '')}`,
    )
  },

  /** Streams progress steps, resolves with the validated final response. */
  async streamChat(
    request: ChatRequest,
    onProgress: (event: ProgressEvent) => void,
    signal?: AbortSignal,
  ): Promise<AgentResponse> {
    const res = await fetch(`${BASE}/api/chat/stream`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'text/event-stream' },
      body: JSON.stringify(request),
      signal,
    })
    if (!res.ok || !res.body) throw new ApiError(res.status, await errorMessage(res))
    for await (const message of readSSE(res.body)) {
      if (message.event === 'progress') onProgress(message.data as ProgressEvent)
      else if (message.event === 'final') return message.data as AgentResponse
      else if (message.event === 'error') {
        const body = message.data as { error?: string }
        throw new ApiError(500, body.error ?? 'Something went wrong.')
      }
    }
    throw new ApiError(502, 'The response ended before an answer arrived.')
  },
}
