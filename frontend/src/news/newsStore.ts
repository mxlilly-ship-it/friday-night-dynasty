import type { NewsArticle, TickerItem } from './newsTypes'
import { articleVisibleInFeed, tickerVisibleInFeed } from './newsVisibility'

const MAX_ARTICLES = 100
const MAX_TICKER = 180

type Listener = () => void

let seq = 0
function nextId(prefix: string) {
  seq += 1
  return `${prefix}-${Date.now()}-${seq}`
}

export class NewsCenter {
  articles: NewsArticle[] = []
  tickerItems: TickerItem[] = []
  private listeners = new Set<Listener>()
  private dedupeKeys = new Set<string>()

  subscribe(fn: Listener): () => void {
    this.listeners.add(fn)
    return (): void => {
      this.listeners.delete(fn)
    }
  }

  private emit() {
    for (const fn of this.listeners) fn()
  }

  clear() {
    this.articles = []
    this.tickerItems = []
    this.dedupeKeys.clear()
    this.emit()
  }

  /** Drop headlines that no longer match the current week / phase (call whenever saveState updates). */
  pruneForState(state: any) {
    if (!state) return
    const nextArticles = this.articles.filter((a) => articleVisibleInFeed(a, state))
    const nextTicker = this.tickerItems.filter((t) => tickerVisibleInFeed(t, state))
    if (nextArticles.length === this.articles.length && nextTicker.length === this.tickerItems.length) return
    this.articles = nextArticles
    this.tickerItems = nextTicker
    this.emit()
  }

  /** Returns false if this key was already consumed (avoids duplicate ingests). */
  tryConsumeKey(key: string): boolean {
    if (this.dedupeKeys.has(key)) return false
    this.dedupeKeys.add(key)
    if (this.dedupeKeys.size > 800) {
      const drop = [...this.dedupeKeys].slice(0, 400)
      for (const k of drop) this.dedupeKeys.delete(k)
    }
    return true
  }

  /** Every article adds a matching ticker line (synced coverage). */
  addArticleWithTicker(article: NewsArticle, ticker: Omit<TickerItem, 'id' | 'timestamp'> & { id?: string; timestamp?: number }) {
    const id = ticker.id ?? article.id
    const item: TickerItem = {
      id,
      text: clipTicker(ticker.text || article.tickerText),
      type: ticker.type,
      priority: ticker.priority,
      timestamp: ticker.timestamp ?? article.timestamp,
      relatedArticleId: ticker.relatedArticleId ?? article.id,
      newsWeek: ticker.newsWeek ?? article.newsWeek,
      seasonPhase: ticker.seasonPhase ?? article.seasonPhase,
      seasonYear: ticker.seasonYear ?? article.seasonYear,
    }
    this.articles.unshift(article)
    if (this.articles.length > MAX_ARTICLES) this.articles.length = MAX_ARTICLES
    this.tickerItems.unshift(item)
    if (this.tickerItems.length > MAX_TICKER) this.tickerItems.length = MAX_TICKER
    this.emit()
  }

  /** Ticker-only line (no full article). */
  pushTicker(ticker: Omit<TickerItem, 'id' | 'timestamp'> & { id?: string; timestamp?: number }) {
    const item: TickerItem = {
      id: ticker.id ?? nextId('t'),
      text: clipTicker(ticker.text),
      type: ticker.type,
      priority: ticker.priority,
      timestamp: ticker.timestamp ?? Date.now(),
      relatedArticleId: ticker.relatedArticleId,
      newsWeek: ticker.newsWeek,
      seasonPhase: ticker.seasonPhase,
      seasonYear: ticker.seasonYear,
    }
    this.tickerItems.unshift(item)
    if (this.tickerItems.length > MAX_TICKER) this.tickerItems.length = MAX_TICKER
    this.emit()
  }
}

export function clipTicker(s: string, max = 80): string {
  const t = s.replace(/\s+/g, ' ').trim()
  if (t.length <= max) return t
  return `${t.slice(0, max - 1)}…`
}

const stores = new Map<string, NewsCenter>()

export function getNewsCenter(saveId: string): NewsCenter {
  let s = stores.get(saveId)
  if (!s) {
    s = new NewsCenter()
    stores.set(saveId, s)
  }
  return s
}

export function resetNewsCenter(saveId: string) {
  stores.delete(saveId)
}

export { nextId }
