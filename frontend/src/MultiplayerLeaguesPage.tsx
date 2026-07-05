import { useCallback, useEffect, useState } from 'react'
import './LeagueDashboardPage.css'
import type { DeletedLeagueListItem, LeagueListItem } from './multiplayer'
import {
  deleteAdminLeague,
  fetchDeletedLeagues,
  fetchMyLeagues,
  permanentDeleteAdminLeague,
  restoreAdminLeague,
} from './multiplayer'

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
  const [deletingId, setDeletingId] = useState('')
  const [restoringId, setRestoringId] = useState('')
  const [deletedLeagues, setDeletedLeagues] = useState<DeletedLeagueListItem[]>([])
  const [selectedArchivedId, setSelectedArchivedId] = useState('')
  const [permanentDeletingId, setPermanentDeletingId] = useState('')
  const [flash, setFlash] = useState('')

  const reload = useCallback(async () => {
    const data = await fetchMyLeagues(apiBase, headers)
    setLeagues(data.leagues)
    setIsPlatformOwner(data.is_platform_owner)
    setPlatformOwnerConfigured(Boolean(data.platform_owner_configured))
    setAccountEmail(data.account_email ?? '')
    if (data.is_platform_owner) {
      try {
        const archived = await fetchDeletedLeagues(apiBase, headers)
        setDeletedLeagues(archived)
        setSelectedArchivedId((prev) =>
          prev && archived.some((l) => l.league_id === prev) ? prev : archived[0]?.league_id ?? '',
        )
      } catch {
        setDeletedLeagues([])
        setSelectedArchivedId('')
      }
    } else {
      setDeletedLeagues([])
      setSelectedArchivedId('')
    }
  }, [apiBase, headers])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    void reload()
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load leagues')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [reload])

  async function onDeleteLeague(league: LeagueListItem) {
    const typed = window.prompt(
      `Archive league "${league.name}"?\n\nIt will be hidden from all players but can be restored from Archived leagues below.\n\nType the league name exactly to confirm:`,
    )
    if (typed === null) return
    if (typed.trim() !== league.name) {
      setError('League name did not match — nothing was deleted.')
      return
    }
    setDeletingId(league.league_id)
    setError('')
    setFlash('')
    try {
      const res = await deleteAdminLeague(apiBase, headers, league.league_id)
      await reload()
      setFlash(`Archived «${res.name}». You can restore it below.`)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to delete league')
    } finally {
      setDeletingId('')
    }
  }

  async function onRestoreLeague(league: DeletedLeagueListItem) {
    setRestoringId(league.league_id)
    setError('')
    setFlash('')
    try {
      const res = await restoreAdminLeague(apiBase, headers, league.league_id)
      await reload()
      setFlash(`Restored «${res.name}».`)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to restore league')
    } finally {
      setRestoringId('')
    }
  }

  async function onPermanentDeleteLeague(league: DeletedLeagueListItem) {
    const typed = window.prompt(
      `Permanently delete "${league.name}"?\n\nThis removes the league from the server and cannot be undone.\n\nType the league name exactly to confirm:`,
    )
    if (typed === null) return
    if (typed.trim() !== league.name) {
      setError('League name did not match — nothing was deleted.')
      return
    }
    setPermanentDeletingId(league.league_id)
    setError('')
    setFlash('')
    try {
      const res = await permanentDeleteAdminLeague(apiBase, headers, league.league_id)
      await reload()
      setFlash(`Permanently deleted «${res.name}».`)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to permanently delete league')
    } finally {
      setPermanentDeletingId('')
    }
  }

  const selectedArchived =
    deletedLeagues.find((l) => l.league_id === selectedArchivedId) ?? null

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
        {flash ? (
          <p style={{ margin: '0 0 12px', color: 'var(--green-status)', fontSize: '0.9rem' }}>{flash}</p>
        ) : null}

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
                teams, custom JSON upload, coach profile, and your school. Archive removes a league from play
                (type the name to confirm). Use the archived leagues menu below to restore or permanently delete.
              </p>
              <button type="button" className="ldash-action-btn ldash-action-btn--gold" onClick={onCreateLeague}>
                Create new league
              </button>

              <div
                style={{
                  marginTop: 20,
                  paddingTop: 16,
                  borderTop: '1px solid rgba(255,255,255,0.08)',
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: 8 }}>Archived leagues</div>
                <p style={{ margin: '0 0 10px', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                  Hidden from all players. Restore to bring back, or delete permanently to remove from the server.
                </p>
                {deletedLeagues.length === 0 ? (
                  <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                    No archived leagues.
                  </p>
                ) : (
                  <>
                    <select
                      className="ldash-action-btn"
                      style={{
                        width: '100%',
                        maxWidth: 420,
                        marginBottom: 12,
                        textAlign: 'left',
                      }}
                      value={selectedArchivedId}
                      onChange={(e) => setSelectedArchivedId(e.target.value)}
                    >
                      {deletedLeagues.map((league) => (
                        <option key={league.league_id} value={league.league_id}>
                          {league.name}
                        </option>
                      ))}
                    </select>
                    {selectedArchived ? (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                        <button
                          type="button"
                          className="ldash-action-btn ldash-action-btn--gold"
                          disabled={Boolean(restoringId) || Boolean(permanentDeletingId)}
                          onClick={() => void onRestoreLeague(selectedArchived)}
                        >
                          {restoringId === selectedArchived.league_id ? 'Restoring…' : 'Restore'}
                        </button>
                        <button
                          type="button"
                          className="ldash-back-btn"
                          style={{ color: 'var(--red-status)', borderColor: 'rgba(217, 100, 91, 0.45)' }}
                          disabled={Boolean(restoringId) || Boolean(permanentDeletingId)}
                          onClick={() => void onPermanentDeleteLeague(selectedArchived)}
                        >
                          {permanentDeletingId === selectedArchived.league_id
                            ? 'Deleting…'
                            : 'Delete permanently'}
                        </button>
                      </div>
                    ) : null}
                  </>
                )}
              </div>
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
                <div
                  key={league.league_id}
                  className="ldash-div-header"
                  style={{ padding: '14px 16px', alignItems: 'flex-start', display: 'flex', gap: 10 }}
                >
                  <button
                    type="button"
                    style={{
                      flex: 1,
                      textAlign: 'left',
                      background: 'transparent',
                      border: 0,
                      padding: 0,
                      color: 'inherit',
                      cursor: 'pointer',
                    }}
                    onClick={() => onOpenLeague(league)}
                  >
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
                  </button>
                  <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8 }}>
                    <span className="ldash-div-count">{league.status}</span>
                    {isPlatformOwner ? (
                      <button
                        type="button"
                        className="ldash-back-btn"
                        style={{ color: 'var(--red-status)', borderColor: 'rgba(217, 100, 91, 0.45)' }}
                        disabled={Boolean(deletingId)}
                        onClick={(e) => {
                          e.stopPropagation()
                          void onDeleteLeague(league)
                        }}
                      >
                        {deletingId === league.league_id ? 'Archiving…' : 'Archive'}
                      </button>
                    ) : null}
                  </span>
                </div>
              )
            })}
          </div>
        ) : null}
      </div>
    </div>
  )
}
