import { useEffect, useState } from 'react'
import './LeagueDashboardPage.css'
import type { LeagueListItem } from './multiplayer'
import { fetchMyLeagues } from './multiplayer'

type MultiplayerLeaguesPageProps = {
  apiBase: string
  headers: Record<string, string>
  onBack: () => void
  onOpenLeague: (league: LeagueListItem) => void
  onCreateLeague?: () => void
}

function badgeClass(badge: string): string {
  const b = badge.toLowerCase()
  if (b === 'submitted') return 'ldash-list-badge ldash-list-badge--ok'
  if (b === 'your turn') return 'ldash-list-badge ldash-list-badge--turn'
  if (b === 'commissioner' || b === 'admin') return 'ldash-list-badge ldash-list-badge--role'
  if (b === 'setup needed' || b === 'awaiting team') return 'ldash-list-badge ldash-list-badge--wait'
  return 'ldash-list-badge'
}

export default function MultiplayerLeaguesPage({
  apiBase,
  headers,
  onBack,
  onOpenLeague,
  onCreateLeague,
}: MultiplayerLeaguesPageProps) {
  const [leagues, setLeagues] = useState<LeagueListItem[]>([])
  const [isPlatformOwner, setIsPlatformOwner] = useState(false)
  const [platformOwnerConfigured, setPlatformOwnerConfigured] = useState(false)
  const [accountEmail, setAccountEmail] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    void fetchMyLeagues(apiBase, headers)
      .then((data) => {
        if (!cancelled) {
          setLeagues(data.leagues)
          setIsPlatformOwner(data.is_platform_owner)
          setPlatformOwnerConfigured(Boolean(data.platform_owner_configured))
          setAccountEmail(data.account_email ?? '')
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load leagues')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [apiBase, headers])

  return (
    <div className="ldash-root">
      <div className="ldash-topbar">
        <div className="ldash-league-identity">
          <div className="ldash-league-crest">MP</div>
          <div>
            <div className="ldash-league-name">Multiplayer leagues</div>
            <div className="ldash-league-sub">Online dynasties on the server</div>
            {isPlatformOwner ? <span className="ldash-commish-badge">Platform admin</span> : null}
          </div>
        </div>
        <button type="button" className="ldash-back-btn" onClick={onBack}>
          ← Title
        </button>
      </div>

      <div style={{ padding: '24px 32px', maxWidth: 720 }}>
        {loading ? <p className="ldash-loading">Loading leagues…</p> : null}
        {error ? <p className="ldash-error">{error}</p> : null}

        {isPlatformOwner && onCreateLeague ? (
          <div className="ldash-panel" style={{ marginBottom: 16 }}>
            <div className="ldash-panel-header">
              <span className="ldash-panel-title">
                Admin <span className="accent">Dashboard</span>
              </span>
            </div>
            <div className="ldash-panel-body">
              <p style={{ margin: '0 0 12px', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                Create a new multiplayer league using the same setup flow as a single-player dynasty — default
                teams, custom JSON upload, coach profile, and your school.
              </p>
              <button type="button" className="ldash-action-btn ldash-action-btn--gold" onClick={onCreateLeague}>
                Create new league
              </button>
            </div>
          </div>
        ) : null}

        {!loading && !isPlatformOwner ? (
          <div className="ldash-panel" style={{ marginBottom: 16 }}>
            <div className="ldash-panel-body">
              <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                {!platformOwnerConfigured ? (
                  <>
                    Platform admin is not enabled on this server. In Railway Variables, set{' '}
                    <code style={{ color: 'var(--gold-bright)' }}>FND_PLATFORM_OWNER_EMAILS=mxlilly@gmail.com</code>{' '}
                    and redeploy. Signed in as{' '}
                    <strong style={{ color: 'var(--text-primary)' }}>{accountEmail || 'unknown'}</strong>.
                  </>
                ) : (
                  <>
                    Signed in as <strong style={{ color: 'var(--text-primary)' }}>{accountEmail || 'unknown'}</strong>.
                    That account is not in <code style={{ color: 'var(--gold-bright)' }}>FND_PLATFORM_OWNER_EMAILS</code>.
                  </>
                )}
              </p>
            </div>
          </div>
        ) : null}

        {!loading && !error && leagues.length === 0 ? (
          <div className="ldash-panel">
            <div className="ldash-panel-body">
              <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
                {isPlatformOwner
                  ? 'No leagues yet — use Create new league above to get started.'
                  : 'No multiplayer leagues yet. When a commissioner invites your email, your league will appear here.'}
              </p>
            </div>
          </div>
        ) : null}

        {!loading && leagues.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {leagues.map((league) => {
              const badges =
                league.badges && league.badges.length
                  ? league.badges
                  : [
                      ...(league.is_commissioner ? ['Commissioner'] : []),
                      ...(league.is_platform_owner_view && !league.can_run_league ? ['Admin'] : []),
                      ...(league.submitted ? ['Submitted'] : []),
                      ...(league.your_turn ? ['Your turn'] : []),
                    ]
              return (
                <button
                  key={league.league_id}
                  type="button"
                  className="ldash-div-header"
                  style={{ padding: '14px 16px', alignItems: 'flex-start' }}
                  onClick={() => onOpenLeague(league)}
                >
                  <span style={{ textAlign: 'left', flex: 1 }}>
                    <span className="ldash-div-name" style={{ fontSize: 15 }}>
                      {league.name}
                    </span>
                    <span className="ldash-your-status-sub" style={{ display: 'block', marginTop: 4 }}>
                      {league.week_label ? `${league.week_label} · ` : ''}
                      {league.teams.length > 0
                        ? league.teams.map((t) => t.team_name).filter(Boolean).join(', ')
                        : 'League overview'}
                    </span>
                    {badges.length ? (
                      <span className="ldash-list-badges">
                        {badges.map((b) => (
                          <span key={b} className={badgeClass(b)}>
                            {b}
                          </span>
                        ))}
                      </span>
                    ) : null}
                  </span>
                  <span className="ldash-div-count">{league.status}</span>
                </button>
              )
            })}
          </div>
        ) : null}
      </div>
    </div>
  )
}
