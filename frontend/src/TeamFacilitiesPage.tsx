import { useMemo } from 'react'
import catalogJson from './programEquipmentCatalog.json'
import TeamLogo from './TeamLogo'
import {
  buildTeamEquipmentRows,
  fmtProgramDollars,
  parsePpFromAttributeLines,
  type ProgramEquipmentCatalog,
  type ProgramInventoryRow,
} from './programDevelopmentUtils'
import './TeamFacilitiesPage.css'

const CATALOG = catalogJson as ProgramEquipmentCatalog

type Props = {
  apiBase: string
  headers: Record<string, string>
  saveState: any
  userTeam: string
  allTeamNames: string[]
  viewTeam: string
  onViewTeamChange: (name: string) => void
}

function findTeam(saveState: any, name: string) {
  return (saveState?.teams as any[] | undefined)?.find((t) => t?.name === name)
}

export default function TeamFacilitiesPage({
  apiBase,
  headers,
  saveState,
  userTeam,
  allTeamNames,
  viewTeam,
  onViewTeamChange,
}: Props) {
  const team = findTeam(saveState, viewTeam)
  const equipment = useMemo(() => {
    const inv = (team?.program_equipment || []) as ProgramInventoryRow[]
    return buildTeamEquipmentRows(inv, CATALOG)
  }, [team?.program_equipment])

  const fundingBalance = Number(team?.program_funding_balance ?? 0)
  const facilitiesGrade = team?.facilities_grade != null ? String(team.facilities_grade) : '—'
  const boosterSupport = team?.booster_support != null ? String(team.booster_support) : '—'

  const grouped = useMemo(() => {
    const map = new Map<string, typeof equipment>()
    for (const row of equipment) {
      const cat = row.category || 'Other'
      if (!map.has(cat)) map.set(cat, [])
      map.get(cat)!.push(row)
    }
    return [...map.entries()]
  }, [equipment])

  return (
    <div className="teamhome-roster-shell team-facilities-shell">
      <div className="teamhome-teaminfo-header">
        <div className="teamhome-card-title" style={{ marginBottom: 0 }}>
          Facilities
        </div>
        <div className="teamhome-teaminfo-picker">
          <label className="teamhome-teaminfo-picker-label" htmlFor="facilities-team-select">
            View team
          </label>
          <select
            id="facilities-team-select"
            className="teamhome-select teamhome-teaminfo-select"
            value={viewTeam}
            onChange={(e) => onViewTeamChange(e.target.value)}
            disabled={allTeamNames.length < 1}
          >
            {allTeamNames.length < 1 ? (
              <option value="">—</option>
            ) : (
              allTeamNames.map((name) => (
                <option key={name} value={name}>
                  {name}
                  {name === userTeam ? ' (you)' : ''}
                </option>
              ))
            )}
          </select>
        </div>
      </div>

      <div className="team-facilities-summary">
        <div className="team-facilities-logo">
          <TeamLogo
            apiBase={apiBase}
            headers={headers}
            teamName={viewTeam}
            size={72}
            className="teamhome-teaminfo-biglogo"
          />
        </div>
        <div className="team-facilities-metrics">
          <div>
            <span className="teamhome-teaminfo-label">Program</span>
            <span className="team-facilities-metric-val">{viewTeam || '—'}</span>
          </div>
          <div>
            <span className="teamhome-teaminfo-label">Funding balance</span>
            <span className="team-facilities-metric-val">{fmtProgramDollars(fundingBalance)}</span>
          </div>
          <div>
            <span className="teamhome-teaminfo-label">Facilities grade</span>
            <span className="team-facilities-metric-val">{facilitiesGrade}/10</span>
          </div>
          <div>
            <span className="teamhome-teaminfo-label">Booster support</span>
            <span className="team-facilities-metric-val">{boosterSupport}/10</span>
          </div>
          <div>
            <span className="teamhome-teaminfo-label">Owned equipment</span>
            <span className="team-facilities-metric-val">{equipment.length}</span>
          </div>
        </div>
      </div>

      {equipment.length === 0 ? (
        <p className="team-facilities-empty">
          No program equipment on file for this team yet. Items purchased during offseason Program Development appear
          here.
        </p>
      ) : (
        <div className="team-facilities-groups">
          {grouped.map(([category, rows]) => (
            <section key={category} className="team-facilities-group">
              <h3 className="team-facilities-cat-head">{category}</h3>
              <div className="team-facilities-table-wrap">
                <table className="teamhome-roster-table team-facilities-table">
                  <thead>
                    <tr>
                      <th style={{ textAlign: 'left' }}>Item</th>
                      <th>Effects</th>
                      <th>Purchased</th>
                      <th>Condition</th>
                      <th>Renewal</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => {
                      const attrs = (row.attributes_affected || []).filter(Boolean)
                      const pp = parsePpFromAttributeLines(attrs)
                      const effectText =
                        attrs
                          .map((a) => a.replace(/\s*\d+\s*PP\s*Points?/gi, '').trim())
                          .filter(Boolean)
                          .join(' · ') || (pp > 0 ? `+${pp} PP / year` : '—')
                      const expiring = row.seasons_remaining <= 1
                      return (
                        <tr key={row.item_id} className={expiring ? 'team-facilities-row-expiring' : undefined}>
                          <td>
                            <div className="team-facilities-item-name">{row.name}</div>
                            <div className="team-facilities-item-cost">{fmtProgramDollars(row.cost)}</div>
                          </td>
                          <td className="team-facilities-effects">{effectText}</td>
                          <td>{row.purchased_year ?? '—'}</td>
                          <td>
                            <div className="team-facilities-dur">
                              <div className="team-facilities-dur-bar">
                                <div
                                  className={`team-facilities-dur-fill${
                                    row.durability_pct > 60 ? ' good' : row.durability_pct > 30 ? ' mid' : ' low'
                                  }`}
                                  style={{ width: `${row.durability_pct}%` }}
                                />
                              </div>
                              <span>
                                {row.seasons_remaining.toFixed(1)} yr left ({row.durability_pct}%)
                              </span>
                            </div>
                          </td>
                          <td>{fmtProgramDollars(row.renewal_cost)}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
