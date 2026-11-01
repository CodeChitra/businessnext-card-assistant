import { type KeyboardEvent, useEffect, useLayoutEffect, useRef, useState } from 'react'

import { DiscardConfirm } from './DiscardConfirm'
import { PencilIcon } from './icons'

interface Props {
  text: string
  disabled: boolean
  /** Request ids in the answers an edit would discard (empty = no confirmation needed). */
  raisedRequests: string[]
  onEdit: (text: string) => void
  /** The editor opened: the conversation should stop following new content. */
  onOpen?: () => void
}

const MAX_HEIGHT = 168

/** A customer message, with an inline editor. Sending an edit discards it and everything after. */
export function EditableMessage({ text, disabled, raisedRequests, onEdit, onOpen }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(text)
  const [confirming, setConfirming] = useState(false)
  const editButton = useRef<HTMLButtonElement>(null)
  const area = useRef<HTMLTextAreaElement>(null)
  const restoreFocus = useRef(false)

  const trimmed = draft.trim()
  const canSend = !disabled && trimmed.length > 0 && trimmed !== text.trim()

  useEffect(() => {
    if (editing) {
      const el = area.current
      el?.focus()
      el?.setSelectionRange(el.value.length, el.value.length)
    } else if (restoreFocus.current) {
      restoreFocus.current = false
      editButton.current?.focus()
    }
  }, [editing])

  useLayoutEffect(() => {
    const el = area.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`
  }, [draft, editing])

  const open = () => {
    onOpen?.()
    setDraft(text)
    setConfirming(false)
    setEditing(true)
  }
  const cancel = () => {
    restoreFocus.current = true
    setConfirming(false)
    setEditing(false)
  }
  const submit = () => {
    if (!canSend) return
    if (raisedRequests.length > 0) setConfirming(true)
    else onEdit(trimmed)
  }
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Escape') {
      e.stopPropagation()
      cancel()
    } else if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  if (!editing) {
    return (
      <div className="group flex items-start justify-end gap-1">
        <p className="sr-only">You said:</p>
        <button
          ref={editButton}
          type="button"
          onClick={open}
          disabled={disabled}
          aria-label="Edit message"
          title="Edit message"
          className="grid h-11 w-11 shrink-0 place-items-center rounded-control text-muted opacity-0 hover:bg-sunk hover:text-ink focus-visible:opacity-100 group-hover:opacity-100 pointer-coarse:opacity-100 disabled:cursor-not-allowed disabled:text-muted/50 disabled:hover:bg-transparent md:h-9 md:w-9"
        >
          <PencilIcon width={16} height={16} />
        </button>
        <p className="max-w-[min(85%,36rem)] whitespace-pre-wrap break-words rounded-message rounded-br-[6px] bg-navy-wash px-4 py-2.5">
          {text}
        </p>
      </div>
    )
  }

  return (
    <div className="ml-auto w-full max-w-[36rem] space-y-2">
      <div className="rounded-message border border-teal bg-paper p-2 pl-4 focus-within:ring-1 focus-within:ring-teal">
        <textarea
          ref={area}
          aria-label="Edit your message"
          rows={1}
          maxLength={2000}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          readOnly={confirming}
          className="block max-h-[168px] min-h-[2.5rem] w-full resize-none bg-transparent py-2 leading-normal outline-none focus-visible:outline-none"
        />
      </div>
      {confirming ? (
        <DiscardConfirm
          requestIds={raisedRequests}
          confirmLabel="Edit and send"
          onConfirm={() => onEdit(trimmed)}
          onKeep={cancel}
        />
      ) : (
        <div className="flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={cancel}
            className="min-h-11 rounded-control border border-line px-4 text-[0.9375rem] font-medium hover:border-teal"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={!canSend}
            className="min-h-11 rounded-control bg-teal px-4 text-[0.9375rem] font-medium text-on-accent hover:bg-teal/90 disabled:bg-line disabled:text-muted"
          >
            Send edited message
          </button>
        </div>
      )}
    </div>
  )
}
