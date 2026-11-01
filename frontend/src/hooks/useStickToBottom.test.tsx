import { act, renderHook } from '@testing-library/react'

import { NEAR_BOTTOM_PX, useStickToBottom } from './useStickToBottom'

function fakeScroller(init: { scrollHeight: number; scrollTop: number; clientHeight: number }) {
  const node = { ...init, scrollTo: vi.fn() }
  return node as unknown as HTMLDivElement & { scrollTo: ReturnType<typeof vi.fn> }
}

function setup(node: ReturnType<typeof fakeScroller>) {
  const hook = renderHook(() => useStickToBottom())
  act(() => hook.result.current.ref(node))
  return hook
}

describe('useStickToBottom', () => {
  it('scrolls the container itself, never the page', () => {
    const spy = vi.fn()
    Element.prototype.scrollIntoView = spy
    const node = fakeScroller({ scrollHeight: 2000, scrollTop: 0, clientHeight: 700 })
    const { result } = setup(node)
    act(() => result.current.follow())
    expect(node.scrollTo).toHaveBeenCalledWith({ top: 2000, behavior: 'auto' })
    expect(spy).not.toHaveBeenCalled()
  })

  it('follows new content while the reader is near the bottom', () => {
    const node = fakeScroller({ scrollHeight: 2000, scrollTop: 1300 - NEAR_BOTTOM_PX + 10, clientHeight: 700 })
    const { result } = setup(node)
    act(() => result.current.onScroll())
    node.scrollTo.mockClear()
    act(() => result.current.follow())
    expect(node.scrollTo).toHaveBeenCalledOnce()
    expect(result.current.away).toBe(false)
  })

  it('does not yank a reader who scrolled up, and offers a way back', () => {
    const node = fakeScroller({ scrollHeight: 2000, scrollTop: 100, clientHeight: 700 })
    const { result } = setup(node)
    act(() => result.current.onScroll()) // the reader is far from the end
    act(() => result.current.follow()) // more content arrives
    expect(node.scrollTo).not.toHaveBeenCalled()
    expect(result.current.away).toBe(true)
  })

  it('jumps to the latest on request and stops offering the jump', () => {
    const node = fakeScroller({ scrollHeight: 2000, scrollTop: 100, clientHeight: 700 })
    const { result } = setup(node)
    act(() => result.current.onScroll())
    act(() => result.current.follow())
    act(() => result.current.jumpToLatest())
    expect(node.scrollTo).toHaveBeenLastCalledWith({ top: 2000, behavior: 'smooth' })
    expect(result.current.away).toBe(false)
  })

  it('a message the reader just sent always scrolls into view', () => {
    const node = fakeScroller({ scrollHeight: 2000, scrollTop: 100, clientHeight: 700 })
    const { result } = setup(node)
    act(() => result.current.onScroll())
    act(() => result.current.stick())
    expect(node.scrollTo).toHaveBeenCalledWith({ top: 2000, behavior: 'auto' })
    node.scrollTo.mockClear()
    act(() => result.current.follow()) // and the answer that follows is followed
    expect(node.scrollTo).toHaveBeenCalledOnce()
  })

  it('does not fight a reader who scrolls up while the content keeps growing', () => {
    // During a reveal the height changes every few milliseconds; a scroll up must still win.
    const node = fakeScroller({ scrollHeight: 2000, scrollTop: 1300, clientHeight: 700 })
    const { result } = setup(node)
    act(() => result.current.follow())
    for (const [height, top] of [[2040, 900], [2080, 500], [2120, 100]] as const) {
      Object.assign(node, { scrollHeight: height, scrollTop: top })
      act(() => result.current.onScroll()) // the reader moves up...
      node.scrollTo.mockClear()
      act(() => result.current.follow()) // ...and the answer grows again
      expect(node.scrollTo).not.toHaveBeenCalled()
    }
    expect(result.current.away).toBe(true)
  })

  it('does not mistake the late echo of its own scroll for the reader leaving', () => {
    // Scroll events arrive a frame late; by then a revealed answer may have made the content taller.
    const node = fakeScroller({ scrollHeight: 1057, scrollTop: 0, clientHeight: 600 })
    const { result } = setup(node)
    act(() => result.current.follow()) // we scroll to the end: top should be 457
    Object.assign(node, { scrollHeight: 1825, scrollTop: 457 }) // the answer grew; the browser reports our scroll
    act(() => result.current.onScroll())
    node.scrollTo.mockClear()
    act(() => result.current.follow()) // so the next growth is still followed
    expect(node.scrollTo).toHaveBeenCalledWith({ top: 1825, behavior: 'auto' })
    expect(result.current.away).toBe(false)
  })

  it('still notices a reader who scrolls somewhere else', () => {
    const node = fakeScroller({ scrollHeight: 1057, scrollTop: 0, clientHeight: 600 })
    const { result } = setup(node)
    act(() => result.current.follow())
    Object.assign(node, { scrollHeight: 1825, scrollTop: 200 }) // not where we scrolled to
    act(() => result.current.onScroll())
    node.scrollTo.mockClear()
    act(() => result.current.follow())
    expect(node.scrollTo).not.toHaveBeenCalled()
    expect(result.current.away).toBe(true)
  })

  it('stops following once the reader starts editing above the end', () => {
    const node = fakeScroller({ scrollHeight: 2000, scrollTop: 1300, clientHeight: 700 })
    const { result } = setup(node)
    act(() => result.current.release())
    act(() => result.current.follow()) // the editor made the content taller
    expect(node.scrollTo).not.toHaveBeenCalled()
    expect(result.current.away).toBe(false) // the editor is not news, so no "Jump to latest"
  })

  it('offers the jump again once the reader scrolls on their own after editing', () => {
    const node = fakeScroller({ scrollHeight: 2000, scrollTop: 1300, clientHeight: 700 })
    const { result } = setup(node)
    act(() => result.current.release())
    node.scrollTop = 100
    act(() => result.current.onScroll())
    act(() => result.current.follow()) // genuinely new content while reading further up
    expect(result.current.away).toBe(true)
  })

  it('honours reduced motion for the jump', () => {
    const original = window.matchMedia
    window.matchMedia = ((q: string) => ({ matches: q.includes('reduce'), addEventListener() {}, removeEventListener() {} })) as never
    try {
      const node = fakeScroller({ scrollHeight: 2000, scrollTop: 100, clientHeight: 700 })
      const { result } = setup(node)
      act(() => result.current.jumpToLatest())
      expect(node.scrollTo).toHaveBeenLastCalledWith({ top: 2000, behavior: 'auto' })
    } finally {
      window.matchMedia = original
    }
  })
})
