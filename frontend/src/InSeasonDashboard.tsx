import { useMemo, useState } from 'react'
import './InSeasonDashboard.css'
import TeamLogo from './TeamLogo'
import TeamStadium from './TeamStadium'
import { useNews } from './news/NewsContext'
import { articleVisibleInFeed } from './news/newsVisibility'
import {
  buildGoalTiles,
  buildInboxPreview,
  buildLastGameRecap,
  buildOpponentScoutSummary,
  buildSeasonStatStrip,
  teamStadiumName,
  mapNewsArticles,
  parseScoreLine,
  rankForTeam,
  teamRecordLine,
  type ScheduleRow,
  type StandingsRow,
} from './inSeasonDashboardData'

type Props = {
  apiBase: string
  headers: Record<string, string>
  logoVersion: number
  stadiumVersion: number
  saveState: any
  userTeam: string
  currentWeek: number
  scheduleRows: ScheduleRow[]
  classStandings: StandingsRow[]
  teamStatsRow: {
    pointsFor: number
    pointsAgainst: number
    games: number
    totalYards: number
    turnovers: number
  } | null
  hasUnplayedGameThisWeek: boolean
  canContinue: boolean
  canStartCoachPlay: boolean
  playingWeek: boolean
  simmingWeek: boolean
  simMultipleCount: number
  onPlayGame: () => void
  onSimGame: () => void
  onSimMultiple: (weeks: number) => void
  onOpenOffGameplan: () => void
  onOpenDefGameplan: () => void
  onOpenScouting: () => void
  onOpenInbox: () => void
  onOpenGamePreview?: () => void
}

function findTeam(state: any, teamName: string) {
  return (state?.teams ?? []).find((t: { name?: string }) => t?.name === teamName) ?? null
}

function teamSchoolName(team: any, fallback: string): string {
  const name = String(team?.name ?? '').trim()
  return name || fallback
}

function teamDisplayName(team: any, fallback: string): string {
  const nick = String(team?.nickname ?? '').trim()
  return nick || fallback
}

