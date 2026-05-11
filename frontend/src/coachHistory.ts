export type CoachHistoryRow = {
  year: number | string | null | undefined
  team: string
  wins: number
  losses: number
  postseason: string
  coach: string
  has_recap: boolean
}

function resolvePlayoffsInnerForClassification(
  playoffsByClass: Record<string, unknown>,
  classification: string | null | undefined,
): Record<string, unknown> | null {
  const cls = String(classification ?? '').trim()
  if (!cls || !playoffsByClass || typeof playoffsByClass !== 'object') return null
  const direct = playoffsByClass[cls]
  if (direct && typeof direct === 'object') return direct as Record<string, unknown>
  const low = cls.toLowerCase()
  for (const [k, v] of Object.entries(playoffsByClass)) {
    if (String(k).trim().toLowerCase() === low && v && typeof v === 'object') return v as Record<string, unknown>
  }
  return null
}

export function classificationForTeamFromSave(teamName: string, saveTeams: unknown): string | null {
  const tn = String(teamName ?? '').trim()
  if (!tn || !Array.isArray(saveTeams)) return null
  for (const t of saveTeams) {
    if (!t || typeof t !== 'object') continue
    const nm = String((t as { name?: unknown }).name ?? '').trim()
    if (nm !== tn) continue
    const c = (t as { classification?: unknown }).classification
    const s = c != null ? String(c).trim() : ''
    return s || null
  }
  return null
}

/** Postseason chip from flat or per-class playoff object (games list + optional champion/runner_up). */
export function postseasonLabelFromBracket(teamName: string, inner: Record<string, unknown> | null | undefined): string {
  const t = String(teamName ?? '').trim()
  if (!t || !inner || typeof inner !== 'object') return '—'
  if (inner.champion === t) return 'State Champion'
  if (inner.runner_up === t) return 'Runner-up'
  const br = Array.isArray(inner.bracket_results) ? inner.bracket_results : []
  const order: Record<string, number> = { Quarterfinal: 1, Semifinal: 2, Championship: 3 }
  let best: number | null = null
  for (const g of br) {
    if (!g || typeof g !== 'object') continue
    if ((g as { home?: unknown }).home !== t && (g as { away?: unknown }).away !== t) continue
    const rnd = String((g as { round?: unknown }).round ?? '')
    const v = order[rnd]
    if (v != null && (best == null || v > best)) best = v
  }
  if (best === 2) return 'Semifinalist'
  if (best === 1) return 'Quarterfinalist'
  return '—'
}

function postseasonLabelForTeam(teamName: string, season: any, saveTeams?: unknown): string {
  const cls = classificationForTeamFromSave(teamName, saveTeams)
  const pbc = season?.playoffs_by_class
  let inner: Record<string, unknown> | null = null
  if (pbc && typeof pbc === 'object' && Object.keys(pbc as object).length > 0) {
    inner = resolvePlayoffsInnerForClassification(pbc as Record<string, unknown>, cls)
  }
  if (inner) return postseasonLabelFromBracket(teamName, inner)
  if (teamName === season?.state_champion) return 'State Champion'
  if (teamName === season?.runner_up) return 'Runner-up'
  const playoffs = season?.playoffs && typeof season.playoffs === 'object' ? season.playoffs : {}
  const br = Array.isArray(playoffs?.bracket_results) ? playoffs.bracket_results : []
  return postseasonLabelFromBracket(teamName, { bracket_results: br })
}

/** Active save `state.playoffs` postseason label for `teamName` (multiclass `by_class` or legacy flat). */
export function livePostseasonLabelForTeam(teamName: string, saveState: any): string {
  const p = saveState?.playoffs
  if (!p || typeof p !== 'object') return '—'
  const byClass = (p as { by_class?: unknown }).by_class
  const cls = classificationForTeamFromSave(teamName, saveState?.teams)
  let inner: Record<string, unknown> | null = null
  if (byClass && typeof byClass === 'object' && Object.keys(byClass as object).length > 0) {
    inner = resolvePlayoffsInnerForClassification(byClass as Record<string, unknown>, cls)
  }
  if (inner) return postseasonLabelFromBracket(teamName, inner)
  const flatBr = Array.isArray((p as { bracket_results?: unknown }).bracket_results)
    ? (p as { bracket_results: unknown[] }).bracket_results
    : []
  const bundle: Record<string, unknown> = {
    champion: (p as { champion?: unknown }).champion ?? null,
    runner_up: (p as { runner_up?: unknown }).runner_up ?? null,
    bracket_results: flatBr,
  }
  return postseasonLabelFromBracket(teamName, bundle)
}

