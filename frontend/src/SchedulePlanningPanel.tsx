import { useMemo, useState } from 'react'
import TeamLogo from './TeamLogo'
import type { CrossRegionSelections, SchedulePlanningInfo } from './schedulePlanningData'
import { defaultUserHomeForSlot, emptySlotSelection } from './schedulePlanningData'
import './SchedulePlanningPanel.css'

type Props = {
  apiBase: string
  headers: Record<string, string>
  logoVersion: number
  userTeam: string
  seasonYear: number
  info: SchedulePlanningInfo
  selections: CrossRegionSelections
  onSelectionsChange: (next: CrossRegionSelections) => void
}

export default function SchedulePlanningPanel({
  apiBase,
  headers,
  logoVersion,
  userTeam,
  seasonYear,
  info,
  selections,
  onSelectionsChange,
}: Props) {
  const [filter, setFilter] = useState('')

  const summaryLine = useMemo(() => {
    const parts = [`${info.in_region_games} region games locked in`]
    if (info.slot_count === 1) parts.push('1 out-of-region game to choose')
    else parts.push(`${info.slot_count} out-of-region games to choose`)
    return parts.join(' · ')
  }, [info])

  const setOpponent = (slotIndex: number, opponent: string) => {
    const prev = selections[slotIndex] ?? emptySlotSelection(slotIndex)
    onSelectionsChange({
      ...selections,
      [slotIndex]: {
        opponent,
        userHome: prev.userHome ?? defaultUserHomeForSlot(slotIndex),
      },
    })
  }

  const setUserHome = (slotIndex: number, userHome: boolean) => {
    const prev = selections[slotIndex] ?? emptySlotSelection(slotIndex)
    onSelectionsChange({
      ...selections,
      [slotIndex]: { ...prev, userHome },
    })
  }

  return (
    <div className="schedplan" role="region" aria-label="Schedule planning">
      <div className="schedplan-header">
        <div className="schedplan-eyebrow">
          <span className="schedplan-dot" />
          Schedule planning · {seasonYear}
        </div>
        <h2 className="schedplan-title">Non-region selection — pick your opponents</h2>
        <p className="schedplan-sub">
          {userTeam} · {summaryLine}. Region matchups are set automatically; choose who you face from
          other regions in your class ({info.total_games} games total). For each out-of-region game, pick
          the opponent and whether you host or travel.
        </p>
      </div>

      <div className="schedplan-slots">
        {info.slots.map((slot) => {
          const sel = selections[slot.slot_index] ?? emptySlotSelection(slot.slot_index)
          const selected = sel.opponent
          const userHome = sel.userHome
          const q = filter.trim().toLowerCase()
          const eligible = slot.eligible_teams.filter((name) => !q || name.toLowerCase().includes(q))
          return (
            <section key={slot.slot_index} className="schedplan-slot">
              <div className="schedplan-slot-head">
                <span className="schedplan-slot-num">Game {slot.slot_index + 1}</span>
                <span className="schedplan-slot-label">{slot.label}</span>
              </div>
              <div className="schedplan-picker-row">
                <label className="schedplan-select-wrap">
                  <span className="schedplan-select-label">Opponent</span>
                  <select
                    className="schedplan-select"
                    value={selected}
                    onChange={(e) => setOpponent(slot.slot_index, e.target.value)}
                  >
                    <option value="">— Select school —</option>
                    {eligible.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                </label>
                {selected ? (
                  <div className="schedplan-ha-wrap">
                    <span className="schedplan-select-label">Site</span>
                    <div className="schedplan-ha-toggle" role="group" aria-label="Home or away">
                      <button
                        type="button"
                        className={`schedplan-ha-btn${userHome ? ' schedplan-ha-btn--active' : ''}`}
                        aria-pressed={userHome}
                        onClick={() => setUserHome(slot.slot_index, true)}
                      >
                        Home
                      </button>
                      <button
                        type="button"
                        className={`schedplan-ha-btn${!userHome ? ' schedplan-ha-btn--active' : ''}`}
                        aria-pressed={!userHome}
                        onClick={() => setUserHome(slot.slot_index, false)}
                      >
                        Away
                      </button>
                    </div>
                  </div>
                ) : null}
                {selected ? (
                  <div className="schedplan-preview">
                    <TeamLogo
                      apiBase={apiBase}
                      headers={headers}
                      teamName={selected}
                      logoVersion={logoVersion}
                      size={36}
                    />
                    <span className="schedplan-preview-name">
                      {userHome ? `vs ${selected}` : `@ ${selected}`}
                    </span>
                  </div>
                ) : null}
              </div>
            </section>
          )
        })}
      </div>

      {info.slots.some((s) => s.eligible_teams.length > 8) ? (
        <div className="schedplan-filter">
          <label className="schedplan-select-label" htmlFor="schedplan-filter-input">
            Filter schools
          </label>
          <input
            id="schedplan-filter-input"
            className="schedplan-filter-input"
            type="search"
            placeholder="Type to narrow list…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
      ) : null}
    </div>
  )
}
