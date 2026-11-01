import { useEffect, useRef } from 'react'

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Focus handling for a sheet. On open, focus moves to the element marked `data-autofocus`
 * (or the container). On close, it goes back to whatever opened it. When `modal` is set,
 * Tab stays inside the sheet. Escape always closes.
 */
export function useDialog<T extends HTMLElement>(open: boolean, onClose: () => void, modal: boolean) {
  const ref = useRef<T>(null)
  const closeRef = useRef(onClose)
  useEffect(() => {
    closeRef.current = onClose
  })

  useEffect(() => {
    if (!open) return
    const opener = document.activeElement as HTMLElement | null
    const root = ref.current
    const target = root?.querySelector<HTMLElement>('[data-autofocus]') ?? root
    target?.focus()

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        closeRef.current()
        return
      }
      if (!modal || e.key !== 'Tab' || !root) return
      const items = [...root.querySelectorAll<HTMLElement>(FOCUSABLE)]
      if (items.length === 0) return
      const first = items[0]!
      const last = items[items.length - 1]!
      if (e.shiftKey && (document.activeElement === first || document.activeElement === root)) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
    root?.addEventListener('keydown', onKey)
    return () => {
      root?.removeEventListener('keydown', onKey)
      // Only restore if focus is still inside the sheet (don't steal it from elsewhere).
      const active = document.activeElement
      if (opener?.isConnected && (!active || active === document.body || root?.contains(active))) {
        opener.focus()
      }
    }
  }, [open, modal])

  return ref
}
