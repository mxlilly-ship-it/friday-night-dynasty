import './NewsTicker.css'
import type { TickerItem } from './newsTypes'
import { useNews } from './NewsContext'
import { dedupeTickerItemsByText, tickerVisibleInFeed } from './newsVisibility'

const DEFAULT_LINE = 'Friday Night Dynasty — Sim a week or play a game for live headlines'

export default function NewsTicker() {
  const { center, saveState, openArticle } = useNews()
  const expanded = dedupeTickerItemsByText(center.tickerItems.filter((t: TickerItem) => tickerVisibleInFeed(t, saveState)))

  if (expanded.length === 0) {
    return (
      <div className="fnd-news-ticker-viewport" role="status" aria-live="polite">
        <div className="fnd-news-ticker-label">News</div>
        <div className="fnd-news-ticker-marquee">
          <div className="fnd-news-ticker-track" style={{ animation: 'none', transform: 'none' }}>
            <div className="fnd-news-ticker-segment">{DEFAULT_LINE}</div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="fnd-news-ticker-viewport" role="status" aria-live="polite">
      <div className="fnd-news-ticker-label">News</div>
      <div className="fnd-news-ticker-marquee">
        <div className="fnd-news-ticker-track">
          <div className="fnd-news-ticker-segment">
            {expanded.map((it, idx) => (
              <span key={`a-${it.id}-${idx}`}>
                {idx > 0 ? <span className="fnd-news-ticker-sep">•</span> : null}
                <span
                  className="fnd-news-ticker-item"
                  role="button"
                  tabIndex={0}
                  onClick={() => it.relatedArticleId && openArticle(it.relatedArticleId)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      if (it.relatedArticleId) openArticle(it.relatedArticleId)
                    }
                  }}
                >
                  {it.text}
                </span>
              </span>
            ))}
          </div>
          <div className="fnd-news-ticker-segment" aria-hidden>
            {expanded.map((it, idx) => (
              <span key={`b-${it.id}-${idx}`}>
                {idx > 0 ? <span className="fnd-news-ticker-sep">•</span> : null}
                <span className="fnd-news-ticker-item">{it.text}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
