import { useMemo, useState, type ReactNode } from 'react'
import TeamLogo from './TeamLogo'
import { filterTeamRatingsByClass, type TeamRatingRow } from './teamRatings'
import './TeamRatingsPage.css'

type SortKey = keyof Pick<
  TeamRatingRow,
  | 'teamName'
  | 'classification'
  | 'wins'
  | 'losses'
  | 'overall'
  | 'offense'
  | 'defense'
  | 'run'
  | 'pass'
>

type Props = {
  rows: TeamRatingRow[]
  loading: boolean
  classFilter: string | 'all'
  classFilterBar: ReactNode
  apiBase: string
  headers: Record<string, string>
  logoVersion: number
  userTeam?: string
}

export default function TeamRatingsPage({
  rows,
  loading,
  classFilter,
  classFilterBar,
  apiBase,
  headers,
  logoVersion,
  userTeam,
}: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('overall')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  const filtered = useMemo(() => filterTeamRatingsByClass(rows, classFilter), [rows, classFilter])

  const sortedRows = useMemo(() => {
    const arr = [...filtered]
    arr.sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      if (typeof av === 'string' && typeof bv === 'string') {
        const cmp = av.localeCompare(bv, undefined, { numeric: true })
        return sortDir === 'asc' ? cmp : -cmp
      }
      const an = Number(av)
      const bn = Number(bv)
      return sortDir === 'asc' ? an - bn : bn - an
    })
    return arr.map((r, idx) => ({ ...r, displayRank: idx + 1 }))
  }, [filtered, sortDir, sortKey])

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir(key === 'teamName' || key === 'classification' ? 'asc' : 'desc')
    }
  }

  const teamWithLogo = (name: string) => (
    <span className="teamhome-name-with-logo">
      <TeamLogo apiBase={apiBase} teamName={name} logoVersion={logoVersion} headers={headers} size={20} />
      <span>{name}</span>
    </span>
  )

  return (
    <div className="teamhome-roster-shell team-ratings-page">
      <div className="teamhome-teaminfo-header">
        <div className="teamhome-card-title" style={{ marginBottom: 0 }}>
          Team Ratings
        </div>
        <div className="teamhome-small" style={{ marginTop: 8, opacity: 0.9, maxWidth: 640, lineHeight: 1.45 }}>
          Roster talent ratings used by the game engine (starter-weighted, prestige-adjusted). Filter by class below or click
          a column header to sort.
        </div>
      </div>

      {classFilterBar}

      <div className="teamhome-roster-head" style={{ marginTop: 12 }}>
        Click a column to sort
      </div>

      <div className="teamhome-roster-table">
        <div className="team-ratings-row team-ratings-row-head">
          <div className="teamhome-roster-cell">#</div>
          <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleSort('teamName')}>
            Team
          </button>
          <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleSort('classification')}>
            Class
          </button>
          <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleSort('wins')}>
            W
          </button>
          <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleSort('losses')}>
            L
          </button>
          <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleSort('overall')}>
            OVR
          </button>
          <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleSort('offense')}>
            OFF
          </button>
          <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleSort('defense')}>
            DEF
          </button>
          <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleSort('run')}>
            RUN
          </button>
          <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleSort('pass')}>
            PASS
          </button>
        </div>

        {loading ? (
          <div className="teamhome-roster-empty">Loading team ratings…</div>
        ) : sortedRows.length === 0 ? (
          <div className="teamhome-roster-empty">No team ratings available.</div>
        ) : (
          sortedRows.map((r) => {
            const isUser = userTeam && r.teamName === userTeam
            return (
              <div key={r.teamName} className={`team-ratings-row${isUser ? ' team-ratings-row--user' : ''}`}>
                <div className="teamhome-roster-cell">{r.displayRank}</div>
                <div className="teamhome-roster-name">{teamWithLogo(r.teamName)}</div>
                <div className="teamhome-roster-cell">{r.classification}</div>
                <div className="teamhome-roster-cell">{r.wins}</div>
                <div className="teamhome-roster-cell">{r.losses}</div>
                <div className="teamhome-roster-cell team-ratings-ovr">{r.overall}</div>
                <div className="teamhome-roster-cell">{r.offense}</div>
                <div className="teamhome-roster-cell">{r.defense}</div>
                <div className="teamhome-roster-cell">{r.run}</div>
                <div className="teamhome-roster-cell">{r.pass}</div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
