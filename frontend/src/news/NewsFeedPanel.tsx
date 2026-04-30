import { useState } from 'react'
import './NewsFeedPanel.css'
import { useNews } from './NewsContext'
import type { NewsArticle } from './newsTypes'
import { articleVisibleInFeed } from './newsVisibility'

type Props = {
  limit?: number
  compact?: boolean
  /** When false, do not sync expand state from ticker selection */
  syncSelection?: boolean
}

export default function NewsFeedPanel({ limit = 8, compact = false, syncSelection = true }: Props) {
  const { center, saveState, selectedArticleId, openArticle, closeArticle } = useNews()
  const [localOpen, setLocalOpen] = useState<string | null>(null)

  const rows = center.articles.filter((a: NewsArticle) => articleVisibleInFeed(a, saveState)).slice(0, limit)

  const effectiveOpen = syncSelection && selectedArticleId ? selectedArticleId : localOpen

  return (
    <div className={`fnd-news-feed ${compact ? 'fnd-news-feed--compact' : ''}`}>
      {rows.length === 0 ? (
        <div className="fnd-news-feed-empty">No headlines yet — play or sim to fill the wire.</div>
      ) : (
        rows.map((a: NewsArticle) => {
          const expanded = effectiveOpen === a.id
          return (
            <article
              key={a.id}
              className={`fnd-news-card ${a.breaking ? 'fnd-news-card--breaking' : ''} ${selectedArticleId === a.id ? 'fnd-news-card--active' : ''}`}
            >
              <div className="fnd-news-card-meta">
                {a.breaking ? 'Breaking · ' : ''}
                {a.type}
                {' · '}
                {new Date(a.timestamp).toLocaleString()}
              </div>
              <h3 className="fnd-news-card-title">{a.title}</h3>
              <p className="fnd-news-card-summary">{a.summary}</p>
              <button
                type="button"
                className="fnd-news-card-toggle"
                onClick={() => {
                  if (expanded) {
                    setLocalOpen(null)
                    if (selectedArticleId === a.id) closeArticle()
                  } else {
                    setLocalOpen(a.id)
                    openArticle(a.id)
                  }
                }}
              >
                {expanded ? 'Collapse' : 'Read full story'}
              </button>
              {expanded ? <div className="fnd-news-card-body">{a.content}</div> : null}
            </article>
          )
        })
      )}
    </div>
  )
}
