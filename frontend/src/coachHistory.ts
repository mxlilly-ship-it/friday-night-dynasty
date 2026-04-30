export type CoachHistoryRow = {
  year: number | string | null | undefined
  team: string
  wins: number
  losses: number
  postseason: string
  coach: string
  has_recap: boolean
}

function postseasonLabelForTeam(teamName: string, season: any): string {
  if (teamName === season?.state_champion) return 'State Champion'
  if (teamName === season?.runner_up) return 'Runner-up'
  const playoffs = season?.playoffs && typeof season.playoffs === 'object' ? season.playoffs : {}
  const br = Array.isArray(playoffs?.bracket_results) ? playoffs.bracket_results : []
  const order: Record<string, number> = { Quarterfinal: 1, Semifinal: 2, Championship: 3 }
  let best: number | null = null
  for (const g of br) {
    if (!g || typeof g !== 'object') continue
    if (g.home !== teamName && g.away !== teamName) continue
    const rnd = String(g.round ?? '')
    const v = order[rnd]
    if (v != null && (best == null || v > best)) best = v
  }
  if (best === 2) return 'Semifinalist'
  if (best === 1) return 'Quarterfinalist'
  return '—'
}

function normCoach(s: string | null | undefined): string {
  return String(s ?? '')
    .trim()
    .toLowerCase()
}

/** Build coach history rows from bundled or in-memory league_history.json (same rules as server get_coach_history). */
export function buildCoachHistoryFromLeagueHistory(leagueHistory: any, coachName: string): CoachHistoryRow[] {
  const target = normCoach(coachName)
  if (!target) return []
  const seasons = Array.isArray(leagueHistory?.seasons) ? leagueHistory.seasons : []
  const rows: CoachHistoryRow[] = []
  for (const s of seasons) {
    if (!s || typeof s !== 'object') continue
    const year = s.year
    const standingsList = Array.isArray(s.standings) ? s.standings : []
    const recaps = s.team_recaps && typeof s.team_recaps === 'object' ? s.team_recaps : {}
    for (const stRow of standingsList) {
      if (!stRow || typeof stRow !== 'object') continue
      const c = stRow.coach
      if (typeof c !== 'string' || normCoach(c) !== target) continue
      const team = String(stRow.team ?? '').trim()
      if (!team) continue
      const rel = recaps[team]
      rows.push({
        year,
        team,
        wins: Number(stRow.wins ?? 0),
        losses: Number(stRow.losses ?? 0),
        postseason: postseasonLabelForTeam(team, s),
        coach: c.trim() || '—',
        has_recap: typeof rel === 'string' && rel.length > 0,
      })
    }
  }
  rows.sort((a, b) => Number(b.year ?? 0) - Number(a.year ?? 0))
  return rows
}

export type CoachCareerTotals = {
  seasons: number
  totalWins: number
  totalLosses: number
  stateChampionships: number
  runnerUps: number
}

export function aggregateCoachCareer(rows: CoachHistoryRow[]): CoachCareerTotals {
  let totalWins = 0
  let totalLosses = 0
  let stateChampionships = 0
  let runnerUps = 0
  for (const r of rows) {
    totalWins += Number(r.wins ?? 0)
    totalLosses += Number(r.losses ?? 0)
    if (r.postseason === 'State Champion') stateChampionships += 1
    if (r.postseason === 'Runner-up') runnerUps += 1
  }
  return {
    seasons: rows.length,
    totalWins,
    totalLosses,
    stateChampionships,
    runnerUps,
  }
}

/** Best-effort: find recap text in a local zip bundle map (path -> text). */
export function findLocalSeasonRecap(
  seasonRecaps: Record<string, string> | undefined,
  teamName: string,
  year: number | string,
): string | null {
  if (!seasonRecaps || !teamName) return null
  const y = String(year)
  const slug = teamName.replaceAll(' ', '_')
  for (const [path, text] of Object.entries(seasonRecaps)) {
    const low = path.toLowerCase()
    if (!low.endsWith('.txt')) continue
    if (low.includes(slug.toLowerCase()) && path.includes(y)) return text
  }
  for (const [, text] of Object.entries(seasonRecaps)) {
    if (text.includes(teamName) && text.includes(`Year ${y}`)) return text
  }
  return null
}
