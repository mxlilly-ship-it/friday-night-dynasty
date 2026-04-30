import { Fragment, useEffect, useMemo, useState } from 'react'
import TeamLogo from './TeamLogo'
import { COACH_ATTRIBUTE_GROUPS, formatCoachAttributeCell } from './coachAttributes'
import {
  aggregateCoachCareer,
  buildCoachHistoryFromLeagueHistory,
  findLocalSeasonRecap,
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
  const isLocalBundle = saveId === '__local__'
  const team = teamName ? findTeam(saveState, teamName) : null

  const [historyRows, setHistoryRows] = useState<CoachHistoryRow[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)

  useEffect(() => {
    if (!coachName || coachName === '—') {
      setHistoryRows([])
      return
    }
    if (leagueHistory != null) {
      setHistoryRows(buildCoachHistoryFromLeagueHistory(leagueHistory, coachName))
      return
    }
    if (isLocalBundle || !apiBase || !saveId) {
      setHistoryRows([])
      return
    }
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
  }, [apiBase, coachName, headers, isLocalBundle, leagueHistory, saveId])

  const career = useMemo(() => aggregateCoachCareer(historyRows), [historyRows])

  const st = teamName ? saveState?.standings?.[teamName] : null
  const seasonWins = st != null ? Number(st?.wins ?? 0) : Number(team?.wins ?? 0)
  const seasonLosses = st != null ? Number(st?.losses ?? 0) : Number(team?.losses ?? 0)
  const programChampionships = Number(team?.championships ?? 0)
  const programRegionals = Number(team?.regional_championships ?? 0)
  const prestige = team?.prestige != null ? String(team.prestige) : '—'

  const teamWithLogo = (name: string, size = 22) => (
    <span className="teamhome-name-with-logo coach-profile-team-logo">
      <TeamLogo apiBase={apiBase} teamName={name} logoVersion={logoVersion} headers={headers} size={size} />
      <span>{name}</span>
    </span>
  )

  const downloadRecap = async (rowTeam: string, year: number | string) => {
    if (isLocalBundle && seasonRecaps) {
      const text = findLocalSeasonRecap(seasonRecaps, rowTeam, year)
      if (!text) {
        onError('Recap not found in this save zip for that season.')
        return
      }
      const blob = new Blob([text], { type: 'text/plain' })
      const dlUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = dlUrl
      a.download = `${rowTeam.replaceAll(' ', '_')}_Year_${year}_recap.txt`
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(dlUrl), 250)
      onError('')
      return
    }
    try {
      const url = `${apiBase}/saves/${saveId}/team-history/recap.txt?team_name=${encodeURIComponent(
        rowTeam,
      )}&year=${encodeURIComponent(String(year))}`
      const resp = await fetch(url, { headers })
      if (!resp.ok) throw new Error(await resp.text())
      const text = await resp.text()
      const blob = new Blob([text], { type: 'text/plain' })
      const dlUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = dlUrl
      a.download = `${rowTeam.replaceAll(' ', '_')}_Year_${year}_recap.txt`
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(dlUrl), 250)
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
                This season {teamName ? `${seasonWins}-${seasonLosses}` : '—'}
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
        ) : historyRows.length === 0 ? (
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
              {historyRows.map((r) => (
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
