import { useCallback, useEffect, useMemo, useState } from 'react'
import SchedulePlanningPanel from './SchedulePlanningPanel'
import {
  allSlotsFilled,
  buildCrossRegionPicksPayload,
  type CrossRegionSelections,
  emptySlotSelection,
  type SchedulePlanningInfo,
  schedulePlanningInfoFromState,
} from './schedulePlanningData'
import { saveCommishCrossRegionPicks, type CommishCrossRegionPlanningData } from './multiplayer'
import './CommishCrossRegionPlanning.css'

type TeamRow = CommishCrossRegionPlanningData['teams'][number]

function selectionsFromRow(row: TeamRow): CrossRegionSelections {
  const info = schedulePlanningInfoFromState({ schedule_planning_info: row.schedule_planning_info })
  if (!info) return {}
  const out: CrossRegionSelections = {}
  for (const slot of info.slots) {
    const saved = row.selections.find((s) => s.slot_index === slot.slot_index)
    if (saved?.opponent) {
      out[slot.slot_index] = {
        opponent: saved.opponent,
        userHome: saved.user_home != null ? Boolean(saved.user_home) : slot.slot_index % 2 === 0,
      }
    } else {
      out[slot.slot_index] = emptySlotSelection(slot.slot_index)
    }
  }
  return out
}

type Props = {
  apiBase: string
  headers: Record<string, string>
  leagueId: string
  planning: CommishCrossRegionPlanningData
  logoVersion?: number
  onPlanningChange?: (next: CommishCrossRegionPlanningData) => void
  compact?: boolean
}

export default function CommishCrossRegionPlanning({
  apiBase,
  headers,
  leagueId,
  planning,
  logoVersion = 0,
  onPlanningChange,
  compact = false,
}: Props) {
  const [selectionsByTeam, setSelectionsByTeam] = useState<Record<string, CrossRegionSelections>>({})
  const [savingTeam, setSavingTeam] = useState<string | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const next: Record<string, CrossRegionSelections> = {}
    for (const row of planning.teams) {
      next[row.team_name] = selectionsFromRow(row)
    }
    setSelectionsByTeam(next)
  }, [planning])

  const teamInfos = useMemo(() => {
    const map = new Map<string, SchedulePlanningInfo | null>()
    for (const row of planning.teams) {
      map.set(row.team_name, schedulePlanningInfoFromState({ schedule_planning_info: row.schedule_planning_info }))
    }
    return map
  }, [planning.teams])

  const saveTeam = useCallback(
    async (teamName: string) => {
      const info = teamInfos.get(teamName)
      const selections = selectionsByTeam[teamName]
      if (!info || !selections) return
      if (!allSlotsFilled(info, selections)) {
        setError(`Complete every out-of-region slot for ${teamName} before saving.`)
        return
      }
      setSavingTeam(teamName)
      setError('')
      try {
        const res = await saveCommishCrossRegionPicks(
          apiBase,
          headers,
          leagueId,
          teamName,
          buildCrossRegionPicksPayload(info, selections),
        )
        if (res.cross_region_planning) onPlanningChange?.(res.cross_region_planning)
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Could not save schedule')
      } finally {
        setSavingTeam(null)
      }
    },
    [apiBase, headers, leagueId, onPlanningChange, selectionsByTeam, teamInfos],
  )

  if (!planning.active || planning.teams.length === 0) return null

  return (
    <div className={`ccrp${compact ? ' ccrp--compact' : ''}`}>
      <div className="ccrp-head">
        <h2 className="ccrp-title">Out-of-region schedules — human schools</h2>
        <p className="ccrp-sub">
          Set non-region opponents for each human team for {planning.season_year}. CPU schools are filled
          automatically when you advance. Match opponents correctly so human coaches face the schools you
          intend.
        </p>
        <div className="ccrp-status-row">
          <span className={`ccrp-status-pill${planning.all_complete ? ' ccrp-status-pill--done' : ''}`}>
            {planning.all_complete
              ? 'All human schools ready — you can Sim week'
              : `${planning.teams.filter((t) => t.picks_complete).length}/${planning.teams.length} schools saved`}
          </span>
          {planning.missing_teams.length > 0 ? (
            <span className="ccrp-missing">Still need picks: {planning.missing_teams.join(', ')}</span>
          ) : null}
        </div>
      </div>

      {error ? <div className="fnd-error ccrp-error">{error}</div> : null}

      <div className="ccrp-team-list">
        {planning.teams.map((row) => {
          const info = teamInfos.get(row.team_name)
          const selections = selectionsByTeam[row.team_name] ?? {}
          const ready = info ? allSlotsFilled(info, selections) : false
          const saved = row.picks_complete
          return (
            <section key={row.team_name} className="ccrp-team-card">
              <div className="ccrp-team-card-head">
                <div>
                  <h3 className="ccrp-team-name">{row.team_name}</h3>
                  <div className="ccrp-team-meta">
                    {saved ? (
                      <span className="ccrp-tag ccrp-tag--saved">Saved on league file</span>
                    ) : ready ? (
                      <span className="ccrp-tag ccrp-tag--ready">Ready to save</span>
                    ) : (
                      <span className="ccrp-tag">Needs opponents</span>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  className="ccrp-save-btn"
                  disabled={!ready || savingTeam === row.team_name}
                  onClick={() => void saveTeam(row.team_name)}
                >
                  {savingTeam === row.team_name ? 'Saving…' : saved && ready ? 'Update' : 'Save'}
                </button>
              </div>
              {info ? (
                <SchedulePlanningPanel
                  apiBase={apiBase}
                  headers={headers}
                  logoVersion={logoVersion}
                  userTeam={row.team_name}
                  seasonYear={planning.season_year}
                  info={info}
                  selections={selections}
                  onSelectionsChange={(next) =>
                    setSelectionsByTeam((prev) => ({ ...prev, [row.team_name]: next }))
                  }
                />
              ) : null}
            </section>
          )
        })}
      </div>
    </div>
  )
}
