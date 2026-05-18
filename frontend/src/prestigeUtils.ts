/** Team Points / prestige helpers (mirrors systems/prestige_system.py). */

export const PRESTIGE_FLOORS = [
  0.0, 1.0, 1.7, 2.5, 3.4, 4.4, 5.5, 6.7, 8.0, 9.4, 10.9, 12.5, 14.2, 16.0, 17.9,
] as const

export function formatTeamPoints(tp: number | null | undefined): string {
  const n = Number(tp)
  if (!Number.isFinite(n)) return '—'
  return n.toFixed(2)
}

export function formatTeamPointsDelta(delta: number | null | undefined): string {
  const n = Number(delta)
  if (!Number.isFinite(n)) return '—'
  if (n > 0) return `+${n.toFixed(2)}`
  if (n < 0) return n.toFixed(2)
  return '0.00'
}

export function prestigeFromTeamPoints(tp: number): number {
  const value = Math.max(0, Number(tp) || 0)
  let level = 1
  for (let idx = PRESTIGE_FLOORS.length - 1; idx >= 0; idx--) {
    if (value >= PRESTIGE_FLOORS[idx]) {
      level = idx + 1
      break
    }
  }
  return Math.max(1, Math.min(15, level))
}

export function prestigeBandLabel(prestige: number): string {
  const p = Math.max(1, Math.min(15, Math.floor(prestige)))
  const lo = PRESTIGE_FLOORS[p - 1]
  const hi = p >= 15 ? null : PRESTIGE_FLOORS[p]
  if (hi == null) return `${formatTeamPoints(lo)}+ TP`
  return `${formatTeamPoints(lo)} – ${formatTeamPoints(hi)} TP`
}

export type PrestigeReportRow = {
  team: string
  prestige: number
  teamPoints: number
  lastDelta: number
}

export function buildPrestigeReportRows(teams: unknown[], highlightTeam?: string): PrestigeReportRow[] {
  const rows: PrestigeReportRow[] = []
  if (!Array.isArray(teams)) return rows
  for (const raw of teams) {
    if (!raw || typeof raw !== 'object') continue
    const t = raw as Record<string, unknown>
    const name = String(t.name ?? '').trim()
    if (!name) continue
    const tpRaw = t.team_points
    const tp =
      tpRaw != null && Number.isFinite(Number(tpRaw))
        ? Number(tpRaw)
        : null
    const prestige =
      tp != null ? prestigeFromTeamPoints(tp) : Math.max(1, Math.min(15, Number(t.prestige ?? 5) || 5))
    const teamPoints = tp != null ? tp : NaN
    const lastDelta = Number(t.team_points_last_delta ?? 0) || 0
    rows.push({
      team: name,
      prestige,
      teamPoints: Number.isFinite(teamPoints) ? teamPoints : 0,
      lastDelta,
    })
  }
  rows.sort((a, b) => b.teamPoints - a.teamPoints || a.team.localeCompare(b.team))
  if (highlightTeam) {
    const hi = highlightTeam.trim()
    const idx = rows.findIndex((r) => r.team === hi)
    if (idx > 0) {
      const [row] = rows.splice(idx, 1)
      rows.unshift(row)
    }
  }
  return rows
}