function scanPlayoffsByClassForTeam(teamName: string, pbc: Record<string, unknown>): boolean {
  for (const inner of Object.values(pbc)) {
    if (!inner || typeof inner !== 'object') continue
    const inn = inner as { champion?: unknown; runner_up?: unknown; bracket_results?: unknown }
    if (inn.champion === teamName || inn.runner_up === teamName) return true
    const br = Array.isArray(inn.bracket_results) ? inn.bracket_results : []
    for (const g of br) {
      if (!g || typeof g !== 'object') continue
      if ((g as { home?: string }).home === teamName || (g as { away?: string }).away === teamName) return true
    }
  }
  return false
}

/** True if team won a state title in this season row (top-level or any multiclass bracket). */
export function teamWonStateInSeason(teamName: string, entry: any): boolean {
  if (!teamName || !entry || typeof entry !== 'object') return false
  if (String(entry.state_champion ?? '') === teamName) return true
  const pbc = entry.playoffs_by_class
  if (pbc && typeof pbc === 'object') {
    for (const inner of Object.values(pbc as Record<string, unknown>)) {
      if (inner && typeof inner === 'object' && (inner as { champion?: string }).champion === teamName) return true
    }
  }
  return false
}

/** True if team is in the current playoff bracket (multiclass or legacy). */
export function teamInActivePlayoffBracket(teamName: string, saveState: any): boolean {
  if (String(saveState?.season_phase ?? '').toLowerCase() !== 'playoffs') return false
  const p = saveState?.playoffs
  if (!p || typeof p !== 'object') return false
  const byClass = (p as { by_class?: unknown }).by_class
  if (byClass && typeof byClass === 'object' && Object.keys(byClass as object).length > 0) {
    for (const inner of Object.values(byClass as Record<string, unknown>)) {
      if (!inner || typeof inner !== 'object') continue
      const inn = inner as { seeds?: unknown }
      const seeds = Array.isArray(inn.seeds) ? inn.seeds : []
      for (const s of seeds) {
        if (s && typeof s === 'object' && (s as { team?: string }).team === teamName) return true
      }
    }
    return scanPlayoffsByClassForTeam(teamName, byClass as Record<string, unknown>)
  }
  const seeds = Array.isArray((p as { seeds?: unknown }).seeds) ? (p as { seeds: unknown[] }).seeds : []
  for (const s of seeds) {
    if (s && typeof s === 'object' && (s as { team?: string }).team === teamName) return true
  }
  const flatBr = Array.isArray((p as { bracket_results?: unknown }).bracket_results)
    ? (p as { bracket_results: unknown[] }).bracket_results
    : []
  for (const g of flatBr) {
    if (g && typeof g === 'object') {
      if ((g as { home?: string }).home === teamName || (g as { away?: string }).away === teamName) return true
    }
  }
  return false
}

/** Merge current (unfinished) season wins/losses and playoff credit into program totals for display.
 *
 * In offseason / preseason, ``standings`` are reset to 0-0 and the just-finished season is
 * already counted in ``base`` (from league_history). We still merge if standings happens to
 * carry non-zero data (mid-stage edge cases from older saves) — adding 0 is a no-op anyway.
 */
export function mergeInProgressTeamProgramTotals(
  base: TeamProgramTotalsDisplay,
  teamName: string,
  saveState: any,
): TeamProgramTotalsDisplay {
  const tn = String(teamName ?? '').trim()
  if (!tn) return base
  const st = saveState?.standings?.[tn]
  const w = st && typeof st === 'object' ? Number((st as { wins?: unknown }).wins ?? 0) || 0 : 0
  const l = st && typeof st === 'object' ? Number((st as { losses?: unknown }).losses ?? 0) || 0 : 0
  const phase = String(saveState?.season_phase ?? '').toLowerCase()
  let po = base.playoff_appearances
  if (phase === 'playoffs' && teamInActivePlayoffBracket(tn, saveState)) po += 1
  return {
    ...base,
    program_wins: base.program_wins + w,
    program_losses: base.program_losses + l,
    playoff_appearances: po,
  }
}

