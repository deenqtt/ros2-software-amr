/**
 * Pagination arithmetic.
 *
 * Kept as plain functions so the off-by-one cases — an empty list, a deleted
 * last row, a page size change — are testable without mounting a table.
 */

export const PAGE_SIZES = [10, 25, 50] as const
export type PageSize = (typeof PAGE_SIZES)[number]

export interface PageRange {
  /** 1-based index of the first visible item; 0 when there is nothing. */
  from: number
  /** 1-based index of the last visible item; 0 when there is nothing. */
  to: number
  total: number
}

/**
 * Never returns 0. An empty list is one empty page, not zero pages — that way
 * "page 1 of 1" stays true and the controls have something to disable against.
 */
export function pageCount(total: number, pageSize: number): number {
  if (pageSize <= 0) return 1
  return Math.max(1, Math.ceil(Math.max(0, total) / pageSize))
}

/**
 * Pull a page back into range.
 *
 * The case that matters: someone deletes the only row on the last page. The
 * page index is now past the end, and without clamping the table renders empty
 * while insisting there is data.
 */
export function clampPage(page: number, total: number, pageSize: number): number {
  const last = pageCount(total, pageSize)
  if (!Number.isFinite(page)) return 1
  return Math.min(Math.max(1, Math.trunc(page)), last)
}

export function pageSlice<T>(items: readonly T[], page: number, pageSize: number): T[] {
  const safePage = clampPage(page, items.length, pageSize)
  const start = (safePage - 1) * pageSize
  return items.slice(start, start + pageSize)
}

export function pageRange(page: number, pageSize: number, total: number): PageRange {
  if (total <= 0) return { from: 0, to: 0, total: 0 }
  const safePage = clampPage(page, total, pageSize)
  const from = (safePage - 1) * pageSize + 1
  return { from, to: Math.min(from + pageSize - 1, total), total }
}

/**
 * Keep the first visible item visible when the page size changes.
 *
 * Without this, switching 10 -> 50 on page 3 lands on page 3 of a 50-row
 * layout, which is somewhere the operator was not looking.
 */
export function pageAfterResize(page: number, oldSize: number, newSize: number, total: number): number {
  if (oldSize <= 0 || newSize <= 0) return 1
  const firstIndex = (clampPage(page, total, oldSize) - 1) * oldSize
  return clampPage(Math.floor(firstIndex / newSize) + 1, total, newSize)
}

export function isPageSize(value: number): value is PageSize {
  return (PAGE_SIZES as readonly number[]).includes(value)
}
