import { attachMarkers, splitSentences, tokens } from './evidence'

describe('tokens', () => {
  it('normalises Indian digit grouping and drops stop words', () => {
    expect(tokens('The fee is waived on 1,50,000')).toEqual(new Set(['fee', 'waived', '150000']))
  })
})

describe('splitSentences', () => {
  it('splits on sentence ends and newlines without breaking decimals', () => {
    expect(splitSentences('The markup is 3.5%. It applies abroad.\nThanks')).toEqual([
      'The markup is 3.5%.',
      'It applies abroad.',
      'Thanks',
    ])
  })
})

describe('attachMarkers', () => {
  it('puts each claim number on its best-matching sentence, once', () => {
    const segs = attachMarkers(
      "I've checked. Your card-year spend is 1,62,000. The Signature fee is waived at 4,00,000.",
      ['Card-year spend is 1,62,000', 'Signature annual fee waived on spend of 4,00,000'],
    )
    expect(segs.map((s) => s.markers)).toEqual([[], [1], [2]])
  })

  it('leaves an unrelated claim unattached instead of guessing', () => {
    const segs = attachMarkers('The markup is 3.5%.', ['Cash advance costs 2.5%, minimum 500'])
    expect(segs.every((s) => s.markers.length === 0)).toBe(true)
  })

  it('keeps paragraph breaks in the gap after a sentence', () => {
    const segs = attachMarkers('First point.\n\nRequest SR-1 raised.', [])
    expect(segs.map((s) => s.text)).toEqual(['First point.', 'Request SR-1 raised.'])
    expect(segs[0]!.gap).toBe('\n\n')
  })

  it('never loses a character: text and gaps rebuild the message exactly', () => {
    const message = '  Intro line:\n\n- **One:** first item. Second sentence.\n- Two\n\nOutro?  \n'
    const segs = attachMarkers(message, ['first item'])
    expect(segs.map((s) => s.text + s.gap).join('')).toBe(message)
  })

  describe('lists', () => {
    const message =
      'Here is how it works:\n\n- **Eligibility checks:** The card must be open for six statement cycles.\n- **Income assessment:** A credit officer must assess your income first.\n- **Declines:** We give a plain-language reason within 7 days.\n\nI can submit a request.'

    it('treats every bullet as its own segment', () => {
      const texts = attachMarkers(message, []).map((s) => s.text)
      expect(texts).toEqual([
        'Here is how it works:',
        '- **Eligibility checks:** The card must be open for six statement cycles.',
        '- **Income assessment:** A credit officer must assess your income first.',
        '- **Declines:** We give a plain-language reason within 7 days.',
        'I can submit a request.',
      ])
    })

    it('lands each marker on the bullet that matches, not the one before or after', () => {
      const segs = attachMarkers(message, [
        'A credit officer must assess income before any decision',
        'Plain-language reason within 7 days when declined',
      ])
      expect(segs.map((s) => s.markers)).toEqual([[], [], [1], [2], []])
    })
  })
})
