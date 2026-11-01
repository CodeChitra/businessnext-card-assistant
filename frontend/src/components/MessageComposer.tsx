import { type FormEvent, type KeyboardEvent, type RefObject, useLayoutEffect, useRef } from 'react'

import { SendIcon } from './icons'

interface Props {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  disabled: boolean
  placeholder: string
  inputRef?: RefObject<HTMLTextAreaElement | null>
  note?: string | null
}

const MAX_HEIGHT = 168 // about six lines, then it scrolls

export function MessageComposer({ value, onChange, onSend, disabled, placeholder, inputRef, note }: Props) {
  const own = useRef<HTMLTextAreaElement | null>(null)
  const local = inputRef ?? own
  const canSend = !disabled && value.trim().length > 0

  useLayoutEffect(() => {
    const el = local.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`
  }, [value, local])

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (canSend) onSend()
  }
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends; Shift+Enter (or an IME composition) keeps typing.
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      if (canSend) onSend()
    }
  }

  return (
    <form
      onSubmit={submit}
      className="shrink-0 border-t border-line bg-mist px-3 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-6"
    >
      <div className="mx-auto max-w-[50rem]">
        <div className="flex items-end gap-2 rounded-panel border border-line bg-paper p-1.5 pl-4 transition-colors duration-150 focus-within:border-teal focus-within:ring-1 focus-within:ring-teal">
          <textarea
            ref={local}
            aria-label="Message"
            aria-describedby="composer-note"
            rows={1}
            className="max-h-[168px] min-h-[2.75rem] min-w-0 flex-1 resize-none bg-transparent py-2.5 leading-normal outline-none placeholder:text-muted focus-visible:outline-none"
            value={value}
            placeholder={placeholder}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={onKeyDown}
            maxLength={2000}
          />
          <button
            type="submit"
            disabled={!canSend}
            aria-label="Send message"
            className="grid h-11 w-11 shrink-0 place-items-center rounded-control bg-teal text-on-accent transition-opacity duration-150 hover:bg-teal/90 disabled:bg-line disabled:text-muted"
          >
            <SendIcon />
          </button>
        </div>
        <p id="composer-note" className="mt-1.5 px-1 text-xs text-muted">
          {note ?? 'Don’t share your full card number, PIN or CVV.'}
          <span className="max-sm:hidden"> Enter to send, Shift+Enter for a new line.</span>
        </p>
      </div>
    </form>
  )
}
