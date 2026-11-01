import { type KeyboardEvent, useEffect, useId, useRef } from 'react'

interface Props {
  /** Ids of requests that were already raised in the answers about to be discarded. */
  requestIds: string[]
  confirmLabel: string
  onConfirm: () => void
  onKeep: () => void
}

/**
 * Inline guard for the one consequential case: redoing an answer that already raised a real
 * service request. Ordinary questions never need it. Focus moves to the primary action when
 * it opens; Escape keeps everything as it was.
 */
export function DiscardConfirm({ requestIds, confirmLabel, onConfirm, onKeep }: Props) {
  const titleId = useId()
  const bodyId = useId()
  const primary = useRef<HTMLButtonElement>(null)
  useEffect(() => primary.current?.focus(), [])

  const what =
    requestIds.length === 1
      ? `request ${requestIds[0]} that was`
      : `requests ${requestIds.slice(0, -1).join(', ')} and ${requestIds[requestIds.length - 1]} that were`

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.stopPropagation()
      onKeep()
    }
  }

  return (
    <div
      role="alertdialog"
      aria-labelledby={titleId}
      aria-describedby={bodyId}
      onKeyDown={onKeyDown}
      className="fade-in w-full max-w-[34rem] rounded-panel border border-line bg-paper p-4"
    >
      <p id={titleId} className="font-semibold">
        Discard these answers?
      </p>
      <p id={bodyId} className="mt-1 text-[0.9375rem] text-muted">
        This will discard answers below, including {what} already raised, and a new request may be
        raised.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          ref={primary}
          type="button"
          onClick={onConfirm}
          className="min-h-11 rounded-control bg-teal px-4 font-medium text-on-accent hover:bg-teal/90"
        >
          {confirmLabel}
        </button>
        <button
          type="button"
          onClick={onKeep}
          className="min-h-11 rounded-control border border-line px-4 font-medium hover:border-teal"
        >
          Keep it as it is
        </button>
      </div>
    </div>
  )
}
