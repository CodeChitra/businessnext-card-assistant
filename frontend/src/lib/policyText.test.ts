import { bestUnit, parsePolicy } from './policyText'

const FEES = `| Charge | Amount |
| --- | --- |
| Annual card fee, Classic | Waived on spend of 1,50,000 in the card year |
| Annual card fee, Signature | Waived on spend of 4,00,000 in the card year |

Fees reversed as a goodwill gesture require a supervisor approval and are capped at
two reversals per customer per financial year.`

const DECLINES = `A request must be declined, without discretion, where any of the following apply:
- The debt-burden ratio after the increase would exceed 55%.
- An unresolved dispute exists on the account.
- The customer has had a limit increase approved in the preceding
  6 months.`

describe('parsePolicy', () => {
  it('turns markdown tables into header and rows, dropping the separator', () => {
    const [table] = parsePolicy(FEES)
    expect(table).toEqual({
      kind: 'table',
      header: ['Charge', 'Amount'],
      rows: [
        ['Annual card fee, Classic', 'Waived on spend of 1,50,000 in the card year'],
        ['Annual card fee, Signature', 'Waived on spend of 4,00,000 in the card year'],
      ],
    })
  })

  it('reflows hard-wrapped paragraphs and list items', () => {
    expect(parsePolicy(FEES)[1]).toEqual({
      kind: 'para',
      sentences: [
        'Fees reversed as a goodwill gesture require a supervisor approval and are capped at two reversals per customer per financial year.',
      ],
    })
    const list = parsePolicy(DECLINES)[1]
    expect(list?.kind === 'list' && list.items[2]).toBe(
      'The customer has had a limit increase approved in the preceding 6 months.',
    )
  })
})

describe('bestUnit', () => {
  it('picks the supporting table row', () => {
    expect(bestUnit(parsePolicy(FEES), 'Signature annual fee waived at 4,00,000')).toEqual({ block: 0, unit: 1 })
  })

  it('picks the supporting list item', () => {
    expect(bestUnit(parsePolicy(DECLINES), 'An open dispute on the account blocks increases')).toEqual({
      block: 1,
      unit: 1,
    })
  })

  it('returns null when nothing is close', () => {
    expect(bestUnit(parsePolicy(FEES), 'travel insurance cover')).toBeNull()
  })
})
