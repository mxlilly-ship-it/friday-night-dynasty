import type { NewsArticle, TickerItem } from './newsTypes'

/** Regular-season week index (1-based) on the schedule row; 0 = not tied to a single league week. */
function parsePhase(state: any): string {
  return String(state?.season_phase ?? '').toLowerCase()
}

/** True if this headline should appear for the current save snapshot (week-to-week regular season). */
export function articleVisibleInFeed(article: NewsArticle, state: any): boolean {
  if (!state) return false
  const phase = parsePhase(state)
  const y = Number(state?.current_year ?? 0)
  if (article.seasonYear != null && article.seasonYear > 0 && y > 0 && article.seasonYear !== y) return false

  const w = article.newsWeek
  const ap = article.seasonPhase

  if (w == null || w === 0) {
    if (!ap) {
      if (phase === 'regular') return false
      return true
    }
    return ap === phase
  }

  const cw = Math.max(1, Number(state?.current_week ?? 1))
  const isRegularWeekStory = (ap ?? 'regular') === 'regular'

  // Non–regular-season tagged rows (shouldn't happen often)
  if (!isRegularWeekStory) {
    if (phase !== 'regular') return false
    return w >= cw - 1 && w <= cw
  }

  // Regular-season scores: tight window while still in the regular season
  if (phase === 'regular') {
    return w >= cw - 1 && w <= cw
  }

  // Playoffs / preseason / offseason / done: keep regular-season lines so the wire
  // doesn't go blank (current_week may sit past the last schedule week).
  return w >= 1 && w <= cw + 2
}

export function tickerVisibleInFeed(item: TickerItem, state: any): boolean {
  if (!state) return false
  const phase = parsePhase(state)
  const y = Number(state?.current_year ?? 0)
  if (item.seasonYear != null && item.seasonYear > 0 && y > 0 && item.seasonYear !== y) return false

  const w = item.newsWeek
  const ip = item.seasonPhase

  if (w == null || w === 0) {
    if (!ip) {
      if (phase === 'regular') return false
      return true
    }
    return ip === phase
  }

  const cw = Math.max(1, Number(state?.current_week ?? 1))
  const isRegularWeekStory = (ip ?? 'regular') === 'regular'

  if (!isRegularWeekStory) {
    if (phase !== 'regular') return false
    return w >= cw - 1 && w <= cw
  }

  if (phase === 'regular') {
    return w >= cw - 1 && w <= cw
  }

  return w >= 1 && w <= cw + 2
}

export function dedupeTickerItemsByText(items: TickerItem[]): TickerItem[] {
  const seen = new Set<string>()
  const out: TickerItem[] = []
  for (const it of items) {
    const k = it.text.trim().toLowerCase()
    if (seen.has(k)) continue
    seen.add(k)
    out.push(it)
  }
  return out
}
