import { Children, Fragment, type ReactNode } from 'react'
import Markdown, { type Components } from 'react-markdown'

import { splitMarkers } from '../lib/citationMarkers'

// A bank answer renders prose structure only. No links, images, headings, tables or HTML:
// whatever the model writes, the customer can't be sent anywhere or shown remote content.
const ALLOWED = ['p', 'ul', 'ol', 'li', 'strong', 'em', 'br', 'code', 'blockquote']

interface Props {
  source: string
  selectedClaim: number | null // 1-based
  onSelectClaim: (n: number) => void
  /** False while the answer is still being revealed: markers show but aren't buttons yet. */
  interactive: boolean
}

const MARKER =
  'figures relative top-[-0.45em] ml-0.5 inline-flex h-[1.15rem] min-w-[1.15rem] items-center justify-center rounded-full px-1 text-[0.7rem] font-semibold leading-none transition-colors duration-150'

export function AnswerMarkdown({ source, selectedClaim, onSelectClaim, interactive }: Props) {
  const withMarkers = (children: ReactNode): ReactNode =>
    Children.map(children, (child) =>
      typeof child === 'string'
        ? splitMarkers(child).map((part, i) =>
            typeof part === 'string' ? (
              <Fragment key={i}>{part}</Fragment>
            ) : (
              part.map((n) =>
                interactive ? (
                  <button
                    key={`${i}-${n}`}
                    type="button"
                    onClick={() => onSelectClaim(n)}
                    aria-label={`Show source ${n}`}
                    aria-pressed={selectedClaim === n}
                    className={`${MARKER} ${
                      selectedClaim === n
                        ? 'bg-teal text-on-accent'
                        : 'bg-teal-wash text-teal hover:bg-teal hover:text-on-accent'
                    }`}
                  >
                    {n}
                  </button>
                ) : (
                  <span key={`${i}-${n}`} className={`${MARKER} bg-teal-wash text-teal`}>
                    {n}
                  </span>
                ),
              )
            ),
          )
        : child,
    )

  const components: Components = {
    p: ({ children }) => <p className="whitespace-pre-line">{withMarkers(children)}</p>,
    ul: ({ children }) => (
      <ul className="list-disc space-y-2 pl-6 marker:text-muted">{children}</ul>
    ),
    ol: ({ children }) => (
      <ol className="list-decimal space-y-2 pl-6 marker:text-muted">{children}</ol>
    ),
    li: ({ children }) => <li className="pl-1">{withMarkers(children)}</li>,
    strong: ({ children }) => <strong className="font-semibold">{withMarkers(children)}</strong>,
    em: ({ children }) => <em>{withMarkers(children)}</em>,
    code: ({ children }) => (
      <code className="figures rounded-control bg-sunk px-1 py-0.5 text-[0.9em]">{children}</code>
    ),
    blockquote: ({ children }) => (
      <blockquote className="border-l-2 border-line pl-4 text-muted">{children}</blockquote>
    ),
  }

  return (
    <div className="max-w-[68ch] space-y-3 text-[1.0625rem] leading-[1.7]">
      <Markdown allowedElements={ALLOWED} unwrapDisallowed components={components}>
        {source}
      </Markdown>
    </div>
  )
}
