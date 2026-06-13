import type { NewsArticle, TickerItem } from './newsTypes'

/** Regular-season week index (1-based) on the schedule row; 0 = not tied to a single league week. */
function parsePhase(state: any): string {
  return String(state?.season_phase ?? '').toLowerCase()
}

/** Firehose: show all regular-season headlines through the current week (plus a small forward buffer). */
function regularSeasonWeekVisible(storyWeek: number, currentWeek: number): boolean {
  const cw = Math.max(1, currentWeek)
  return storyWeek >= 1 && storyWeek <= cw + 1
}

/** True if this headline should appear for the current save snapshot. */
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

  if (!isRegularWeekStory) {
    if (phase === 'regular') return false
    return ap === phase || !ap
  }

  if (phase === 'regular') {
    return regularSeasonWeekVisible(w, cw)
  }

  // Playoffs / preseason / offseason: keep the full regular-season backlog visible.
  return w >= 1 && w <= Math.max(cw + 2, 12)
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
    if (phase === 'regular') return false
    return ip === phase || !ip
  }

  if (phase === 'regular') {
    return regularSeasonWeekVisible(w, cw)
  }

  return w >= 1 && w <= Math.max(cw + 2, 12)
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
