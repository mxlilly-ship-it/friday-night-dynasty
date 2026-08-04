import { useEffect, useMemo, useRef, useState } from 'react'
import './LeagueDashboardPage.css'
import type { LeagueChatMessage, LeagueDashboardData } from './multiplayer'
import { downloadLeagueLogoPack, fetchLeagueLogoPackStatus } from './multiplayer'

type LeagueDashboardPageProps = {
  apiBase: string
  headers: Record<string, string>
  data: LeagueDashboardData
  onBack: () => void
  onOpenCoachDashboard?: () => void
  coachDashBusy?: boolean
  /** Submit/unsubmit — only passed for multiplayer coach hub views. */
  onSubmitWeek?: () => void
  onUnsubmitWeek?: () => void
  submitBusy?: boolean
  onSendChat?: (body: string) => Promise<LeagueChatMessage>
}

export default function LeagueDashboardPage({
  apiBase,
  headers,
  data,
  onBack,
  onOpenCoachDashboard,
  coachDashBusy = false,
  onSubmitWeek,
  onUnsubmitWeek,
  submitBusy = false,
  onSendChat,
}: LeagueDashboardPageProps) {
  const [expandedDivisions, setExpandedDivisions] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {}
    for (const div of data.division_submissions) {
      init[div.division] = div.submitted_count < div.total_count
    }
    return init
  })
  const [standingsMode, setStandingsMode] = useState<'division' | 'full'>('division')
  const [activeDivision, setActiveDivision] = useState(() => data.standings_by_division[0]?.division ?? '')
  const [slateFilter, setSlateFilter] = useState('All Games')
  const [chatMessages, setChatMessages] = useState<LeagueChatMessage[]>(data.chat_messages ?? [])
  const [chatDraft, setChatDraft] = useState('')
  const [chatBusy, setChatBusy] = useState(false)
  const [chatError, setChatError] = useState('')
  const [logoCount, setLogoCount] = useState(0)
  const [logoBusy, setLogoBusy] = useState(false)
  const [logoError, setLogoError] = useState('')
  const chatEndRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    setChatMessages(data.chat_messages ?? [])
  }, [data.chat_messages, data.league_id, data.state_version])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [chatMessages])

  useEffect(() => {
    let cancelled = false
    void fetchLeagueLogoPackStatus(apiBase, headers, data.league_id)
      .then((s) => {
        if (!cancelled) setLogoCount(s.logo_count || 0)
      })
      .catch(() => {
        if (!cancelled) setLogoCount(0)
      })
    return () => {
      cancelled = true
    }
  }, [apiBase, headers, data.league_id])

  const divisionFilters = useMemo(() => {
    const divs = new Set<string>()
    for (const g of data.slate_games) divs.add(g.division)
    return ['All Games', ...Array.from(divs).sort(), 'Notable']
  }, [data.slate_games])

  const filteredSlate = useMemo(() => {
    if (slateFilter === 'All Games') return data.slate_games
    if (slateFilter === 'Notable') return data.slate_games.filter((g) => g.notable)
    return data.slate_games.filter((g) => g.division === slateFilter)
  }, [data.slate_games, slateFilter])

  const standingsRows = useMemo(() => {
    if (standingsMode === 'full') return data.full_league_standings
    const block = data.standings_by_division.find((d) => d.division === activeDivision)
    return block?.rows ?? []
  }, [standingsMode, activeDivision, data])

  function toggleDivision(name: string) {
    setExpandedDivisions((prev) => ({ ...prev, [name]: !prev[name] }))
  }

  const weekShort = data.week_label.replace(/^Week\s+(\d+).*/, 'Week $1') || data.week_label
  const showCoachCta = Boolean(data.acting_team_name && onOpenCoachDashboard)

  return (
    <div className="ldash-root">
      <div className="ldash-topbar">
        <div className="ldash-league-identity">
          <div className="ldash-league-crest">{data.league_crest}</div>
          <div>
            <div className="ldash-league-name">{data.league_name}</div>
            <div className="ldash-league-sub">{data.league_subtitle}</div>
            {data.is_commissioner ? <span className="ldash-commish-badge">Commissioner</span> : null}
            {data.is_read_only_admin ? <span className="ldash-commish-badge">Admin view</span> : null}
          </div>
        </div>
        <div className="ldash-topbar-actions">
          <button type="button" className="ldash-back-btn" onClick={onBack}>
            ← Leagues
          </button>
          {data.logos_download_url ? (
            <button
              type="button"
              className="ldash-action-btn"
              title="Open the commissioner logo pack link"
              onClick={() =>
                window.open(data.logos_download_url!, '_blank', 'noopener,noreferrer')
              }
            >
              Download logos
            </button>
          ) : logoCount > 0 ? (
            <button
              type="button"
              className="ldash-action-btn"
              disabled={logoBusy}
              title={`${logoCount} league logo${logoCount === 1 ? '' : 's'} available`}
              onClick={() => {
                setLogoBusy(true)
                setLogoError('')
                const safe =
                  data.league_name.replace(/[^\w\-]+/g, '_').replace(/^_|_$/g, '') || 'league'
                void downloadLeagueLogoPack(apiBase, headers, data.league_id, `${safe}_logos.zip`)
                  .catch((err: unknown) => {
                    setLogoError(err instanceof Error ? err.message : 'Download failed')
                  })
                  .finally(() => setLogoBusy(false))
              }}
            >
              {logoBusy ? 'Downloading…' : 'Download logos'}
            </button>
          ) : null}
          {showCoachCta ? (
            <button
              type="button"
              className="ldash-action-btn ldash-action-btn--gold"
              disabled={coachDashBusy}
              onClick={onOpenCoachDashboard}
            >
              {coachDashBusy ? 'Opening…' : 'My dynasty'}
            </button>
          ) : null}
          {data.acting_team_name && onSubmitWeek && !data.your_status.submitted ? (
            <button
              type="button"
              className="ldash-action-btn ldash-action-btn--gold"
              disabled={submitBusy}
              onClick={onSubmitWeek}
            >
              {submitBusy ? 'Submitting…' : 'Submit week'}
            </button>
          ) : null}
          {data.acting_team_name && onUnsubmitWeek && data.your_status.submitted ? (
            <button
              type="button"
              className="ldash-action-btn"
              disabled={submitBusy || data.your_status.can_unsubmit === false}
              title={
                data.your_status.can_unsubmit === false
                  ? 'Locked — too close to the advance deadline'
                  : undefined
              }
              onClick={onUnsubmitWeek}
            >
              Unsubmit
            </button>
          ) : null}
        </div>
        <div className="ldash-week-status">
          <div className="ldash-week-badge">{data.week_label}</div>
          {data.countdown_value ? (
            <div className="ldash-countdown-block">
              <div className="ldash-countdown-label">{data.countdown_label ?? 'Advances in'}</div>
              <div className="ldash-countdown-value">{data.countdown_value}</div>
            </div>
          ) : null}
        </div>
      </div>

      <div className="ldash-grid">
        <div className="ldash-column">
          <div className="ldash-panel">
            <div className="ldash-panel-header">
              <span className="ldash-panel-title">
                Week <span className="accent">Progress</span>
              </span>
            </div>
            <div className="ldash-panel-body">
              <div className="ldash-progress-track">
                <div className="ldash-progress-fill" style={{ width: `${data.progress.percent}%` }} />
              </div>
              <div className="ldash-progress-caption">
                <span>
                  {data.progress.submitted} of {data.progress.total} submitted
                </span>
                <span>{data.progress.percent}%</span>
              </div>
            </div>
          </div>

          <div className="ldash-panel">
            <div className="ldash-panel-header">
              <span className="ldash-panel-title">
                Submission <span className="accent">Tracker</span>
              </span>
            </div>
            <div className="ldash-panel-body">
              {data.acting_team_name ? (
                <div className={`ldash-your-status${data.your_status.submitted ? '' : ' pending'}`}>
                  <div className="ldash-status-dot" />
                  <div>
                    <div className="ldash-your-status-text">{data.your_status.label}</div>
                    <div className="ldash-your-status-sub">{data.your_status.sub_label}</div>
                  </div>
                </div>
              ) : (
                <div className="ldash-your-status pending">
                  <div className="ldash-status-dot" />
                  <div>
                    <div className="ldash-your-status-text">League overview</div>
                    <div className="ldash-your-status-sub">Select a team to manage your school</div>
                  </div>
                </div>
              )}

              {data.division_submissions.map((div) => {
                const expanded = expandedDivisions[div.division] ?? false
                const complete = div.submitted_count >= div.total_count
                return (
                  <div key={div.division} className="ldash-div-group">
                    <button
                      type="button"
                      className={`ldash-div-header${expanded ? ' expanded' : ''}`}
                      onClick={() => toggleDivision(div.division)}
                    >
                      <span className="ldash-div-name">
                        <span className="chevron">▶</span>
                        {div.division}
                      </span>
                      <span className={`ldash-div-count${complete ? ' complete' : ''}`}>
                        {div.submitted_count}/{div.total_count}
                      </span>
                    </button>
                    {expanded ? (
                      <div className="ldash-div-teams">
                        {div.teams.map((t) => (
                          <span key={t.name} className={`ldash-team-chip${t.submitted ? ' in' : ' out'}`}>
                            <span className="dot" />
                            {t.name}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                )
              })}
            </div>
          </div>

          {data.featured_game ? (
            <div className="ldash-featured-game">
              <div className="ldash-featured-label">Your Game — {weekShort}</div>
              <div className="ldash-matchup">
                <div className="ldash-team-side">
                  <div className={`ldash-team-mark ${data.featured_game.is_home ? 'home' : 'away'}`}>
                    {data.featured_game.your_initials}
                  </div>
                  <div className="ldash-team-side-name">{data.featured_game.your_team}</div>
                  <div className="ldash-team-side-record">{data.featured_game.your_record}</div>
                </div>
                <div className="ldash-matchup-vs">{data.featured_game.is_home ? 'vs' : '@'}</div>
                <div className="ldash-team-side">
                  <div className={`ldash-team-mark ${data.featured_game.is_home ? 'away' : 'home'}`}>
                    {data.featured_game.opponent_initials}
                  </div>
                  <div className="ldash-team-side-name">{data.featured_game.opponent}</div>
                  <div className="ldash-team-side-record">{data.featured_game.opponent_record}</div>
                </div>
              </div>
              <div className="ldash-matchup-meta">
                <span>{data.featured_game.division}</span>
                {data.featured_game.tags.length > 0 ? (
                  <span className="tag">{data.featured_game.tags.join(' · ')}</span>
                ) : (
                  <span />
                )}
              </div>
            </div>
          ) : null}
        </div>

        <div className="ldash-column">
          <div className="ldash-panel ldash-chat-panel">
            <div className="ldash-panel-header">
              <span className="ldash-panel-title">
                League <span className="accent">Chat</span>
              </span>
            </div>
            <div className="ldash-chat-body">
              <div className="ldash-chat-system">
                📋 {data.progress.submitted}/{data.progress.total} teams have submitted for {data.week_label}
              </div>
              {chatMessages.length === 0 ? (
                <p className="ldash-chat-placeholder">No messages yet. Say hi to the league.</p>
              ) : (
                chatMessages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`ldash-chat-msg${msg.is_you ? ' ldash-chat-msg--you' : ''}`}
                  >
                    <div className="ldash-chat-msg-meta">
                      {msg.display_name}
                      {msg.time_label ? ` · ${msg.time_label}` : ''}
                    </div>
                    <div className="ldash-chat-msg-body">{msg.body}</div>
                  </div>
                ))
              )}
              <div ref={chatEndRef} />
              {chatError ? <p className="ldash-error" style={{ marginTop: 8 }}>{chatError}</p> : null}
              {logoError ? <p className="ldash-error" style={{ marginTop: 8 }}>{logoError}</p> : null}
            </div>
            <div className="ldash-chat-input-row">
              <input
                className="ldash-chat-input"
                type="text"
                placeholder={data.chat_enabled && onSendChat ? 'Message the league…' : 'Chat unavailable'}
                value={chatDraft}
                disabled={!data.chat_enabled || !onSendChat || chatBusy}
                maxLength={500}
                onChange={(e) => setChatDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    void (async () => {
                      if (!onSendChat || !chatDraft.trim() || chatBusy) return
                      setChatBusy(true)
                      setChatError('')
                      try {
                        const msg = await onSendChat(chatDraft.trim())
                        setChatMessages((prev) => [...prev, msg])
                        setChatDraft('')
                      } catch (err: unknown) {
                        setChatError(err instanceof Error ? err.message : 'Failed to send')
                      } finally {
                        setChatBusy(false)
                      }
                    })()
                  }
                }}
              />
              <button
                type="button"
                className="ldash-chat-send"
                disabled={!data.chat_enabled || !onSendChat || chatBusy || !chatDraft.trim()}
                onClick={() => {
                  void (async () => {
                    if (!onSendChat || !chatDraft.trim() || chatBusy) return
                    setChatBusy(true)
                    setChatError('')
                    try {
                      const msg = await onSendChat(chatDraft.trim())
                      setChatMessages((prev) => [...prev, msg])
                      setChatDraft('')
                    } catch (err: unknown) {
                      setChatError(err instanceof Error ? err.message : 'Failed to send')
                    } finally {
                      setChatBusy(false)
                    }
                  })()
                }}
              >
                {chatBusy ? '…' : 'Send'}
              </button>
            </div>
          </div>
        </div>

        <div className="ldash-column">
          <div className="ldash-panel">
            <div className="ldash-panel-header">
              <span className="ldash-panel-title">
                <span className="accent">Standings</span>
              </span>
            </div>
            <div className="ldash-panel-body">
              <div className="ldash-toggle-row">
                <button
                  type="button"
                  className={`ldash-toggle-btn${standingsMode === 'division' ? ' active' : ''}`}
                  onClick={() => setStandingsMode('division')}
                >
                  Division
                </button>
                <button
                  type="button"
                  className={`ldash-toggle-btn${standingsMode === 'full' ? ' active' : ''}`}
                  onClick={() => setStandingsMode('full')}
                >
                  Full league
                </button>
              </div>
              {standingsMode === 'division' && data.standings_by_division.length > 1 ? (
                <div className="ldash-slate-filters" style={{ marginBottom: 10 }}>
                  {data.standings_by_division.map((d) => (
                    <button
                      key={d.division}
                      type="button"
                      className={`ldash-filter-chip${activeDivision === d.division ? ' active' : ''}`}
                      onClick={() => setActiveDivision(d.division)}
                    >
                      {d.division.split('·').pop()?.trim() ?? d.division}
                    </button>
                  ))}
                </div>
              ) : null}
              <table className="ldash-standings-table">
                <thead>
                  <tr>
                    <th />
                    <th>Team</th>
                    <th style={{ textAlign: 'right' }}>W-L</th>
                  </tr>
                </thead>
                <tbody>
                  {standingsRows.map((row) => (
                    <tr key={`${row.rank}-${row.team}`} className={row.is_you ? 'you' : ''}>
                      <td className="rank">{row.rank}</td>
                      <td>{row.team}</td>
                      <td className="rec">{row.record}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="ldash-panel">
            <div className="ldash-panel-header">
              <span className="ldash-panel-title">
                League <span className="accent">Activity</span>
              </span>
            </div>
            <div className="ldash-panel-body">
              {data.activity.length === 0 ? (
                <p className="ldash-chat-placeholder">No recent activity yet.</p>
              ) : (
                data.activity.map((item, i) => (
                  <div key={`act-${i}`} className="ldash-activity-item">
                    <div className="ldash-activity-icon">{item.icon}</div>
                    <div>
                      <div className="ldash-activity-text">{item.text}</div>
                      <div className="ldash-activity-time">{item.time_label}</div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {data.slate_games.length > 0 ? (
        <div className="ldash-slate-section">
          <div className="ldash-slate-header">
            <div className="ldash-slate-title">
              {weekShort} <span className="accent">Full Slate</span>
            </div>
            <div className="ldash-slate-filters">
              {divisionFilters.map((f) => (
                <button
                  key={f}
                  type="button"
                  className={`ldash-filter-chip${slateFilter === f ? ' active' : ''}`}
                  onClick={() => setSlateFilter(f)}
                >
                  {f === 'All Games' ? f : f.split('·').pop()?.trim() ?? f}
                </button>
              ))}
            </div>
          </div>
          <div className="ldash-slate-grid">
            {filteredSlate.map((g) => (
              <div key={`${g.away}-${g.home}`} className={`ldash-slate-card${g.notable ? ' notable' : ''}`}>
                <div className="ldash-slate-div-tag">
                  {g.notable ? <span className="notable-star">★ </span> : null}
                  {g.division}
                  {g.tags.length > 0 ? ` · ${g.tags.join(' · ')}` : ''}
                </div>
                <div className="ldash-slate-matchup">
                  <div className="ldash-slate-team">
                    <div className="ldash-slate-mark g2">{g.away_initials}</div>
                    <div className="ldash-slate-team-name">{g.away}</div>
                  </div>
                </div>
                <div className="ldash-slate-vs">@</div>
                <div className="ldash-slate-matchup">
                  <div className="ldash-slate-team">
                    <div className="ldash-slate-mark">{g.home_initials}</div>
                    <div className="ldash-slate-team-name">{g.home}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
