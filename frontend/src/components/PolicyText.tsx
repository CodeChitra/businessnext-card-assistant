import { type Block, type UnitRef } from '../lib/policyText'

/** Policy text set as a document (serif), with the supporting unit highlighted. */
export function PolicyText({ blocks, highlight }: { blocks: Block[]; highlight: UnitRef | null }) {
  const isHit = (b: number, u: number) => highlight?.block === b && highlight.unit === u
  return (
    <div className="space-y-3 font-serif text-[0.95rem] leading-[1.65]">
      {blocks.map((block, b) => {
        if (block.kind === 'table') {
          return (
            <table key={b} className="figures w-full border-collapse text-left text-[0.9rem] leading-snug">
              <thead>
                <tr className="border-b border-line">
                  {block.header.map((h) => (
                    <th key={h} className="py-1.5 pr-3 font-sans text-xs font-semibold text-muted">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {block.rows.map((row, r) => (
                  <tr key={r} className="border-b border-line last:border-0">
                    {row.map((cell, c) => (
                      <td key={c} className="py-1.5 pr-3 align-top">
                        {isHit(b, r) ? <mark className="evidence-mark">{cell}</mark> : cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )
        }
        if (block.kind === 'list') {
          return (
            <ul key={b} className="list-disc space-y-1 pl-5 marker:text-muted">
              {block.items.map((item, u) => (
                <li key={u}>{isHit(b, u) ? <mark className="evidence-mark">{item}</mark> : item}</li>
              ))}
            </ul>
          )
        }
        return (
          <p key={b}>
            {block.sentences.map((s, u) => (
              <span key={u}>
                {isHit(b, u) ? <mark className="evidence-mark">{s}</mark> : s}{' '}
              </span>
            ))}
          </p>
        )
      })}
    </div>
  )
}
