import type { ReactNode } from 'react'
import TeamLogo from './TeamLogo'
import { evaluateSeasonGoals, postseasonTierForTeam } from './seasonSummaryGoals'
import { formatTeamPoints, formatTeamPointsDelta } from './prestigeUtils'
import { findSeasonEntryByCalendarYear } from './leagueHistoryView'

export type SeasonSummaryStandingsRow = {
  rank: number
  teamName: string
  wins: number
  losses: number
  pointsFor: number
  pointsAgainst: number
}

type Props = {
  apiBase: string
  headers: Record<string, string>
  logoVersion: number
  saveState: any
  userTeam: string
  leagueHistory?: { seasons?: unknown[] } | null
  seasonYear: number
  playoffView: {
    missingBracket?: boolean
    viewClass?: string | null
    completed?: boolean
    champion?: string
  }
  standingsRows: SeasonSummaryStandingsRow[]
  bracketSlot: ReactNode
  /** Class / region selectors (same as live playoffs when multiple brackets exist). */
  bracketToolbar?: ReactNode
  onOpenLeagueHistory: () => void
  onOpenTeamHistory: () => void
  teamWithLogo: (name: string, size?: number, opts?: { playoffSeed?: number | null }) => ReactNode
}

function goalStatusPill(met: boolean | null): { label: string; className: string } {
  if (met === true) return { label: 'Met', className: 'season-summary-goal-pill season-summary-goal-pill--met' }
  if (met === false) return { label: 'Missed', className: 'season-summary-goal-pill season-summary-goal-pill--miss' }
  return { label: '—', className: 'season-summary-goal-pill' }
}

