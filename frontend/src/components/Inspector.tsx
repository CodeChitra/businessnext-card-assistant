import type { AgentResponse, ProgressEvent } from '../api/types'
import { BEHAVIOUR_LABEL, formatCost, ruleLabel } from '../lib/format'
import { WrenchIcon } from './icons'

function stepDetail(s: ProgressEvent): string | null {
  if (s.degraded) return 'unavailable, degraded mode'
  if (s.miss) return 'retrieval miss'
  if (typeof s.sources_found === 'number') return `${s.sources_found} documents`
  if (typeof s.issues_found === 'number' && s.issues_found > 0)
    return `${s.issues_found} issue${s.issues_found === 1 ? '' : 's'}, repairing`
  return null
}

/** Reviewer layer: what the pipeline did for this answer. Hidden from the customer view. */
export function Inspector({ steps, response }: { steps: ProgressEvent[]; response?: AgentResponse }) {
  const m = response?.meta
  return (
    <details
      className="max-w-[68ch] rounded-panel border border-dashed border-line bg-sunk/60 text-sm"
      open
    >
      <summary className="flex min-h-10 cursor-pointer select-none items-center gap-2 px-4 py-2 font-medium text-muted">
        <WrenchIcon width={15} height={15} />
        Developer details
        <span className="font-normal">(not shown to customers)</span>
      </summary>
      <div className="grid gap-4 border-t border-dashed border-line px-4 py-3 sm:grid-cols-2">
        <section>
          <h4 className="mb-1 font-semibold">Pipeline</h4>
          <ol className="space-y-0.5 text-muted">
            {steps.map((s, i) => {
              const d = stepDetail(s)
              return (
                <li key={`${s.step}-${i}`}>
                  {s.label}
                  {d && <span className="text-ink"> ({d})</span>}
                </li>
              )
            })}
          </ol>
        </section>
        {m && response && (
          <section>
            <h4 className="mb-1 font-semibold">Outcome</h4>
            <dl className="figures grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5 text-muted">
              <dt>Behaviour</dt>
              <dd className="text-ink">{BEHAVIOUR_LABEL[response.behaviour]}</dd>
              <dt>Rules fired</dt>
              <dd className="text-ink">
                {m.rules_fired.length ? m.rules_fired.map(ruleLabel).join(', ') : 'None'}
              </dd>
              <dt>Model</dt>
              <dd className="break-all text-ink">
                {m.model ?? 'No model call'}
                {m.fallback_used ? ' (fallback)' : ''}
              </dd>
              <dt>Tokens</dt>
              <dd className="text-ink">
                {m.input_tokens.toLocaleString()} in, {m.output_tokens.toLocaleString()} out
              </dd>
              <dt>Cost</dt>
              <dd className="text-ink">{formatCost(m.cost_usd)}</dd>
              <dt>Latency</dt>
              <dd className="text-ink">{(m.latency_ms / 1000).toFixed(1)} s</dd>
              <dt>Checks</dt>
              <dd className="text-ink">
                {m.safe_fallback
                  ? 'Failed after repair, safe response sent'
                  : m.repaired
                    ? 'Repaired once, then passed'
                    : 'Passed first time'}
              </dd>
              <dt>Prompts</dt>
              <dd className="break-all text-ink">{Object.values(m.prompt_versions).join(', ')}</dd>
              {m.trace_id && (
                <>
                  <dt>Trace</dt>
                  <dd className="break-all text-ink">{m.trace_id}</dd>
                </>
              )}
            </dl>
          </section>
        )}
      </div>
    </details>
  )
}