/** True if team reached the bracket (QF+), title game, or was runner-up. Matches server tally. */
export function teamHadPostseasonBracketAppearance(teamName: string, entry: any): boolean {
  if (!teamName || !entry || typeof entry !== 'object') return false
  if (String(entry.state_champion ?? '') === teamName) return true
  if (String(entry.runner_up ?? '') === teamName) return true
  const playoffs = entry.playoffs && typeof entry.playoffs === 'object' ? entry.playoffs : {}
  const br = Array.isArray(playoffs.bracket_results) ? playoffs.bracket_results : []
  for (const g of br) {
    if (!g || typeof g !== 'object') continue
    if (g.home === teamName || g.away === teamName) return true
  }
  const pbc = entry.playoffs_by_class
  if (pbc && typeof pbc === 'object') {
    if (scanPlayoffsByClassForTeam(teamName, pbc as Record<string, unknown>)) return true
  }
  return false
}

function seasonsAllHaveRegionalChampionsKey(seasons: any[]): boolean {
  if (!seasons.length) return true
  return seasons.every((s) => s && typeof s === 'object' && 'regional_champions' in (s as object))
}

/** Authoritative aggregates from bundled league_history (mirrors backend build_team_program_totals_display). */
export type TeamProgramTotalsDisplay = {
  program_wins: number
  program_losses: number
  state_championships: number
  regional_championships: number
  playoff_appearances: number
}

export function buildTeamProgramTotalsFromLeagueHistory(
  leagueHistory: any,
  teamName: string,
  persistedRegional: number = 0,
): TeamProgramTotalsDisplay {
  const team = String(teamName ?? '').trim()
  const seasons = Array.isArray(leagueHistory?.seasons) ? leagueHistory.seasons : []
  let programWins = 0
  let programLosses = 0
  let stateChampionships = 0
  let regionalFromHist = 0
  let playoffAppearances = 0
  for (const ent of seasons) {
    if (!ent || typeof ent !== 'object') continue
    if (teamWonStateInSeason(team, ent)) stateChampionships += 1
    const rc = (ent as { regional_champions?: unknown }).regional_champions
    if (Array.isArray(rc) && rc.includes(team)) regionalFromHist += 1
    if (teamHadPostseasonBracketAppearance(team, ent)) playoffAppearances += 1
    const standingsList = Array.isArray(ent.standings) ? ent.standings : []
    for (const r of standingsList) {
      if (r && typeof r === 'object' && r.team === team) {
        programWins += Number(r.wins ?? 0)
        programLosses += Number(r.losses ?? 0)
        break
      }
    }
  }
  const p = Number(persistedRegional) || 0
  const h = regionalFromHist
  const regionalChampionships = seasonsAllHaveRegionalChampionsKey(seasons) ? h : Math.max(p, h)
  return {
    program_wins: programWins,
    program_losses: programLosses,
    state_championships: stateChampionships,
    regional_championships: regionalChampionships,
    playoff_appearances: playoffAppearances,
  }
}

function normCoach(s: string | null | undefined): string {
  return String(s ?? '')
    .trim()
    .toLowerCase()
}

/** Build coach history rows from bundled or in-memory league_history.json (same rules as server get_coach_history). */
export type TeamHistoryRow = {
  year: number | string | null | undefined
  wins: number
  losses: number
  postseason: string
  coach: string
  has_recap: boolean
}

/** Per-season rows for one team from bundled league_history (matches server get_team_history). */
export function buildTeamHistoryFromLeagueHistory(
  leagueHistory: any,
  teamName: string,
  saveTeams?: unknown,
): TeamHistoryRow[] {
  const team = String(teamName ?? '').trim()
  if (!team) return []
  const seasons = Array.isArray(leagueHistory?.seasons) ? leagueHistory.seasons : []
  const rows: TeamHistoryRow[] = []
  for (const s of seasons) {
    if (!s || typeof s !== 'object') continue
    const year = s.year
    const standingsList = Array.isArray(s.standings) ? s.standings : []
    const recaps = s.team_recaps && typeof s.team_recaps === 'object' ? s.team_recaps : {}
    let stRow: any = null
    for (const r of standingsList) {
      if (r && typeof r === 'object' && r.team === team) {
        stRow = r
        break
      }
    }
    if (!stRow) continue
    const coachRaw = stRow.coach
    const coach = typeof coachRaw === 'string' ? coachRaw.trim() || '—' : '—'
    const rel = recaps[team]
    rows.push({
      year,
      wins: Number(stRow.wins ?? 0),
      losses: Number(stRow.losses ?? 0),
      postseason: postseasonLabelForTeam(team, s, saveTeams),
      coach,
      has_recap: typeof rel === 'string' && rel.length > 0,
    })
  }
  rows.sort((a, b) => Number(b.year ?? 0) - Number(a.year ?? 0))
  return rows
}

