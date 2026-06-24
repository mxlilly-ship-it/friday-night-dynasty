import { Fragment, useEffect, useMemo, useState } from 'react'
import TeamLogo from './TeamLogo'
import { COACH_ATTRIBUTE_GROUPS, formatCoachAttributeCell } from './coachAttributes'
import {
  ALL_COACHING_CARDS,
  normalizeLoadout,
  type CoachingCardLoadout,
} from './coachingCards'
import './CoachingCardPicker.css'
import {
  aggregateCoachCareer,
  buildCoachHistoryFromLeagueHistory,
  downloadTeamSeasonRecap,
  mergeInProgressCoachHistory,
  type CoachHistoryRow,
} from './coachHistory'
import './TeamHomePage.css'
import './PlayerProfilePage.css'
import './CoachProfilePage.css'

function findTeam(state: any, teamName: string) {
  return (state?.teams ?? []).find((t: any) => t?.name === teamName) ?? null
}

type Props = {
  apiBase: string
  headers: Record<string, string>
  saveId: string
  logoVersion: number
  teamName: string
  coach: any
  saveState: any
  leagueHistory?: any
  seasonRecaps?: Record<string, string>
  onClose: () => void
  onError: (msg: string) => void
}

export default function CoachProfilePage({
  apiBase,
  headers,
  saveId,
  logoVersion,
  teamName,
  coach,
  saveState,
  leagueHistory,
  seasonRecaps,
  onClose,
  onError,
}: Props) {
  const coachName = String(coach?.name ?? '—')
  const isLocalBundle = saveId === '__local__' || saveId.startsWith('b_')
  const team = teamName ? findTeam(saveState, teamName) : null

  const [historyRows, setHistoryRows] = useState<CoachHistoryRow[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)

  useEffect(() => {
    if (!coachName || coachName === '—') {
      setHistoryRows([])
      return
    }
    if (!isLocalBundle) return
    if (leagueHistory != null) {
      setHistoryRows(
        buildCoachHistoryFromLeagueHistory(
          leagueHistory,
          coachName,
          saveState?.teams,
          saveState?.coach_career_log,
        ),
      )
    } else {
      setHistoryRows([])
    }
  }, [coachName, isLocalBundle, leagueHistory, saveState?.teams, saveState?.coach_career_log])

  useEffect(() => {
    if (!coachName || coachName === '—') {
      setHistoryRows([])
      return
    }
    if (isLocalBundle) return
    if (!apiBase || !saveId) {
      setHistoryRows([])
      return
    }
    setHistoryRows([])
    let cancelled = false
    setHistoryLoading(true)
    void (async () => {
      try {
        const r = await fetch(
          `${apiBase}/saves/${saveId}/coach-history?coach_name=${encodeURIComponent(coachName)}`,
          { headers },
        )
        if (!r.ok) throw new Error(await r.text())
        const j = await r.json()
        if (!cancelled) {
          setHistoryRows(Array.isArray(j?.history) ? j.history : [])
          onError('')
        }
      } catch (e: any) {
        if (!cancelled) {
          setHistoryRows([])
          onError(e?.message ?? 'Failed to load coach history')
        }
      } finally {
        if (!cancelled) setHistoryLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- onError from parent; avoid refetch loops
  }, [
    apiBase,
    coachName,
    headers,
    isLocalBundle,
    saveId,
    saveState?.current_year,
    saveState?.season_phase,
    saveState?.last_completed_year,
  ])

  const displayRows = useMemo(
    () => mergeInProgressCoachHistory(historyRows, coachName, teamName, saveState),
    [historyRows, coachName, teamName, saveState],
  )

  const career = useMemo(() => aggregateCoachCareer(displayRows), [displayRows])

  const st = teamName ? saveState?.standings?.[teamName] : null
  const liveWins = st != null ? Number(st?.wins ?? 0) : Number(team?.wins ?? 0)
  const liveLosses = st != null ? Number(st?.losses ?? 0) : Number(team?.losses ?? 0)
  // Outside regular/playoffs the live ``standings`` are stale (reset to 0-0 by
  // finish_season; can't accrue regular-season W-L in offseason/preseason). Always
  // prefer the just-finished season's snapshot when available so this line doesn't
  // read "This season 0-0" on every offseason / preseason screen.
  const _phaseLower = String(saveState?.season_phase ?? '')
    .trim()
    .toLowerCase()
  const _snap = teamName ? saveState?.last_completed_standings?.[teamName] : null
  const _useSnapshot =
    teamName != null &&
    _phaseLower !== 'regular' &&
    _phaseLower !== 'playoffs' &&
    _snap != null &&
    typeof _snap === 'object'
  const seasonWins = _useSnapshot ? Number(_snap?.wins ?? 0) : liveWins
  const seasonLosses = _useSnapshot ? Number(_snap?.losses ?? 0) : liveLosses
  const seasonRecordLabel = _useSnapshot ? 'Last season' : 'This season'
  const seasonRecordYear =
    _useSnapshot && Number.isFinite(Number(saveState?.last_completed_year))
      ? Number(saveState.last_completed_year)
      : null
  const programChampionships = Number(team?.championships ?? 0)
  const programRegionals = Number(team?.regional_championships ?? 0)
  const prestige = team?.prestige != null ? String(team.prestige) : '—'

  const coachingCards = useMemo((): CoachingCardLoadout => normalizeLoadout(coach?.coaching_cards), [coach?.coaching_cards])
  const equippedCards = useMemo(
    () => ALL_COACHING_CARDS.filter((c) => {
      const lo = coachingCards
      if (c.layer === 'program') return lo.program_identity === c.id
      if (c.layer === 'position') return lo.position.includes(c.id)
      return lo.platinum.includes(c.id)
    }),
    [coachingCards],
  )

  const teamWithLogo = (name: string, size = 22) => (
    <span className="teamhome-name-with-logo coach-profile-team-logo">
      <TeamLogo apiBase={apiBase} teamName={name} logoVersion={logoVersion} headers={headers} size={size} />
      <span>{name}</span>
    </span>
  )

  const downloadRecap = async (rowTeam: string, year: number | string) => {
    try {
      await downloadTeamSeasonRecap({
        apiBase,
        headers,
        saveId,
        teamName: rowTeam,
        year,
        seasonRecaps,
        isLocalBundle,
      })
      onError('')
    } catch (e: any) {
      onError(e?.message ?? 'Failed to download recap')
    }
  }

  return (
    <div className="player-profile coach-profile-page">
      <div className="player-profile-top">
        <button type="button" className="player-profile-back" onClick={onClose}>
          ← Back
        </button>
        <div className="player-profile-identity">
          {teamName ? (
            <TeamLogo apiBase={apiBase} teamName={teamName} logoVersion={logoVersion} headers={headers} size={56} />
          ) : null}
          <div className="player-profile-title-block">
            <h1>{coachName}</h1>
            <p className="player-profile-meta">
              {teamName ? (
                <>
                  Current program: {teamWithLogo(teamName, 20)}
                </>
              ) : (
                'No program linked in save (coach matched by name only).'
              )}
            </p>
            <div className="player-profile-ratings coach-profile-summary-line">
              <span>
                {seasonRecordLabel}
                {seasonRecordYear != null ? ` (${seasonRecordYear})` : ''}{' '}
                {teamName ? `${seasonWins}-${seasonLosses}` : '—'}
              </span>
              <span>Program titles {programChampionships}</span>
              <span>Program regionals {programRegionals}</span>
              <span>Prestige {prestige}</span>
            </div>
          </div>
        </div>
      </div>

      <section className="player-profile-attrs coach-profile-attrs" aria-label="Coach attributes">
        {COACH_ATTRIBUTE_GROUPS.map((g) => (
          <div key={g.title} className="player-profile-attr-col">
            <h2>{g.title}</h2>
            <dl className="player-profile-attr-grid">
              {g.rows.map((row) => (
                <Fragment key={row.key}>
                  <dt>{row.label}</dt>
                  <dd>{formatCoachAttributeCell(coach, row.key)}</dd>
                </Fragment>
              ))}
            </dl>
          </div>
        ))}
        {coach?.preferred_schemes && typeof coach.preferred_schemes === 'object' && Object.keys(coach.preferred_schemes).length > 0 ? (
          <div className="player-profile-attr-col">
            <h2>Preferred schemes</h2>
            <dl className="player-profile-attr-grid">
              <dt>Raw</dt>
              <dd>{formatCoachAttributeCell(coach, 'preferred_schemes')}</dd>
            </dl>
          </div>
        ) : null}
      </section>

      <section className="coach-cards-panel" aria-label="Coaching cards">
        <h2>Coaching cards</h2>
        {equippedCards.length === 0 ? (
          <p className="teamhome-small" style={{ color: '#64748b', margin: 0 }}>
            No coaching cards equipped.
          </p>
        ) : (
          <div className="coach-cards-mini-grid">
            {equippedCards.map((c) => (
              <div
                key={c.id}
                className="coach-card-mini"
                style={{ '--cc-accent': c.accent } as React.CSSProperties}
              >
                <strong>{c.name}</strong>
                <span>{c.ability}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="coach-profile-career" aria-label="Career from league history">
        <h2 className="coach-profile-section-title">Career (saved seasons)</h2>
        <div className="coach-profile-career-grid">
          <div className="coach-profile-career-tile">
            <span className="coach-profile-career-label">Seasons logged</span>
            <span className="coach-profile-career-val">{career.seasons}</span>
          </div>
          <div className="coach-profile-career-tile">
            <span className="coach-profile-career-label">Career W-L</span>
            <span className="coach-profile-career-val">
              {career.seasons ? `${career.totalWins}-${career.totalLosses}` : '—'}
            </span>
          </div>
          <div className="coach-profile-career-tile">
            <span className="coach-profile-career-label">State championships</span>
            <span className="coach-profile-career-val">{career.stateChampionships}</span>
          </div>
          <div className="coach-profile-career-tile">
            <span className="coach-profile-career-label">Runner-up finishes</span>
            <span className="coach-profile-career-val">{career.runnerUps}</span>
          </div>
        </div>
        <p className="coach-profile-career-hint">
          Regionals are tracked on the program in the current save; postseason labels below reflect each finished season in league history.
        </p>
      </section>

      <section className="coach-profile-history" aria-label="Season history">
        <h2 className="coach-profile-section-title">History</h2>
        {historyLoading ? (
          <p className="player-profile-stats-empty">Loading history…</p>
        ) : displayRows.length === 0 ? (
          <p className="player-profile-stats-empty">
            No league history rows for this coach yet (finish a season with history saved, or import a zip that includes league_history.json).
          </p>
        ) : (
          <>
            <div className="teamhome-roster-head teamhome-roster-row teamhome-team-history-row coach-profile-history-head">
              <div className="teamhome-roster-cell">Year</div>
              <div className="teamhome-roster-cell">Team</div>
              <div className="teamhome-roster-cell">W-L</div>
              <div className="teamhome-roster-cell">Postseason</div>
              <div className="teamhome-roster-cell">Coach</div>
              <div className="teamhome-roster-cell teamhome-team-history-cell-recap">Recap</div>
            </div>
            <div className="teamhome-roster-table">
              {displayRows.map((r) => (
                <div key={`${r.year}-${r.team}`} className="teamhome-roster-row teamhome-team-history-row">
                  <div className="teamhome-roster-cell">{r.year ?? '—'}</div>
                  <div className="teamhome-roster-cell teamhome-team-history-cell-team">{teamWithLogo(r.team, 22)}</div>
                  <div className="teamhome-roster-cell">
                    {typeof r.wins === 'number' && typeof r.losses === 'number' ? `${r.wins}-${r.losses}` : '—'}
                  </div>
                  <div className="teamhome-roster-cell">{r.postseason ?? '—'}</div>
                  <div className="teamhome-roster-cell">{r.coach ?? '—'}</div>
                  <div className="teamhome-roster-cell teamhome-team-history-cell-recap">
                    <button
                      type="button"
                      className="teamhome-schedule-link"
                      disabled={
                        !r.has_recap &&
                        !(isLocalBundle && seasonRecaps && Object.keys(seasonRecaps).length > 0)
                      }
                      onClick={() => downloadRecap(r.team, r.year ?? '')}
                    >
                      Recap
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  )
}
