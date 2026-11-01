import { parseSSE, readSSE } from './sse'

function streamOf(...chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      chunks.forEach((c) => controller.enqueue(enc.encode(c)))
      controller.close()
    },
  })
}

describe('parseSSE', () => {
  it('parses named JSON events and keeps an incomplete tail', () => {
    const { messages, rest } = parseSSE(
      'event: progress\ndata: {"step":"retrieve"}\n\nevent: final\ndata: {"behav',
    )
    expect(messages).toEqual([{ event: 'progress', data: { step: 'retrieve' } }])
    expect(rest).toBe('event: final\ndata: {"behav')
  })

  it('handles CRLF, comments and multi-line data', () => {
    const { messages } = parseSSE(': keep-alive\r\n\r\ndata: line1\r\ndata: line2\r\n\r\n')
    expect(messages).toEqual([{ event: 'message', data: 'line1\nline2' }])
  })
})

describe('readSSE', () => {
  it('reassembles events split across network chunks', async () => {
    const body = streamOf('event: progress\nda', 'ta: {"step":"a"}\n\nevent: fi', 'nal\ndata: {"ok":true}\n\n')
    const out = []
    for await (const m of readSSE(body)) out.push(m)
    expect(out).toEqual([
      { event: 'progress', data: { step: 'a' } },
      { event: 'final', data: { ok: true } },
    ])
  })

  it('flushes a final event that lacks the trailing blank line', async () => {
    const out = []
    for await (const m of readSSE(streamOf('event: final\ndata: {"x":1}'))) out.push(m)
    expect(out).toEqual([{ event: 'final', data: { x: 1 } }])
  })
})