export default function InSeasonDashboard({
  apiBase,
  headers,
  logoVersion,
  stadiumVersion,
  saveState,
  userTeam,
  currentWeek,
  scheduleRows,
  classStandings,
  teamStatsRow,
  hasUnplayedGameThisWeek,
  canContinue,
  canStartCoachPlay,
  playingWeek,
  simmingWeek,
  simMultipleCount,
  onPlayGame,
  onSimGame,
  onSimMultiple,
  onOpenOffGameplan,
  onOpenDefGameplan,
  onOpenScouting,
  onOpenInbox,
  onOpenGamePreview,
}: Props) {
  const [simChip, setSimChip] = useState(3)
  const { center } = useNews()

  const userRow = findTeam(saveState, userTeam)
  const userClass = String(userRow?.classification ?? '—')
  const userRegion = String(userRow?.region ?? '—')

  const currentGame = scheduleRows.find((r) => r.week === currentWeek)
  const opponent = currentGame?.opponent && !/^bye$/i.test(currentGame.opponent) ? currentGame.opponent : null
  const opponentTeam = opponent ? findTeam(saveState, opponent) : null

  const homeTeam = currentGame?.userHome ? userTeam : opponent ?? userTeam
  const venueTeam = currentGame?.userHome ? userRow : opponentTeam ?? userRow
  /** Stadium photo for the field where this week's game is played (home team). */
  const stadiumPhotoTeam = opponent && currentGame ? homeTeam : null

  const stadiumLine = teamStadiumName(venueTeam)
  const lastRecap = useMemo(() => buildLastGameRecap(saveState), [saveState])
  const statStrip = useMemo(
    () => buildSeasonStatStrip(saveState, userTeam, classStandings, teamStatsRow),
    [saveState, userTeam, classStandings, teamStatsRow],
  )
  const goalTiles = useMemo(
    () => buildGoalTiles(saveState, userTeam, scheduleRows, classStandings),
    [saveState, userTeam, scheduleRows, classStandings],
  )
  const inboxItems = useMemo(() => buildInboxPreview(saveState, 5), [
    saveState?.coach_inbox?.emails,
    saveState?.coach_inbox?.last_week_sim_batch_key,
    saveState?.current_week,
  ])
  const inboxUrgent = inboxItems.filter((i) => i.urgency === 'now' || i.urgency === 'soon').length
  const scout = useMemo(
    () => (opponent ? buildOpponentScoutSummary(saveState, opponent) : null),
    [saveState, opponent],
  )
  const newsRows = useMemo(() => {
    const articles = center.articles.filter((a) => articleVisibleInFeed(a, saveState))
    return mapNewsArticles(articles, 18)
  }, [center.articles, saveState])

  const userRank = rankForTeam(classStandings, userTeam)
  const oppRank = opponent ? rankForTeam(classStandings, opponent) : null
  const totalWeeks = scheduleRows.length

  const logoSlot = (teamName: string, size: number, className: string) => (
    <div className={className}>
      <TeamLogo apiBase={apiBase} headers={headers} teamName={teamName} logoVersion={logoVersion} size={size} />
    </div>
  )

  return (
    <div className="isdash" role="region" aria-label="Regular season dashboard">
      <div className="isdash-header">
        <div className="isdash-week-pill">
          Regular Season · <span className="isdash-week-num">Week {currentWeek}</span>
        </div>
        <div className="isdash-subline">
          {userTeam} · Class {userClass}
          {userRegion !== '—' ? ` · ${userRegion} Region` : ''}
        </div>
      </div>

      <div className="isdash-grid">
        <div className="isdash-left">
          <section>
            <div className="isdash-section-label">Next Game</div>
            <div className="isdash-card isdash-card-flush">
              <div className="isdash-stadium-visual">
                {stadiumPhotoTeam ? (
                  <TeamStadium
                    key={`${stadiumPhotoTeam}-${stadiumVersion}`}
                    apiBase={apiBase}
                    headers={headers}
                    teamName={stadiumPhotoTeam}
                    stadiumVersion={stadiumVersion}
                    hidePlaceholder
                    className="isdash-stadium-photo"
                  />
                ) : null}
              </div>
              <div className="isdash-next-body">
                <div className="isdash-badge-row">
                  <span className="isdash-game-badge">This Friday · 7:00 PM</span>
                  {currentGame?.isRegionGame ? <span className="isdash-region-badge">★ Region Game</span> : null}
                  {opponent && hasUnplayedGameThisWeek && onOpenGamePreview ? (
                    <button type="button" className="isdash-preview-btn" onClick={onOpenGamePreview}>
                      Preview
                    </button>
                  ) : null}
                </div>
                {opponent ? (
                  <div className="isdash-matchup">
                    <div className="isdash-team-col">
                      {logoSlot(userTeam, 40, 'isdash-team-logo')}
                      <div className="isdash-team-name">{teamSchoolName(userRow, userTeam)}</div>
                      <div className="isdash-team-rec">{teamRecordLine(saveState, userTeam)}</div>
                      {userRank ? <div className="isdash-team-rank">#{userRank} STATE</div> : null}
                    </div>
                    <div className="isdash-vs">
                      <div className="isdash-vs-label">VS</div>
                      <div className="isdash-vs-time">FRI 7:00</div>
                      <div className="isdash-vs-site">{currentGame?.userHome ? 'HOME' : 'AWAY'}</div>
                    </div>
                    <div className="isdash-team-col">
                      {logoSlot(opponent, 40, 'isdash-team-logo')}
                      <div className="isdash-team-name">{teamSchoolName(opponentTeam, opponent)}</div>
                      <div className="isdash-team-rec">{teamRecordLine(saveState, opponent)}</div>
                      {oppRank ? <div className="isdash-team-rank">#{oppRank} STATE</div> : null}
                    </div>
                  </div>
                ) : (
                  <div className="isdash-empty">No game scheduled this week.</div>
                )}
                {currentGame?.homeThemeLabel ? (
                  <>
                    <div className="isdash-theme-title">⚡ {currentGame.homeThemeLabel}</div>
                    {stadiumLine ? <div className="isdash-theme-sub">{stadiumLine}</div> : null}
                  </>
                ) : stadiumLine ? (
                  <div className="isdash-theme-sub" style={{ marginTop: 10, textAlign: 'center' }}>
                    {stadiumLine}
                  </div>
                ) : null}
              </div>
            </div>
          </section>

          <section>
            <div className="isdash-section-label">Game Week</div>
            <div className="isdash-actions-grid">
              <button
                type="button"
                className="isdash-btn isdash-btn-play"
                disabled={!canStartCoachPlay || playingWeek || !hasUnplayedGameThisWeek}
                onClick={onPlayGame}
              >
                {playingWeek ? 'Loading…' : '▶ Play Game'}
              </button>
              <button
                type="button"
                className="isdash-btn isdash-btn-sim"
                disabled={!canContinue || simmingWeek}
                onClick={onSimGame}
              >
                {simmingWeek ? 'Simming…' : '⏩ Sim Game'}
              </button>
              <button type="button" className="isdash-btn isdash-btn-gameplan" onClick={onOpenOffGameplan}>
                📋 OFF Gameplan
              </button>
              <button type="button" className="isdash-btn isdash-btn-gameplan-def" onClick={onOpenDefGameplan}>
                🛡 DEF Gameplan
              </button>
              <button type="button" className="isdash-btn isdash-btn-scout isdash-btn-scout-wide" onClick={onOpenScouting}>
                🔍 Scouting Report
              </button>
            </div>
            <div className="isdash-sim-multi">
              <span className="isdash-sim-label">Sim Multiple</span>
              <div className="isdash-sim-chips">
                {[2, 3, 4, 5].map((n) => (
                  <button
                    key={n}
                    type="button"
                    className={`isdash-sim-chip${simChip === n ? ' isdash-sim-chip--active' : ''}`}
                    disabled={simMultipleCount > 0 || simmingWeek || !canContinue}
                    onClick={() => {
                      setSimChip(n)
                      onSimMultiple(n)
                    }}
                  >
                    {simMultipleCount === n ? '…' : n}
                  </button>
                ))}
              </div>
              <span style={{ fontSize: 11, color: '#444' }}>games</span>
            </div>
          </section>

          <section>
            <div className="isdash-section-label">Season Stats</div>
            <div className="isdash-stats-strip">
              {statStrip.map((s) => (
                <div key={s.label} className="isdash-stat-tile">
                  <div
                    className={`isdash-stat-val${s.positive ? ' isdash-stat-val--pos' : ''}${s.negative ? ' isdash-stat-val--neg' : ''}`}
                  >
                    {s.value}
                  </div>
                  <div className="isdash-stat-lbl">{s.label}</div>
                  <div className="isdash-stat-sub">{s.sub}</div>
                </div>
              ))}
            </div>
          </section>

          <section>
            <div className="isdash-section-label">
              The Slate — Week {currentWeek} of {totalWeeks || '—'}
            </div>
            <div className="isdash-schedule-list">
              {scheduleRows.map((r) => {
                const isNext = r.week === currentWeek && !r.played
                const isFuture = !r.played && r.week > currentWeek
                const parsed = r.played ? parseScoreLine(r.scoreLine) : null
                const rowClass = [
                  'isdash-game-row',
                  parsed?.outcome === 'W' ? 'isdash-game-row--win' : '',
                  parsed?.outcome === 'L' ? 'isdash-game-row--loss' : '',
                  isNext ? 'isdash-game-row--next' : '',
                  isFuture ? 'isdash-game-row--future' : '',
                ]
                  .filter(Boolean)
                  .join(' ')
                return (
                  <div key={r.week} className={rowClass}>
                    <div className={`isdash-wk${isNext ? ' isdash-wk--cur' : ''}`}>W{r.week}</div>
                    <div className="isdash-sched-logo">
                      {r.opponent && !/^bye$/i.test(r.opponent) ? (
                        <TeamLogo apiBase={apiBase} headers={headers} teamName={r.opponent} logoVersion={logoVersion} size={24} />
                      ) : (
                        '—'
                      )}
                    </div>
                    <div className="isdash-sched-info">
                      <div className={`isdash-sched-opp${isNext ? ' isdash-sched-opp--cur' : ''}`}>{r.opponent || 'BYE'}</div>
                      <div className="isdash-sched-meta">
                        {r.userHome ? 'HOME' : 'AWAY'}
                        {r.isRegionGame ? (
                          <>
                            {' '}
                            · <span className="isdash-reg">★ Region</span>
                          </>
                        ) : null}
                      </div>
                    </div>
                    <div className="isdash-sched-result">
                      {r.played && parsed?.outcome ? (
                        <>
                          <div className={`isdash-res-badge isdash-res-badge--${parsed.outcome.toLowerCase()}`}>
                            {parsed.outcome}
                          </div>
                          <div className="isdash-res-score">
                            {parsed.userScore} – {parsed.oppScore}
                          </div>
                        </>
                      ) : isNext ? (
                        <>
                          <div className="isdash-res-upcoming">FRI</div>
                          <div className="isdash-res-time">7:00 PM</div>
                        </>
                      ) : (
                        <div style={{ fontSize: 11, color: '#333' }}>—</div>
                      )}
                    </div>
                    {isNext ? <div className="isdash-now-pip" /> : <div className="isdash-blank-pip" />}
                  </div>
                )
              })}
            </div>
          </section>

          <section>
            <div className="isdash-section-label">Season Goals</div>
            <div className="isdash-goals-grid">
              {goalTiles.map((g) => (
                <div key={g.name} className="isdash-goal-tile">
                  <div className="isdash-goal-head">
                    <span className="isdash-goal-name">{g.name}</span>
                    <span className={`isdash-goal-status isdash-goal-status--${g.status}`}>{g.statusLabel}</span>
                  </div>
                  <div className="isdash-goal-progress">
                    <div
                      className={`isdash-goal-bar isdash-goal-bar--${g.status === 'on' ? 'green' : g.status === 'track' ? 'yellow' : 'red'}`}
                      style={{ width: `${Math.max(4, g.progressPct)}%` }}
                    />
                  </div>
                  <div className="isdash-goal-desc">{g.description}</div>
                  <div className="isdash-goal-sub">{g.sub}</div>
                </div>
              ))}
            </div>
          </section>
        </div>

        <div className="isdash-right">
          <div className="isdash-card">
            <div className="isdash-inbox-head">
              <div className="isdash-section-label" style={{ marginBottom: 0 }}>
                Coach&apos;s Inbox
              </div>
              {inboxUrgent > 0 ? <span className="isdash-inbox-alert">{inboxUrgent} need you</span> : null}
            </div>
            {inboxItems.length === 0 ? (
              <div className="isdash-empty">Inbox clear — new mail arrives after you Sim Game each week.</div>
            ) : (
              inboxItems.map((item) => (
                <div key={item.id} className="isdash-inbox-item">
                  <div
                    className={`isdash-inbox-dot isdash-dot-${item.urgency === 'now' ? 'now' : item.urgency === 'soon' ? 'soon' : item.urgency === 'done' ? 'done' : 'info'}`}
                  />
                  <div className="isdash-inbox-text">
                    <div className="isdash-inbox-title">{item.title}</div>
                    <div className="isdash-inbox-sub">
                      {item.week > 0 ? `Week ${item.week} · ` : ''}
                      {item.sub}
                    </div>
                    <button type="button" className="isdash-inbox-link" onClick={onOpenInbox}>
                      {item.linkLabel}
                    </button>
                  </div>
                  <div
                    className={`isdash-inbox-badge isdash-badge-${item.urgency === 'now' ? 'now' : item.urgency === 'soon' ? 'soon' : item.urgency === 'done' ? 'done' : 'info'}`}
                  >
                    {item.urgency === 'now' ? 'NOW' : item.urgency === 'soon' ? 'SOON' : item.urgency === 'done' ? 'DONE' : 'INFO'}
                  </div>
                </div>
              ))
            )}
          </div>

          {lastRecap ? (
            <div className="isdash-card-sm">
              <div className="isdash-section-label">Last Game · Week {lastRecap.week}</div>
              <div className="isdash-recap-headline">{lastRecap.headline}</div>
              <div className="isdash-recap-score">
                <div className="isdash-recap-team">
                  {logoSlot(userTeam, 32, 'isdash-recap-logo')}
                  <div>
                    <div className="isdash-recap-name">{teamDisplayName(userRow, userTeam)}</div>
                    <div className={`isdash-recap-pts${lastRecap.won ? ' isdash-recap-pts--win' : ' isdash-recap-pts--loss'}`}>
                      {lastRecap.userScore}
                    </div>
                  </div>
                </div>
                <div className="isdash-recap-divider">FINAL</div>
                <div className="isdash-recap-team isdash-recap-team--away">
                  {logoSlot(lastRecap.opponent, 32, 'isdash-recap-logo')}
                  <div style={{ textAlign: 'right' }}>
                    <div className="isdash-recap-name">{teamDisplayName(findTeam(saveState, lastRecap.opponent), lastRecap.opponent)}</div>
                    <div className={`isdash-recap-pts${!lastRecap.won ? ' isdash-recap-pts--win' : ' isdash-recap-pts--loss'}`}>
                      {lastRecap.oppScore}
                    </div>
                  </div>
                </div>
              </div>
              <div className="isdash-recap-stats">
                <div className="isdash-recap-stat">
                  <div className="isdash-recap-stat-val">{lastRecap.passYds}</div>
                  <div className="isdash-recap-stat-lbl">Pass Yds</div>
                </div>
                <div className="isdash-recap-stat">
                  <div className="isdash-recap-stat-val">{lastRecap.rushYds}</div>
                  <div className="isdash-recap-stat-lbl">Rush Yds</div>
                </div>
                <div className="isdash-recap-stat">
                  <div className="isdash-recap-stat-val">{lastRecap.tds}</div>
                  <div className="isdash-recap-stat-lbl">TDs</div>
                </div>
                <div className="isdash-recap-stat">
                  <div className="isdash-recap-stat-val">{lastRecap.interceptions}</div>
                  <div className="isdash-recap-stat-lbl">INT</div>
                </div>
                <div className="isdash-recap-stat">
                  <div className="isdash-recap-stat-val">{lastRecap.sacks}</div>
                  <div className="isdash-recap-stat-lbl">Sacks</div>
                </div>
                <div className="isdash-recap-stat">
                  <div className="isdash-recap-stat-val">{lastRecap.compPct != null ? `${lastRecap.compPct}%` : '—'}</div>
                  <div className="isdash-recap-stat-lbl">Comp %</div>
                </div>
              </div>
            </div>
          ) : null}

          {scout && opponent ? (
            <div className="isdash-card-sm">
              <div className="isdash-section-label">Scouting · {teamDisplayName(opponentTeam, opponent)}</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div className="isdash-scout-row">
                  <span>Offense</span>
                  <span style={{ color: '#fff', fontWeight: 600 }}>{scout.offense}</span>
                </div>
                <div className="isdash-scout-row">
                  <span>Defense</span>
                  <span style={{ color: '#fff', fontWeight: 600 }}>{scout.defense}</span>
                </div>
                <div className="isdash-scout-row">
                  <span>Weakness</span>
                  <span className="isdash-scout-weak">{scout.weakness}</span>
                </div>
                <div className="isdash-scout-row">
                  <span>Watch out for</span>
                  <span className="isdash-scout-watch">{scout.watch}</span>
                </div>
              </div>
            </div>
          ) : null}

          <div className="isdash-card-sm">
            <div className="isdash-section-label">
              {userClass} Standings · Week {currentWeek}
            </div>
            {classStandings.slice(0, 5).map((r) => (
              <div key={r.teamName} className="isdash-stand-row">
                <span className="isdash-stand-pos">#{r.rank}</span>
                <span className={`isdash-stand-name${r.teamName === userTeam ? ' isdash-stand-name--you' : ''}`}>{r.teamName}</span>
                <span className="isdash-stand-rec">
                  {r.wins}-{r.losses}
                </span>
              </div>
            ))}
          </div>

          <div className="isdash-card-sm">
            <div className="isdash-section-label">League News</div>
            {newsRows.length === 0 ? (
              <div className="isdash-empty">No headlines yet.</div>
            ) : (
              newsRows.map((n) => (
                <div key={n.id} className="isdash-news-item">
                  <span className={`isdash-news-tag isdash-${n.tagClass}`}>{n.tag}</span>
                  <div className="isdash-news-headline">{n.headline}</div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
