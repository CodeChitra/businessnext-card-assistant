import { useEffect, useState } from 'react'

import type { ServiceRequestRef } from '../api/types'
import { QUEUE_LABEL, formatSla } from '../lib/format'
import { CopyIcon } from './icons'

/** Receipt for a request the backend confirmed. Never rendered without a real `request_id`. */
export function SupportCaseCard({ request, title }: { request: ServiceRequestRef; title: string }) {
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    if (!copied) return
    const t = window.setTimeout(() => setCopied(false), 2000)
    return () => window.clearTimeout(t)
  }, [copied])

  const copy = () => {
    void navigator.clipboard?.writeText(request.request_id).then(() => setCopied(true), () => {})
  }

  return (
    <section aria-label="Outcome" className="max-w-[34rem] rounded-panel border border-line bg-paper">
      <header className="flex items-start justify-between gap-4 border-b border-line px-4 py-3">
        <h3 className="font-semibold">{title}</h3>
        <span className="inline-flex shrink-0 items-center gap-1.5 rounded-control bg-amber-wash px-2 py-0.5 text-sm font-medium text-amber">
          <span className="h-2 w-2 rounded-full border-2 border-amber" aria-hidden />
          Under review
        </span>
      </header>
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 px-4 py-3 text-[0.9375rem]">
        <dt className="text-muted">Reference</dt>
        <dd className="flex flex-wrap items-center gap-2">
          <span className="figures font-semibold tracking-wide">{request.request_id}</span>
          <button
            type="button"
            onClick={copy}
            className="inline-flex min-h-8 items-center gap-1 rounded-control px-1.5 text-sm text-teal hover:bg-teal-wash"
            aria-label={`Copy reference ${request.request_id}`}
          >
            <CopyIcon width={15} height={15} />
            <span aria-live="polite">{copied ? 'Copied' : 'Copy'}</span>
          </button>
        </dd>
        <dt className="text-muted">Handled by</dt>
        <dd>{QUEUE_LABEL[request.queue] ?? request.queue}</dd>
        <dt className="text-muted">Reply expected within</dt>
        <dd className="figures">{formatSla(request.sla_hours)}</dd>
      </dl>
      <p className="border-t border-line px-4 py-2.5 text-sm text-muted">
        Keep the reference handy if you contact us about this.
      </p>
    </section>
  )
}
