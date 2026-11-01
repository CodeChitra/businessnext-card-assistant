import { useCallback, useRef, useState } from 'react'

/** Within this distance of the end, the reader counts as "at the bottom". */
export const NEAR_BOTTOM_PX = 120

function prefersReducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

/**
 * The single scroll model for the conversation.
 *
 * The app shell never scrolls; this one container does. It follows new content only while the
 * reader is already near the bottom (or has just sent a message), so scrolling up to re-read is
 * never undone. It scrolls the container itself and never calls scrollIntoView, which would
 * also scroll every ancestor, including the page.
 */
export function useStickToBottom() {
  const el = useRef<HTMLDivElement | null>(null)
  const stuck = useRef(true)
  const lastTarget = useRef<number | null>(null) // where our own last scroll landed
  const [away, setAway] = useState(false) // scrolled up AND newer content has arrived
  const unseen = useRef(false)
  const released = useRef(false) // working above the end: growth is not news

  // A callback ref: the container is handed to React as a plain function, which keeps the
  // element out of render-time reads.
  const ref = useCallback((node: HTMLDivElement | null) => {
    el.current = node
  }, [])

  const toEnd = useCallback((smooth = false) => {
    const node = el.current
    if (!node) return
    lastTarget.current = node.scrollHeight - node.clientHeight
    node.scrollTo?.({
      top: node.scrollHeight,
      behavior: smooth && !prefersReducedMotion() ? 'smooth' : 'auto',
    })
  }, [])

  const onScroll = useCallback(() => {
    const node = el.current
    if (!node) return
    // Scroll events arrive a frame late. If the content grew in between, the echo of OUR OWN
    // scroll would be measured against the new, taller content and misread as the reader leaving.
    // The echo sits exactly where we scrolled to; a reader's scroll lands somewhere else.
    if (stuck.current && lastTarget.current !== null && Math.abs(node.scrollTop - lastTarget.current) <= 2) {
      return
    }
    released.current = false // a real scroll: the reader is navigating again
    stuck.current = node.scrollHeight - node.scrollTop - node.clientHeight <= NEAR_BOTTOM_PX
    if (stuck.current) {
      unseen.current = false
      setAway(false)
    }
  }, [])

  /** Content grew: follow it if the reader is at the bottom, otherwise note there is more. */
  const follow = useCallback(() => {
    if (stuck.current) {
      toEnd()
    } else if (!unseen.current && !released.current) {
      unseen.current = true
      setAway(true)
    }
  }, [toEnd])

  /** The reader just sent something: show it, whatever they were reading. */
  const stick = useCallback(() => {
    stuck.current = true
    released.current = false
    unseen.current = false
    setAway(false)
    toEnd()
  }, [toEnd])

  /** The reader is working on something above the end (editing a message): stop following. */
  const release = useCallback(() => {
    stuck.current = false
    released.current = true
  }, [])

  const jumpToLatest = useCallback(() => {
    stick()
    toEnd(true)
  }, [stick, toEnd])

  return { ref, onScroll, follow, stick, release, jumpToLatest, away }
}