export default function SeasonSummaryPanel({
  apiBase,
  headers,
  logoVersion,
  saveState,
  userTeam,
  leagueHistory,
  seasonYear,
  playoffView,
  standingsRows,
  bracketSlot,
  bracketToolbar,
  onOpenLeagueHistory,
  onOpenTeamHistory,
  teamWithLogo,
}: Props) {
  const ut = String(userTeam || saveState?.user_team || '').trim()
  const seasons = Array.isArray(leagueHistory?.seasons) ? leagueHistory.seasons : []
  const archived = findSeasonEntryByCalendarYear(seasons, seasonYear)

  const st = ut ? (saveState?.standings?.[ut] as { wins?: number; losses?: number } | undefined) : null
  const wins = st != null ? Number(st.wins ?? 0) : 0
  const losses = st != null ? Number(st.losses ?? 0) : 0

  const champ =
    String(archived?.state_champion ?? saveState?.playoffs?.champion ?? playoffView.champion ?? '—') || '—'
  const runner = String(archived?.runner_up ?? saveState?.playoffs?.runner_up ?? '—') || '—'

  const brFlat: Array<{ round?: string; home?: string; away?: string }> = []
  const pbc = archived?.playoffs_by_class as Record<string, { bracket_results?: unknown[] }> | undefined
  if (pbc && typeof pbc === 'object' && playoffView.viewClass) {
    const inner = pbc[playoffView.viewClass]
    if (inner && Array.isArray(inner.bracket_results)) {
      brFlat.push(...(inner.bracket_results as Array<{ round?: string; home?: string; away?: string }>))
    }
  }
  if (!brFlat.length) {
    const legacy = (archived?.playoffs as { bracket_results?: unknown[] } | undefined)?.bracket_results
    if (Array.isArray(legacy)) {
      brFlat.push(...(legacy as Array<{ round?: string; home?: string; away?: string }>))
    } else {
      const flat = saveState?.playoffs?.bracket_results
      if (Array.isArray(flat)) brFlat.push(...flat)
    }
  }

  const goals = saveState?.season_goals as { win_goal?: number; stage_goal?: string } | undefined
  const tier = postseasonTierForTeam(ut, brFlat, champ)
  const goalEval = evaluateSeasonGoals(wins, losses, goals, tier)
  const winPill = goalStatusPill(goalEval.winMet)
  const stagePill = goalStatusPill(goalEval.stageMet)

  const teamRow = (saveState?.teams ?? []).find((t: { name?: string }) => t?.name === ut)
  const tpDelta = formatTeamPointsDelta(Number(teamRow?.team_points_last_delta ?? 0))
  const tp = teamRow?.team_points != null ? formatTeamPoints(Number(teamRow.team_points)) : '—'
  const prestigeStars = teamRow?.prestige != null ? String(teamRow.prestige) : '—'

  const userWonState = ut && champ === ut
  const userWasRunnerUp = ut && runner === ut
  const regionalChamps = Array.isArray(archived?.regional_champions)
    ? (archived.regional_champions as string[]).filter(Boolean)
    : []

  const heroSubtitle = userWonState
    ? 'You brought home the state title.'
    : userWasRunnerUp
      ? 'Runner-up finish — one game from the crown.'
      : goalEval.postseasonTier === 'semifinal' || goalEval.postseasonTier === 'championship'
        ? 'Deep playoff run — building momentum for next year.'
        : goalEval.postseasonTier === 'playoffs'
          ? 'Postseason appearance — program on the rise.'
          : 'Season archived — review the year and plan the offseason.'

  return (
    <div className="teamhome-roster-shell season-summary-hub" role="region" aria-label="Season summary">
      <header className="season-summary-hero">
        <div className="season-summary-hero-text">
          <p className="season-summary-eyebrow">Year complete</p>
          <h1 className="season-summary-title">
            {Number.isFinite(seasonYear) ? seasonYear : '—'} Season Summary
          </h1>
          <p className="season-summary-subtitle">{heroSubtitle}</p>
        </div>
        {ut ? (
          <div className="season-summary-hero-team" aria-hidden>
            <TeamLogo apiBase={apiBase} headers={headers} teamName={ut} logoVersion={logoVersion} size={72} />
            <div className="season-summary-hero-record">
              <span className="season-summary-hero-wl">
                {wins}-{losses}
              </span>
              <span className="season-summary-hero-team-name">{ut}</span>
            </div>
          </div>
        ) : null}
      </header>

      <p className="teamhome-small season-summary-lead">
        Standings and brackets are saved to league history. When you&apos;re ready, use{' '}
        <strong>Begin offseason</strong> (top right) for Graduation and the rest of the offseason hub.
      </p>

      <div className="season-summary-stats-grid">
        <div className="season-summary-stat-card season-summary-stat-card--highlight">
          <span className="season-summary-stat-label">State champion</span>
          <span className="season-summary-stat-value">{teamWithLogo(champ, 28)}</span>
        </div>
        <div className="season-summary-stat-card">
          <span className="season-summary-stat-label">Runner-up</span>
          <span className="season-summary-stat-value">{teamWithLogo(runner, 28)}</span>
        </div>
        <div className="season-summary-stat-card">
          <span className="season-summary-stat-label">Your postseason</span>
          <span className="season-summary-stat-value season-summary-stat-value--text">{goalEval.postseasonLabel}</span>
        </div>
        <div className="season-summary-stat-card">
          <span className="season-summary-stat-label">Prestige · TP</span>
          <span className="season-summary-stat-value season-summary-stat-value--text">
            {prestigeStars}★ · {tp}
            <span className="season-summary-tp-delta"> (Δ {tpDelta})</span>
          </span>
        </div>
      </div>

      {(goalEval.winGoal != null || goalEval.stageGoal) ? (
        <section className="season-summary-section season-summary-goals" aria-labelledby="season-summary-goals-head">
          <h2 id="season-summary-goals-head" className="season-summary-section-title">
            Season goals
          </h2>
          <div className="season-summary-goals-grid">
            {goalEval.winGoal != null ? (
              <div className="season-summary-goal-card">
                <div className="season-summary-goal-head">
                  <span className="season-summary-goal-type">Win total</span>
                  <span className={winPill.className}>{winPill.label}</span>
                </div>
                <p className="season-summary-goal-detail">
                  Target <strong>{goalEval.winGoal}</strong> wins · Finished <strong>{wins}-{losses}</strong>
                </p>
              </div>
            ) : null}
            {goalEval.stageGoal ? (
              <div className="season-summary-goal-card">
                <div className="season-summary-goal-head">
                  <span className="season-summary-goal-type">{goalEval.stageGoal}</span>
                  <span className={stagePill.className}>{stagePill.label}</span>
                </div>
                <p className="season-summary-goal-detail">
                  Reached <strong>{goalEval.postseasonLabel}</strong>
                </p>
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      {!playoffView.missingBracket ? (
        <section className="season-summary-section" aria-labelledby="season-summary-bracket-head">
          <div className="season-summary-bracket-head-row">
            <h2 id="season-summary-bracket-head" className="season-summary-section-title">
              Playoff bracket
              {playoffView.viewClass ? (
                <span className="season-summary-bracket-class"> · Class {playoffView.viewClass}</span>
              ) : null}
            </h2>
            {bracketToolbar ? <div className="season-summary-bracket-toolbar">{bracketToolbar}</div> : null}
          </div>
          <div className="season-summary-bracket-wrap">{bracketSlot}</div>
        </section>
      ) : playoffView.missingBracket && bracketToolbar ? (
        <section className="season-summary-section" aria-labelledby="season-summary-bracket-head">
          <div className="season-summary-bracket-head-row">
            <h2 id="season-summary-bracket-head" className="season-summary-section-title">
              Playoff bracket
            </h2>
            <div className="season-summary-bracket-toolbar">{bracketToolbar}</div>
          </div>
          <p className="teamhome-small" style={{ opacity: 0.88 }}>
            No bracket saved for this classification. Try another class from the menu above.
          </p>
        </section>
      ) : null}

      <div className="season-summary-two-col">
        {standingsRows.length > 0 ? (
          <section className="season-summary-section season-summary-standings" aria-labelledby="season-summary-standings-head">
            <h2 id="season-summary-standings-head" className="season-summary-section-title">
              Final standings
              {playoffView.viewClass ? ` · ${playoffView.viewClass}` : ''}
            </h2>
            <div className="teamhome-card season-summary-standings-card">
              <div className="teamhome-roster-head teamhome-standings-row season-summary-standings-head">
                <div className="teamhome-roster-cell">Rk</div>
                <div className="teamhome-roster-name">Team</div>
                <div className="teamhome-roster-cell">WL</div>
                <div className="teamhome-roster-cell">PF</div>
                <div className="teamhome-roster-cell">PA</div>
              </div>
              <div className="teamhome-roster-table">
                {standingsRows.map((r) => (
                  <div
                    key={r.teamName}
                    className={`teamhome-standings-row${r.teamName === ut ? ' season-summary-standings-row--user' : ''}`}
                  >
                    <div className="teamhome-roster-cell">{r.rank}</div>
                    <div className="teamhome-roster-name">{teamWithLogo(r.teamName)}</div>
                    <div className="teamhome-roster-cell">
                      {r.wins}-{r.losses}
                    </div>
                    <div className="teamhome-roster-cell">{r.pointsFor}</div>
                    <div className="teamhome-roster-cell">{r.pointsAgainst}</div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        ) : null}

        {regionalChamps.length > 0 ? (
          <section className="season-summary-section" aria-labelledby="season-summary-regional-head">
            <h2 id="season-summary-regional-head" className="season-summary-section-title">
              Regional champions
            </h2>
            <ul className="season-summary-regional-list">
              {regionalChamps.map((name) => (
                <li key={name} className="season-summary-regional-item">
                  {teamWithLogo(name, 24)}
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>

      <div className="season-summary-actions">
        <button type="button" className="teamhome-select season-summary-action-btn" onClick={onOpenLeagueHistory}>
          League history
        </button>
        <button type="button" className="teamhome-select season-summary-action-btn" onClick={onOpenTeamHistory}>
          Team history &amp; recap
        </button>
      </div>
    </div>
  )
}
