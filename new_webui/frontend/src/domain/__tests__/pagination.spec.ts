import { describe, expect, it } from 'vitest'
import {
  clampPage,
  isPageSize,
  pageAfterResize,
  pageCount,
  pageRange,
  pageSlice,
} from '../pagination'

const items = Array.from({ length: 23 }, (_, i) => i + 1)

describe('pageCount', () => {
  it('treats an empty list as one empty page', () => {
    // "Page 1 of 0" is nonsense to read and gives the controls nothing to
    // disable against.
    expect(pageCount(0, 10)).toBe(1)
  })

  it('rounds partial pages up', () => {
    expect(pageCount(23, 10)).toBe(3)
    expect(pageCount(20, 10)).toBe(2)
    expect(pageCount(1, 10)).toBe(1)
  })

  it('survives a nonsense page size', () => {
    expect(pageCount(23, 0)).toBe(1)
    expect(pageCount(23, -5)).toBe(1)
  })
})

describe('clampPage', () => {
  it('pulls a page past the end back to the last one', () => {
    // The deleted-last-row case: 11 items on page 2, delete one, page 2 is gone.
    expect(clampPage(2, 10, 10)).toBe(1)
    expect(clampPage(99, 23, 10)).toBe(3)
  })

  it('pulls a page below one back up', () => {
    expect(clampPage(0, 23, 10)).toBe(1)
    expect(clampPage(-4, 23, 10)).toBe(1)
  })

  it('rejects non-finite input rather than propagating NaN', () => {
    expect(clampPage(Number.NaN, 23, 10)).toBe(1)
    expect(clampPage(Number.POSITIVE_INFINITY, 23, 10)).toBe(1)
  })
})

describe('pageSlice', () => {
  it('returns the right window', () => {
    expect(pageSlice(items, 1, 10)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    expect(pageSlice(items, 3, 10)).toEqual([21, 22, 23])
  })

  it('clamps rather than returning an empty window past the end', () => {
    expect(pageSlice(items, 9, 10)).toEqual([21, 22, 23])
  })

  it('returns nothing for an empty list without throwing', () => {
    expect(pageSlice([], 1, 10)).toEqual([])
  })
})

describe('pageRange', () => {
  it('reads as 1-based, inclusive', () => {
    expect(pageRange(1, 10, 23)).toEqual({ from: 1, to: 10, total: 23 })
    expect(pageRange(3, 10, 23)).toEqual({ from: 21, to: 23, total: 23 })
  })

  it('reports zeroes for an empty list, not "1 to 0"', () => {
    expect(pageRange(1, 10, 0)).toEqual({ from: 0, to: 0, total: 0 })
  })

  it('clamps an out-of-range page before computing', () => {
    expect(pageRange(99, 10, 23)).toEqual({ from: 21, to: 23, total: 23 })
  })
})

describe('pageAfterResize', () => {
  it('keeps the first visible row visible when the size grows', () => {
    // Page 3 at size 10 starts at item 21; at size 50 that is still page 1.
    expect(pageAfterResize(3, 10, 50, 23)).toBe(1)
  })

  it('keeps the first visible row visible when the size shrinks', () => {
    // Page 2 at size 25 starts at item 26; at size 10 that is page 3.
    expect(pageAfterResize(2, 25, 10, 60)).toBe(3)
  })

  it('stays on page 1 when it was already there', () => {
    expect(pageAfterResize(1, 10, 25, 23)).toBe(1)
  })
})

describe('isPageSize', () => {
  it('accepts only the offered sizes', () => {
    expect(isPageSize(10)).toBe(true)
    expect(isPageSize(25)).toBe(true)
    expect(isPageSize(11)).toBe(false)
  })
})