export function buildCoachHistoryFromLeagueHistory(
  leagueHistory: any,
  coachName: string,
  saveTeams?: unknown,
): CoachHistoryRow[] {
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
        postseason: postseasonLabelForTeam(team, s, saveTeams),
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

function findCoachTeamInSave(saveState: any, teamHint: string, coachNorm: string): { teamName: string; coachDisplay: string } | null {
  const tnHint = String(teamHint ?? '').trim()
  if (tnHint && saveState?.teams && Array.isArray(saveState.teams)) {
    for (const t of saveState.teams) {
      if (!t || typeof t !== 'object') continue
      if (String((t as { name?: unknown }).name ?? '').trim() !== tnHint) continue
      const cn = normCoach(String((t as { coach?: { name?: unknown } }).coach?.name ?? ''))
      if (cn === coachNorm) {
        const disp = String((t as { coach?: { name?: unknown } }).coach?.name ?? '').trim()
        return { teamName: tnHint, coachDisplay: disp || '—' }
      }
    }
  }
  if (saveState?.teams && Array.isArray(saveState.teams)) {
    for (const t of saveState.teams) {
      if (!t || typeof t !== 'object') continue
      const cn = normCoach(String((t as { coach?: { name?: unknown } }).coach?.name ?? ''))
      if (cn !== coachNorm) continue
      const nm = String((t as { name?: unknown }).name ?? '').trim()
      if (!nm) continue
      const disp = String((t as { coach?: { name?: unknown } }).coach?.name ?? '').trim()
      return { teamName: nm, coachDisplay: disp || '—' }
    }
  }
  return null
}

/** One synthetic row for the in-progress calendar year so W–L and career totals stay current before season is archived.
 *
 * Returns null in non-regular/playoffs phases unless current standings have non-zero data,
 * to avoid stamping a meaningless 0-0 row for the new year on top of an already-archived
 * row from the just-finished season (those archived rows already render for offseason/preseason).
 */
export function buildLiveCoachSeasonRow(
  coachName: string,
  teamName: string | undefined,
  saveState: any,
): CoachHistoryRow | null {
  const target = normCoach(coachName)
  if (!target) return null
  const phase = String(saveState?.season_phase ?? '')
    .trim()
    .toLowerCase()
  const linked = findCoachTeamInSave(saveState, teamName ?? '', target)
  if (!linked) return null
  const { teamName: tnm, coachDisplay } = linked
  const y = Number(saveState?.current_year)
  if (!Number.isFinite(y)) return null
  const stRow = saveState?.standings?.[tnm]
  let wins = stRow != null ? Number(stRow.wins ?? 0) : null
  let losses = stRow != null ? Number(stRow.losses ?? 0) : null
  if (wins == null || losses == null) {
    for (const t of saveState?.teams ?? []) {
      if (t && typeof t === 'object' && String((t as { name?: unknown }).name ?? '').trim() === tnm) {
        wins = Number((t as { wins?: unknown }).wins ?? 0)
        losses = Number((t as { losses?: unknown }).losses ?? 0)
        break
      }
    }
  }
  if (wins == null || losses == null) return null
  if (phase !== 'regular' && phase !== 'playoffs' && wins === 0 && losses === 0) return null
  const postseason = phase === 'playoffs' ? livePostseasonLabelForTeam(tnm, saveState) : '—'
  return {
    year: y,
    team: tnm,
    wins,
    losses,
    postseason,
    coach: coachDisplay,
    has_recap: false,
  }
}

/** Drop archived row for same year/team as the live row, prepend live, sort by year desc. */
export function mergeInProgressCoachHistory(
  archived: CoachHistoryRow[],
  coachName: string,
  teamName: string | undefined,
  saveState: any,
): CoachHistoryRow[] {
  const live = buildLiveCoachSeasonRow(coachName, teamName, saveState)
  if (!live) return archived
  const y = Number(live.year)
  const filtered = archived.filter((r) => !(Number(r.year) === y && r.team === live.team))
  return [...filtered, live].sort((a, b) => Number(b.year ?? 0) - Number(a.year ?? 0))
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
