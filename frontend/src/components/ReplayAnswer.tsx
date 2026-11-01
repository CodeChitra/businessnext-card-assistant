import { useEffect, useRef, useState } from 'react'

import { DiscardConfirm } from './DiscardConfirm'
import { ReplayIcon } from './icons'

interface Props {
  disabled: boolean
  /** Request ids in the answers a replay would discard (empty = no confirmation needed). */
  raisedRequests: string[]
  onReplay: () => void
}

/** Re-asks the same question. Offered on the latest answer only. */
export function ReplayAnswer({ disabled, raisedRequests, onReplay }: Props) {
  const [confirming, setConfirming] = useState(false)
  const button = useRef<HTMLButtonElement>(null)
  const restoreFocus = useRef(false)

  useEffect(() => {
    if (!confirming && restoreFocus.current) {
      restoreFocus.current = false
      button.current?.focus()
    }
  }, [confirming])

  if (confirming) {
    return (
      <DiscardConfirm
        requestIds={raisedRequests}
        confirmLabel="Replay and continue"
        onConfirm={() => {
          setConfirming(false)
          onReplay()
        }}
        onKeep={() => {
          restoreFocus.current = true
          setConfirming(false)
        }}
      />
    )
  }
  return (
    <button
      ref={button}
      type="button"
      disabled={disabled}
      onClick={() => (raisedRequests.length > 0 ? setConfirming(true) : onReplay())}
      aria-label="Replay answer"
      className="inline-flex min-h-11 items-center gap-1.5 rounded-control px-2 text-[0.9375rem] text-muted hover:bg-sunk hover:text-ink disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent md:min-h-9"
    >
      <ReplayIcon width={16} height={16} />
      Replay answer
    </button>
  )
}
