import { useMemo, useState } from 'react'
import TeamLogo from './TeamLogo'
import {
  awardsFromSeasonEntry,
  listAwardClasses,
  sortAllStateEntries,
  statLineForEntry,
  type AllStatePlayerEntry,
  type SeasonAwards,
} from './allStateAwardsView'

type Props = {
  awards?: SeasonAwards | null
  seasonEntry?: unknown
  userTeam?: string
  apiBase: string
  headers: Record<string, string>
  logoVersion: number
  defaultClass?: string
  compact?: boolean
}

function tierLabel(tier: 'first_team' | 'second_team' | 'honorable_mention'): string {
  if (tier === 'first_team') return 'All-State 1st Team'
  if (tier === 'second_team') return 'All-State 2nd Team'
  return 'All-State Honorable Mention'
}

function AwardsTable({
  entries,
  userTeam,
  apiBase,
  headers,
  logoVersion,
}: {
  entries: AllStatePlayerEntry[]
  userTeam: string
  apiBase: string
  headers: Record<string, string>
  logoVersion: number
}) {
  const sorted = sortAllStateEntries(entries)
  if (!sorted.length) {
    return <p className="teamhome-small">No selections for this tier.</p>
  }
  return (
    <div className="all-state-table" role="table">
      <div className="all-state-row all-state-row--head" role="row">
        <span role="columnheader">Pos</span>
        <span role="columnheader">Player</span>
        <span role="columnheader">Team</span>
        <span role="columnheader">Season line</span>
      </div>
      {sorted.map((e) => {
        const highlight = userTeam && e.team === userTeam
        return (
          <div
            key={`${e.position}-${e.name}-${e.team}`}
            className={`all-state-row${highlight ? ' all-state-row--user' : ''}`}
            role="row"
          >
            <span className="all-state-pos" role="cell">
              {e.position}
            </span>
            <span className="all-state-name" role="cell">
              {e.name}
            </span>
            <span className="all-state-team" role="cell">
              <TeamLogo apiBase={apiBase} headers={headers} teamName={e.team} logoVersion={logoVersion} size={20} />
              <span>{e.team}</span>
            </span>
            <span className="all-state-line teamhome-small" role="cell">
              {statLineForEntry(e)}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export default function AllStateAwardsSection({
  awards: awardsProp,
  seasonEntry,
  userTeam = '',
  apiBase,
  headers,
  logoVersion,
  defaultClass,
  compact = false,
}: Props) {
  const awards = awardsProp ?? awardsFromSeasonEntry(seasonEntry)
  const classes = useMemo(() => listAwardClasses(awards), [awards])
  const [activeClass, setActiveClass] = useState(defaultClass || classes[0] || '')
  const [tier, setTier] = useState<'first_team' | 'second_team' | 'honorable_mention'>('first_team')

  const effectiveClass = activeClass && classes.includes(activeClass) ? activeClass : classes[0] || ''
  const block = effectiveClass ? awards?.all_state_by_class?.[effectiveClass] : undefined
  const tierEntries = block?.[tier] ?? []

  if (!awards) return null

  const poy = awards.player_of_the_year
  const opoy = awards.offensive_player_of_the_year
  const dpoy = awards.defensive_player_of_the_year
  const hasHeadline = Boolean(poy?.name || opoy?.name || dpoy?.name)
  const hasAllState = classes.length > 0

  if (!hasHeadline && !hasAllState) return null

  return (
    <section className="season-summary-section all-state-awards" aria-labelledby="all-state-awards-head">
      <h2 id="all-state-awards-head" className="season-summary-section-title">
        State awards
      </h2>

      {hasHeadline ? (
        <div className={`season-summary-stats-grid${compact ? ' season-summary-stats-grid--compact' : ''}`}>
          {poy?.name ? (
            <div className="season-summary-stat-card season-summary-stat-card--highlight">
              <span className="season-summary-stat-label">Player of the Year</span>
              <span className="season-summary-stat-value season-summary-stat-value--text">
                {poy.name}
                {poy.classification ? ` (${poy.classification})` : ''} — {poy.team}
              </span>
            </div>
          ) : null}
          {opoy?.name ? (
            <div className="season-summary-stat-card">
              <span className="season-summary-stat-label">Offensive POY</span>
              <span className="season-summary-stat-value season-summary-stat-value--text">
                {opoy.name} — {opoy.team}
              </span>
            </div>
          ) : null}
          {dpoy?.name ? (
            <div className="season-summary-stat-card">
              <span className="season-summary-stat-label">Defensive POY</span>
              <span className="season-summary-stat-value season-summary-stat-value--text">
                {dpoy.name} — {dpoy.team}
              </span>
            </div>
          ) : null}
        </div>
      ) : null}

      {hasAllState ? (
        <>
          <div className="all-state-toolbar">
            {classes.length > 1 ? (
              <label className="teamhome-small">
                Class{' '}
                <select
                  className="teamhome-select"
                  value={effectiveClass}
                  onChange={(e) => setActiveClass(e.target.value)}
                >
                  {classes.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <span className="teamhome-small">{effectiveClass} All-State</span>
            )}
            <div className="all-state-tier-tabs" role="tablist">
              {(['first_team', 'second_team', 'honorable_mention'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  role="tab"
                  aria-selected={tier === t}
                  className={`all-state-tier-tab${tier === t ? ' all-state-tier-tab--active' : ''}`}
                  onClick={() => setTier(t)}
                >
                  {tierLabel(t).replace('All-State ', '')}
                </button>
              ))}
            </div>
          </div>
          <h3 className="all-state-tier-title">{tierLabel(tier)} — {effectiveClass}</h3>
          <AwardsTable
            entries={tierEntries}
            userTeam={userTeam}
            apiBase={apiBase}
            headers={headers}
            logoVersion={logoVersion}
          />
        </>
      ) : null}
    </section>
  )
}
