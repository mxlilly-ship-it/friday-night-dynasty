import { useMemo, useState } from 'react'
import { CoachProfileName } from './CoachProfileContext'
import TeamLogo from './TeamLogo'
import { buildCoachStatsLeaderboard, type CoachStatsRow } from './coachHistory'
import './CoachStatsPage.css'

type SortKey = keyof Pick<
  CoachStatsRow,
  | 'coachName'
  | 'school'
  | 'wins'
  | 'losses'
  | 'winPct'
  | 'regionalTitles'
  | 'playoffAppearances'
  | 'stateRunnerUps'
  | 'stateChampionships'
>

type Props = {
  saveState: any
  leagueHistory: any
  apiBase: string
  headers: Record<string, string>
  logoVersion: number
  userCoachName?: string
}

function formatWinPct(pct: number): string {
  if (!Number.isFinite(pct) || pct <= 0) return '.000'
  return pct.toFixed(3).replace(/^0/, '')
}

export default function CoachStatsPage({
  saveState,
  leagueHistory,
  apiBase,
  headers,
  logoVersion,
  userCoachName,
}: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('stateChampionships')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  const rows = useMemo(
    () => buildCoachStatsLeaderboard(saveState, leagueHistory),
    [saveState, leagueHistory],
  )

  const sortedRows = useMemo(() => {
    const arr = [...rows]
    arr.sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      if (typeof av === 'string' && typeof bv === 'string') {
        const cmp = av.localeCompare(bv)
        return sortDir === 'asc' ? cmp : -cmp
      }
      const an = Number(av)
      const bn = Number(bv)
      return sortDir === 'asc' ? an - bn : bn - an
    })
    return arr
  }, [rows, sortDir, sortKey])

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir(key === 'coachName' || key === 'school' ? 'asc' : 'desc')
    }
  }

  const userNorm = String(userCoachName ?? '')
    .trim()
    .toLowerCase()

  const teamWithLogo = (name: string) =>
    name ? (
      <span className="teamhome-name-with-logo">
        <TeamLogo apiBase={apiBase} teamName={name} logoVersion={logoVersion} headers={headers} size={20} />
        <span>{name}</span>
      </span>
    ) : (
      '—'
    )

  return (
    <div className="teamhome-roster-shell coach-stats-page">
      <div className="teamhome-teaminfo-header">
        <div className="teamhome-card-title" style={{ marginBottom: 0 }}>
          Coach Stats
        </div>
        <div className="teamhome-small" style={{ marginTop: 8, opacity: 0.9, maxWidth: 640, lineHeight: 1.45 }}>
          Head coach career totals across the dynasty. Click a column header to sort. Coach names open the full profile.
        </div>
      </div>

      <div className="teamhome-roster-head" style={{ marginTop: 12 }}>
        Click a column to sort
      </div>

      <div className="teamhome-roster-table">
        <div className="coach-stats-row coach-stats-row-head">
          <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleSort('coachName')}>
            Coach
          </button>
          <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleSort('school')}>
            School
          </button>
          <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleSort('wins')}>
            W
          </button>
          <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleSort('losses')}>
            L
          </button>
          <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleSort('winPct')}>
            Win %
          </button>
          <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleSort('regionalTitles')}>
            Regional
          </button>
          <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleSort('playoffAppearances')}>
            Playoffs
          </button>
          <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleSort('stateRunnerUps')}>
            State RU
          </button>
          <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleSort('stateChampionships')}>
            State
          </button>
        </div>

        {sortedRows.length === 0 ? (
          <div className="teamhome-roster-empty">No head coach history yet.</div>
        ) : (
          sortedRows.map((r) => {
            const isUser =
              userNorm.length > 0 && r.coachName.trim().toLowerCase() === userNorm
            return (
              <div
                key={r.coachName}
                className={`coach-stats-row${isUser ? ' coach-stats-row--user' : ''}`}
              >
                <div className="teamhome-roster-name">
                  <CoachProfileName mode="by-name" coachName={r.coachName} as="span" />
                  {isUser ? <span className="coach-stats-you-tag"> (you)</span> : null}
                </div>
                <div className="teamhome-roster-name">{teamWithLogo(r.school)}</div>
                <div className="teamhome-roster-cell">{r.wins}</div>
                <div className="teamhome-roster-cell">{r.losses}</div>
                <div className="teamhome-roster-cell">{formatWinPct(r.winPct)}</div>
                <div className="teamhome-roster-cell">{r.regionalTitles}</div>
                <div className="teamhome-roster-cell">{r.playoffAppearances}</div>
                <div className="teamhome-roster-cell">{r.stateRunnerUps}</div>
                <div className="teamhome-roster-cell">{r.stateChampionships}</div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
