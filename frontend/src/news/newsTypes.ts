export type TickerItemType = 'score' | 'player' | 'upset' | 'injury' | 'recruiting' | 'ranking'

export type TickerPriority = 'low' | 'normal' | 'high'

export type TickerItem = {
  id: string
  text: string
  type: TickerItemType
  priority: TickerPriority
  timestamp: number
  relatedArticleId?: string
  /** 1-based schedule week for regular-season stories; 0 / omit = phase-wide (playoffs, offseason, etc.) */
  newsWeek?: number
  seasonPhase?: string
  seasonYear?: number
}

export type NewsArticleType = 'recap' | 'ranking' | 'player' | 'injury' | 'recruiting' | 'feature'

export type NewsArticle = {
  id: string
  title: string
  summary: string
  content: string
  type: NewsArticleType
  teams: string[]
  players: string[]
  timestamp: number
  /** Higher sorts first in feed */
  priority: number
  /** Short line shared with ticker (before clip) */
  tickerText: string
  breaking?: boolean
  /** 1-based schedule week (regular season); 0 / omit = not week-scoped */
  newsWeek?: number
  seasonPhase?: string
  seasonYear?: number
}
