// Mirrors backend/src/grounded_agent/domain/response.py and api/schemas.py.
// Keep in sync when the backend contract changes.

export type Behaviour = 'answer' | 'decline_with_reason' | 'refuse' | 'raise_request'
export type ReasonCode = 'AA01' | 'AA02' | 'AA03' | 'AA04' | 'AA05' | 'AA06'
export type Simulate = 'timeout' | 'primary_down'

export interface Citation {
  type: 'policy' | 'account' | 'rule'
  ref: string
}

export interface Claim {
  text: string
  citations: Citation[]
}

export interface ServiceRequestRef {
  request_id: string
  queue: string
  sla_hours: number
}

export interface ResponseMeta {
  model: string | null
  prompt_versions: Record<string, string>
  input_tokens: number
  output_tokens: number
  cost_usd: number
  latency_ms: number
  trace_id: string | null
  thread_id: string | null
  fallback_used: boolean
  repaired: boolean
  safe_fallback: boolean
  retrieval_miss: boolean
  rules_fired: string[]
}

export interface AgentResponse {
  behaviour: Behaviour
  message: string
  claims: Claim[]
  reason_codes: ReasonCode[]
  service_request: ServiceRequestRef | null
  degraded: boolean
  /** 0-3 short questions the customer might ask next; always safe to send as-is. */
  follow_ups: string[]
  meta: ResponseMeta
}

export interface ProgressEvent {
  step: string
  label: string
  degraded?: boolean
  sources_found?: number
  miss?: boolean
  issues_found?: number
}

export interface CustomerSummary {
  customer_id: string
  name: string
  card_product: string
}

export interface PolicyChunk {
  chunk_id: string
  doc_id: string
  title: string
  heading: string | null
  section: string
  version: string
  effective_date: string | null
  trust: 'policy' | 'non_policy'
  text: string
}

export interface Health {
  status: 'ok'
  as_of_date: string
  chunks_indexed: number
  models: Record<string, string | null>
  prompt_versions: Record<string, string>
  tracing: { enabled: boolean; project: string | null; reason: string }
  demo_faults: boolean
}

export interface ChatRequest {
  customer_id: string
  message: string
  thread_id?: string | null
  simulate?: Simulate | null
  /**
   * Edit / replay: with `thread_id`, the server forks the thread keeping only the first
   * `rewind_to` completed customer turns (0 = none) and answers `message` on the fork.
   * The response's `meta.thread_id` is the new thread. Never sent without `thread_id`.
   */
  rewind_to?: number | null
}
