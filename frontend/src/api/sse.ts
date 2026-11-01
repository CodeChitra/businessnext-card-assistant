// Minimal Server-Sent Events parser for a fetch() body.
// EventSource only supports GET; the chat stream is a POST, so we parse the wire format.

export interface SSEMessage {
  event: string
  data: unknown
}

/** Parse complete SSE blocks from `buffer`; returns parsed messages and the unparsed tail. */
export function parseSSE(buffer: string): { messages: SSEMessage[]; rest: string } {
  const normalised = buffer.replace(/\r\n/g, '\n')
  const blocks = normalised.split('\n\n')
  const rest = blocks.pop() ?? ''
  const messages: SSEMessage[] = []
  for (const block of blocks) {
    let event = 'message'
    const dataLines: string[] = []
    for (const line of block.split('\n')) {
      if (line.startsWith(':')) continue // comment / keep-alive
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''))
    }
    if (dataLines.length === 0) continue
    const raw = dataLines.join('\n')
    let data: unknown = raw
    try {
      data = JSON.parse(raw)
    } catch {
      // non-JSON payloads are passed through as text
    }
    messages.push({ event, data })
  }
  return { messages, rest }
}

export async function* readSSE(body: ReadableStream<Uint8Array>): AsyncGenerator<SSEMessage> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const { messages, rest } = parseSSE(buffer)
      buffer = rest
      yield* messages
    }
    const { messages } = parseSSE(buffer + '\n\n')
    yield* messages
  } finally {
    reader.releaseLock()
  }
}
