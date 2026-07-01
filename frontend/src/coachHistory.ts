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

/** All playoff bracket games on a completed season archive row (multiclass first, else legacy `playoffs`). */
export function iterBracketGamesFromSeasonEntry(entry: any): any[] {
  if (!entry || typeof entry !== 'object') return []
  const pbc = (entry as { playoffs_by_class?: unknown }).playoffs_by_class
  if (pbc && typeof pbc === 'object' && Object.keys(pbc as object).length > 0) {
    const out: any[] = []
    for (const inner of Object.values(pbc as Record<string, unknown>)) {
      if (!inner || typeof inner !== 'object') continue
      const br = Array.isArray((inner as { bracket_results?: unknown }).bracket_results)
        ? (inner as { bracket_results: any[] }).bracket_results
        : []
      for (const g of br) out.push(g)
    }
    return out
  }
  const pl = (entry as { playoffs?: unknown }).playoffs
  if (pl && typeof pl === 'object' && Array.isArray((pl as { bracket_results?: unknown }).bracket_results)) {
    return [...(pl as { bracket_results: any[] }).bracket_results]
  }
  return []
}

/** Bracket games from the in-save `playoffs` object (flat or `by_class`). */
export function iterBracketGamesFromPlayoffsState(playoffs: any): any[] {
  if (!playoffs || typeof playoffs !== 'object') return []
  const raw = (playoffs as { by_class?: unknown }).by_class
  if (raw && typeof raw === 'object' && Object.keys(raw as object).length > 0) {
    const out: any[] = []
    for (const inner of Object.values(raw as Record<string, unknown>)) {
      if (!inner || typeof inner !== 'object') continue
      const br = Array.isArray((inner as { bracket_results?: unknown }).bracket_results)
        ? (inner as { bracket_results: any[] }).bracket_results
        : []
      for (const g of br) out.push(g)
    }
    return out
  }
  return Array.isArray((playoffs as { bracket_results?: unknown }).bracket_results)
    ? [...((playoffs as { bracket_results: any[] }).bracket_results)]
    : []
}

function shouldAddLivePlayoffGames(saveState: any): boolean {
  const ph = String(saveState?.season_phase ?? '').toLowerCase()
  if (ph !== 'playoffs' && ph !== 'season_summary') return false
  return iterBracketGamesFromPlayoffsState(saveState?.playoffs).length > 0
}

/** Wins/losses from a list of bracket result dicts (home/away/winner). */
export function tallyPostseasonGamesForTeam(teamName: string, games: any[]): { wins: number; losses: number } {
  let wins = 0
  let losses = 0
  const t = String(teamName ?? '').trim()
  if (!t) return { wins: 0, losses: 0 }
  for (const g of games) {
    if (!g || typeof g !== 'object') continue
    const h = String((g as { home?: unknown }).home ?? '')
    const a = String((g as { away?: unknown }).away ?? '')
    if (h !== t && a !== t) continue
    const win = String((g as { winner?: unknown }).winner ?? '')
    if (!win) continue
    if (win === t) wins += 1
    else losses += 1
  }
  return { wins, losses }
}

/** Shape used by `teamWonStateInSeason` against completed `saveState.playoffs`. */
export function syntheticSeasonEntryFromLivePlayoffs(saveState: any): Record<string, unknown> | null {
  const p = saveState?.playoffs
  if (!p || typeof p !== 'object' || !p.completed) return null
  return {
    state_champion: String((p as { champion?: unknown }).champion ?? ''),
    runner_up: String((p as { runner_up?: unknown }).runner_up ?? ''),
    playoffs_by_class: (p as { by_class?: unknown }).by_class,
    playoffs: {
      bracket_results: Array.isArray((p as { bracket_results?: unknown }).bracket_results)
        ? (p as { bracket_results: any[] }).bracket_results
        : [],
    },
  }
}

/** Calendar years this school won state (archived `league_history` plus completed bracket not yet in history). */
export function buildStateChampionshipYearsForTeam(
  leagueHistory: any,
  teamName: string,
  saveState?: any,
): number[] {
  const team = String(teamName ?? '').trim()
  if (!team) return []
  const seasons = Array.isArray(leagueHistory?.seasons) ? leagueHistory.seasons : []
  const years: number[] = []
  for (const ent of seasons) {
    if (!ent || typeof ent !== 'object') continue
    if (!teamWonStateInSeason(team, ent)) continue
    const rawY = (ent as { year?: unknown }).year ?? (ent as { season?: unknown }).season
    const y = Number(rawY)
    if (Number.isFinite(y)) years.push(y)
  }
  const stub = saveState ? syntheticSeasonEntryFromLivePlayoffs(saveState) : null
  if (stub && teamWonStateInSeason(team, stub)) {
    const cy = Number(saveState?.current_year)
    if (Number.isFinite(cy) && !years.includes(cy)) years.push(cy)
  }
  years.sort((a, b) => a - b)
  return years
}

/** Cumulative postseason W–L from all archived seasons plus the live bracket during playoffs / season summary. */
export function computeCareerPostseasonWL(
  teamName: string,
  leagueHistory: any,
  saveState?: any,
): { wins: number; losses: number } {
  let wins = 0
  let losses = 0
  const team = String(teamName ?? '').trim()
  if (!team) return { wins: 0, losses: 0 }
  const seasons = Array.isArray(leagueHistory?.seasons) ? leagueHistory.seasons : []
  for (const ent of seasons) {
    const r = tallyPostseasonGamesForTeam(team, iterBracketGamesFromSeasonEntry(ent))
    wins += r.wins
    losses += r.losses
  }
  if (saveState && shouldAddLivePlayoffGames(saveState)) {
    const r2 = tallyPostseasonGamesForTeam(team, iterBracketGamesFromPlayoffsState(saveState.playoffs))
    wins += r2.wins
    losses += r2.losses
  }
  return { wins, losses }
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
  seasonRecaps?: Record<string, string>,
): TeamHistoryRow[] {
  const team = String(teamName ?? '').trim()
  if (!team) return []
  const seasons = Array.isArray(leagueHistory?.seasons) ? leagueHistory.seasons : []
  const rows: TeamHistoryRow[] = []
  for (const s of seasons) {
    if (!s || typeof s !== 'object') continue
    const year = s.year
    const standingsList = Array.isArray(s.standings) ? s.standings : []
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
    rows.push({
      year,
      wins: Number(stRow.wins ?? 0),
      losses: Number(stRow.losses ?? 0),
      postseason: postseasonLabelForTeam(team, s, saveTeams),
      coach,
      has_recap: hasRecapForArchivedSeason(s, team, year ?? '', seasonRecaps),
    })
  }
  rows.sort((a, b) => Number(b.year ?? 0) - Number(a.year ?? 0))
  return rows
}

function teamHistoryRowKey(year: unknown): number {
  return Number(year ?? 0)
}

/** Merge team history row lists; later lists fill gaps and upgrade ``has_recap``. */
export function mergeTeamHistoryRowLists(...lists: TeamHistoryRow[][]): TeamHistoryRow[] {
  const byYear = new Map<number, TeamHistoryRow>()
  for (const list of lists) {
    for (const r of list) {
      const y = teamHistoryRowKey(r.year)
      if (!Number.isFinite(y) || y <= 0) continue
      const prev = byYear.get(y)
      if (!prev) {
        byYear.set(y, { ...r })
        continue
      }
      byYear.set(y, {
        year: r.year ?? prev.year,
        wins: typeof r.wins === 'number' ? r.wins : prev.wins,
        losses: typeof r.losses === 'number' ? r.losses : prev.losses,
        postseason: r.postseason && r.postseason !== '—' ? r.postseason : prev.postseason,
        coach: r.coach && r.coach !== '—' ? r.coach : prev.coach,
        has_recap: Boolean(r.has_recap || prev.has_recap),
      })
    }
  }
  return [...byYear.values()].sort((a, b) => Number(b.year ?? 0) - Number(a.year ?? 0))
}

/** Season rows for one team from ``coach_career_log`` on league_save.json. */
export function buildTeamHistoryFromCareerLog(
  careerLog: unknown,
  teamName: string,
  leagueHistory?: any,
  seasonRecaps?: Record<string, string>,
  saveTeams?: unknown,
): TeamHistoryRow[] {
  const team = String(teamName ?? '').trim()
  if (!team || !Array.isArray(careerLog)) return []
  const seasons = Array.isArray(leagueHistory?.seasons) ? leagueHistory.seasons : []
  const seasonByYear = new Map<number, { team_recaps?: Record<string, string> } & Record<string, unknown>>()
  for (const s of seasons) {
    if (!s || typeof s !== 'object') continue
    const y = Number((s as { year?: unknown }).year)
    if (Number.isFinite(y)) seasonByYear.set(y, s as { team_recaps?: Record<string, string> })
  }
  const rows: TeamHistoryRow[] = []
  const seen = new Set<number>()
  for (const e of careerLog) {
    if (!e || typeof e !== 'object') continue
    const rowTeam = String((e as { team?: unknown }).team ?? '').trim()
    if (rowTeam !== team) continue
    const y = Number((e as { year?: unknown }).year)
    if (!Number.isFinite(y) || seen.has(y)) continue
    seen.add(y)
    const season = seasonByYear.get(y)
    const coachRaw = (e as { coach?: unknown }).coach
    rows.push({
      year: y,
      wins: Number((e as { wins?: unknown }).wins ?? 0),
      losses: Number((e as { losses?: unknown }).losses ?? 0),
      postseason: season ? postseasonLabelForTeam(team, season, saveTeams) : '—',
      coach: typeof coachRaw === 'string' && coachRaw.trim() ? coachRaw.trim() : '—',
      has_recap: hasRecapForArchivedSeason(season, team, y, seasonRecaps),
    })
  }
  rows.sort((a, b) => Number(b.year ?? 0) - Number(a.year ?? 0))
  return rows
}

/** Infer archived seasons from bundled ``season_recaps`` paths when history JSON is missing. */
export function buildTeamHistoryFromSeasonRecaps(
  seasonRecaps: Record<string, string> | undefined,
  teamName: string,
  leagueHistory?: any,
  saveTeams?: unknown,
): TeamHistoryRow[] {
  const team = String(teamName ?? '').trim()
  if (!team || !seasonRecaps) return []
  const slug = team.replaceAll(' ', '_').toLowerCase()
  const teamLow = team.toLowerCase()
  const years = new Set<number>()
  for (const path of Object.keys(seasonRecaps)) {
    const low = path.toLowerCase()
    if (!low.endsWith('.txt')) continue
    const base = (low.split('/').pop() ?? '').replace(/\.txt$/, '')
    const nameMatch =
      base === slug || base === teamLow.replaceAll(' ', '_') || base.includes(slug) || low.includes(teamLow)
    if (!nameMatch) continue
    const ym = low.match(/year[_-](\d{4})/) ?? low.match(/\/(\d{4})\//)
    if (ym) years.add(Number(ym[1]))
  }
  const seasons = Array.isArray(leagueHistory?.seasons) ? leagueHistory.seasons : []
  const rows: TeamHistoryRow[] = []
  for (const y of years) {
    let season: { team_recaps?: Record<string, string> } & Record<string, unknown> | undefined
    for (const s of seasons) {
      if (s && typeof s === 'object' && Number((s as { year?: unknown }).year) === y) {
        season = s as { team_recaps?: Record<string, string> }
        break
      }
    }
    const standingsList = Array.isArray(season?.standings) ? season!.standings : []
    let stRow: { wins?: unknown; losses?: unknown; coach?: unknown } | null = null
    for (const r of standingsList) {
      if (r && typeof r === 'object' && (r as { team?: unknown }).team === team) {
        stRow = r as { wins?: unknown; losses?: unknown; coach?: unknown }
        break
      }
    }
    rows.push({
      year: y,
      wins: stRow ? Number(stRow.wins ?? 0) : 0,
      losses: stRow ? Number(stRow.losses ?? 0) : 0,
      postseason: season ? postseasonLabelForTeam(team, season, saveTeams) : '—',
      coach: typeof stRow?.coach === 'string' && stRow.coach.trim() ? stRow.coach.trim() : '—',
      has_recap: true,
    })
  }
  rows.sort((a, b) => Number(b.year ?? 0) - Number(a.year ?? 0))
  return rows
}

/** Client-side team history from every source available in memory / bundle. */
export function buildFullTeamHistoryRows(
  leagueHistory: any,
  teamName: string,
  saveState?: any,
  seasonRecaps?: Record<string, string>,
): TeamHistoryRow[] {
  const teams = saveState?.teams
  return mergeTeamHistoryRowLists(
    buildTeamHistoryFromLeagueHistory(leagueHistory, teamName, teams, seasonRecaps),
    buildTeamHistoryFromCareerLog(saveState?.coach_career_log, teamName, leagueHistory, seasonRecaps, teams),
    buildTeamHistoryFromSeasonRecaps(seasonRecaps, teamName, leagueHistory, teams),
  )
}

function coachNameForTeamFromSave(saveState: any, teamName: string): string {
  const tn = String(teamName ?? '').trim()
  if (!tn || !Array.isArray(saveState?.teams)) return '—'
  for (const t of saveState.teams) {
    if (!t || typeof t !== 'object') continue
    if (String((t as { name?: unknown }).name ?? '').trim() !== tn) continue
    const nm = String((t as { coach?: { name?: unknown } }).coach?.name ?? '').trim()
    return nm || '—'
  }
  return '—'
}

/**
 * Add in-progress or just-finished season rows when league_history.json has not archived them yet.
 * Matches backend ``_merge_live_and_snapshot_team_history_rows``.
 */
export function mergeLiveAndSnapshotTeamHistory(
  archived: TeamHistoryRow[],
  teamName: string,
  saveState?: any,
  saveTeams?: unknown,
  seasonRecaps?: Record<string, string>,
): TeamHistoryRow[] {
  const team = String(teamName ?? '').trim()
  if (!team || !saveState) return archived
  const seen = new Set(archived.map((r) => Number(r.year ?? 0)))
  const out: TeamHistoryRow[] = [...archived]
  const phase = String(saveState.season_phase ?? '').toLowerCase()
  const coach = coachNameForTeamFromSave(saveState, team)

  const push = (year: number, wins: number, losses: number, postseason: string, hasRecap: boolean) => {
    if (!Number.isFinite(year) || seen.has(year)) return
    seen.add(year)
    out.push({ year, wins, losses, postseason, coach, has_recap: hasRecap })
  }

  const cy = Number(saveState.current_year)
  if (
    Number.isFinite(cy) &&
    (phase === 'regular' || phase === 'playoffs' || phase === 'season_summary')
  ) {
    const st = saveState.standings?.[team]
    const wins = st != null ? Number(st.wins ?? 0) : 0
    const losses = st != null ? Number(st.losses ?? 0) : 0
    const postseason =
      phase === 'playoffs' || phase === 'season_summary'
        ? livePostseasonLabelForTeam(team, saveState)
        : '—'
    const seasons = Array.isArray(saveState?.league_history?.seasons)
      ? saveState.league_history.seasons
      : []
    let seasonEntry: { team_recaps?: Record<string, string> } | undefined
    for (const s of seasons) {
      if (s && typeof s === 'object' && Number(s.year) === cy) {
        seasonEntry = s
        break
      }
    }
    push(
      cy,
      wins,
      losses,
      postseason,
      hasRecapForArchivedSeason(seasonEntry ?? ({ year: cy } as { team_recaps?: Record<string, string> }), team, cy, seasonRecaps),
    )
  }

  const lcy = Number(saveState.last_completed_year)
  const snap = saveState.last_completed_standings?.[team]
  if (Number.isFinite(lcy) && snap && typeof snap === 'object') {
    const seasons = Array.isArray(saveState?.league_history?.seasons)
      ? saveState.league_history.seasons
      : []
    let seasonEntry: any = null
    for (const s of seasons) {
      if (s && typeof s === 'object' && Number(s.year) === lcy) {
        seasonEntry = s
        break
      }
    }
    push(
      lcy,
      Number(snap.wins ?? 0),
      Number(snap.losses ?? 0),
      seasonEntry ? postseasonLabelForTeam(team, seasonEntry, saveTeams) : '—',
      hasRecapForArchivedSeason(seasonEntry ?? ({ year: lcy } as { team_recaps?: Record<string, string> }), team, lcy, seasonRecaps),
    )
  }

  out.sort((a, b) => Number(b.year ?? 0) - Number(a.year ?? 0))
  return out
}

function coachHistoryRowKey(year: unknown, team: string): string {
  return `${Number(year ?? 0)}|${team}`
}

/** Rows from persisted ``coach_career_log`` on league_save (survives archives without ``coach`` on standings). */
export function buildCoachHistoryFromCareerLog(
  careerLog: unknown,
  coachName: string,
  leagueHistory?: any,
  saveTeams?: unknown,
): CoachHistoryRow[] {
  const target = normCoach(coachName)
  if (!target || !Array.isArray(careerLog)) return []
  const seasons = Array.isArray(leagueHistory?.seasons) ? leagueHistory.seasons : []
  const seasonByYear = new Map<number, any>()
  for (const s of seasons) {
    if (!s || typeof s !== 'object') continue
    const y = Number(s.year)
    if (Number.isFinite(y)) seasonByYear.set(y, s)
  }
  const rows: CoachHistoryRow[] = []
  for (const e of careerLog) {
    if (!e || typeof e !== 'object') continue
    const coachRaw = (e as { coach?: unknown }).coach
    if (typeof coachRaw !== 'string' || normCoach(coachRaw) !== target) continue
    const team = String((e as { team?: unknown }).team ?? '').trim()
    if (!team) continue
    const rawYear = (e as { year?: unknown }).year
    const year: CoachHistoryRow['year'] =
      typeof rawYear === 'number' || typeof rawYear === 'string' || rawYear == null ? rawYear : Number(rawYear)
    const yNum = Number(rawYear)
    const season = Number.isFinite(yNum) ? seasonByYear.get(yNum) : undefined
    rows.push({
      year,
      team,
      wins: Number((e as { wins?: unknown }).wins ?? 0),
      losses: Number((e as { losses?: unknown }).losses ?? 0),
      postseason: season ? postseasonLabelForTeam(team, season, saveTeams) : '—',
      coach: coachRaw.trim() || '—',
      has_recap: season ? hasRecapForArchivedSeason(season, team, year ?? '') : false,
    })
  }
  rows.sort((a, b) => Number(b.year ?? 0) - Number(a.year ?? 0))
  return rows
}

export function buildCoachHistoryFromLeagueHistory(
  leagueHistory: any,
  coachName: string,
  saveTeams?: unknown,
  careerLog?: unknown,
): CoachHistoryRow[] {
  const target = normCoach(coachName)
  if (!target) return []

  const fromLog = buildCoachHistoryFromCareerLog(careerLog, coachName, leagueHistory, saveTeams)
  const seen = new Set(fromLog.map((r) => coachHistoryRowKey(r.year, r.team)))
  const seasons = Array.isArray(leagueHistory?.seasons) ? leagueHistory.seasons : []
  const rows: CoachHistoryRow[] = [...fromLog]

  for (const s of seasons) {
    if (!s || typeof s !== 'object') continue
    const year = s.year
    const standingsList = Array.isArray(s.standings) ? s.standings : []
    for (const stRow of standingsList) {
      if (!stRow || typeof stRow !== 'object') continue
      const c = stRow.coach
      if (typeof c !== 'string' || normCoach(c) !== target) continue
      const team = String(stRow.team ?? '').trim()
      if (!team) continue
      const key = coachHistoryRowKey(year, team)
      if (seen.has(key)) continue
      seen.add(key)
      rows.push({
        year,
        team,
        wins: Number(stRow.wins ?? 0),
        losses: Number(stRow.losses ?? 0),
        postseason: postseasonLabelForTeam(team, s, saveTeams),
        coach: c.trim() || '—',
        has_recap: hasRecapForArchivedSeason(s, team, year ?? ''),
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
  const teamLow = teamName.toLowerCase()
  for (const [path, text] of Object.entries(seasonRecaps)) {
    const low = path.toLowerCase()
    if (!low.endsWith('.txt')) continue
    const base = low.split('/').pop() ?? low
    const nameMatch =
      base === `${slug.toLowerCase()}.txt` ||
      base === `${teamLow}.txt` ||
      base.includes(slug.toLowerCase())
    const yearMatch =
      low.includes(`year_${y}/`) ||
      low.includes(`year_${y}\\`) ||
      low.includes(`/${y}/`) ||
      path.includes(y)
    if (nameMatch && yearMatch) return text
  }
  for (const [, text] of Object.entries(seasonRecaps)) {
    if (text.includes(teamName) && text.includes(`Year ${y}`)) return text
  }
  return null
}

/** Whether an archived season row has a recap on disk or in the bundle. */
export function hasRecapForArchivedSeason(
  seasonEntry: { team_recaps?: Record<string, string> } | null | undefined,
  teamName: string,
  year: number | string,
  seasonRecaps?: Record<string, string>,
): boolean {
  const team = String(teamName ?? '').trim()
  if (!team) return false
  const recaps = seasonEntry?.team_recaps
  if (recaps && typeof recaps[team] === 'string' && recaps[team].length > 0) return true
  return Boolean(seasonRecaps && findLocalSeasonRecap(seasonRecaps, team, year))
}

export type DownloadTeamSeasonRecapOpts = {
  apiBase?: string
  headers?: Record<string, string>
  saveId?: string
  teamName: string
  year: number | string
  seasonRecaps?: Record<string, string>
  isLocalBundle?: boolean
}

/** Trigger browser download of a team season recap .txt (API or local bundle). */
export async function downloadTeamSeasonRecap(opts: DownloadTeamSeasonRecapOpts): Promise<void> {
  const team = String(opts.teamName ?? '').trim()
  const year = opts.year
  if (!team) throw new Error('Missing team name')
  const filename = `${team.replaceAll(' ', '_')}_Year_${year}_recap.txt`

  if (opts.isLocalBundle && opts.seasonRecaps) {
    const text = findLocalSeasonRecap(opts.seasonRecaps, team, year)
    if (!text) throw new Error('Recap not found in this save zip for that season.')
    const blob = new Blob([text], { type: 'text/plain' })
    const dlUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = dlUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(dlUrl), 250)
    return
  }

  if (!opts.apiBase || !opts.saveId) throw new Error('No save loaded.')
  const url = `${opts.apiBase}/saves/${opts.saveId}/team-history/recap.txt?team_name=${encodeURIComponent(
    team,
  )}&year=${encodeURIComponent(String(year))}`
  const resp = await fetch(url, { headers: opts.headers })
  if (!resp.ok) throw new Error(await resp.text())
  const text = await resp.text()
  const blob = new Blob([text], { type: 'text/plain' })
  const dlUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = dlUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(dlUrl), 250)
}

export type CoachStatsRow = {
  coachName: string
  school: string
  wins: number
  losses: number
  winPct: number
  regionalTitles: number
  playoffAppearances: number
  stateRunnerUps: number
  stateChampionships: number
  seasons: number
}

function seasonEntryForYear(leagueHistory: any, year: number): any | null {
  if (!Number.isFinite(year)) return null
  const seasons = Array.isArray(leagueHistory?.seasons) ? leagueHistory.seasons : []
  for (const s of seasons) {
    if (!s || typeof s !== 'object') continue
    const y = Number((s as { year?: unknown }).year ?? (s as { season?: unknown }).season)
    if (y === year) return s
  }
  return null
}

/** Head coaches only — career log, archived standings, and current rosters. */
function collectHeadCoachDisplayNames(saveState: any, leagueHistory: any): Map<string, string> {
  const map = new Map<string, string>()
  const add = (raw: unknown) => {
    const disp = typeof raw === 'string' ? raw.trim() : ''
    if (!disp || disp === '—') return
    const key = normCoach(disp)
    if (!key) return
    if (!map.has(key)) map.set(key, disp)
  }

  const careerLog = saveState?.coach_career_log
  if (Array.isArray(careerLog)) {
    for (const e of careerLog) {
      if (!e || typeof e !== 'object') continue
      add((e as { coach?: unknown }).coach)
    }
  }

  const seasons = Array.isArray(leagueHistory?.seasons) ? leagueHistory.seasons : []
  for (const s of seasons) {
    if (!s || typeof s !== 'object') continue
    const standingsList = Array.isArray((s as { standings?: unknown }).standings)
      ? (s as { standings: unknown[] }).standings
      : []
    for (const stRow of standingsList) {
      if (!stRow || typeof stRow !== 'object') continue
      add((stRow as { coach?: unknown }).coach)
    }
  }

  if (Array.isArray(saveState?.teams)) {
    for (const t of saveState.teams) {
      if (!t || typeof t !== 'object') continue
      add((t as { coach?: { name?: unknown } }).coach?.name)
    }
  }

  for (const t of saveState?.teams ?? []) {
    if (!t || typeof t !== 'object') continue
    const disp = String((t as { coach?: { name?: unknown } }).coach?.name ?? '').trim()
    const key = normCoach(disp)
    if (key && disp) map.set(key, disp)
  }

  return map
}

function countRegionalTitlesForCoachRows(rows: CoachHistoryRow[], leagueHistory: any): number {
  let n = 0
  for (const r of rows) {
    const y = Number(r.year)
    const team = String(r.team ?? '').trim()
    if (!team || !Number.isFinite(y)) continue
    const season = seasonEntryForYear(leagueHistory, y)
    if (!season) continue
    const rc = (season as { regional_champions?: unknown }).regional_champions
    if (Array.isArray(rc) && rc.includes(team)) n += 1
  }
  return n
}

function countPlayoffAppearancesForCoachRows(
  rows: CoachHistoryRow[],
  leagueHistory: any,
  saveState?: any,
): number {
  let n = 0
  const countedYears = new Set<string>()
  for (const r of rows) {
    const y = Number(r.year)
    const team = String(r.team ?? '').trim()
    if (!team || !Number.isFinite(y)) continue
    const season = seasonEntryForYear(leagueHistory, y)
    if (season && teamHadPostseasonBracketAppearance(team, season)) {
      n += 1
      countedYears.add(`${y}|${team}`)
    }
  }
  const phase = String(saveState?.season_phase ?? '').toLowerCase()
  if (phase === 'playoffs' && saveState) {
    const cy = Number(saveState.current_year)
    if (Number.isFinite(cy)) {
      for (const r of rows) {
        if (Number(r.year) !== cy) continue
        const team = String(r.team ?? '').trim()
        if (!team) continue
        if (countedYears.has(`${cy}|${team}`)) continue
        if (teamInActivePlayoffBracket(team, saveState)) n += 1
      }
    }
  }
  return n
}

function schoolForCoach(norm: string, saveState: any, rows: CoachHistoryRow[]): string {
  const linked = findCoachTeamInSave(saveState, '', norm)
  if (linked?.teamName) return linked.teamName
  if (rows.length > 0) return String(rows[0].team ?? '').trim()
  return ''
}

/** League-wide head coach leaderboard from career log + league history. */
export function buildCoachStatsLeaderboard(saveState: any, leagueHistory: any): CoachStatsRow[] {
  const coachMap = collectHeadCoachDisplayNames(saveState, leagueHistory)
  const careerLog = saveState?.coach_career_log
  const saveTeams = saveState?.teams
  const out: CoachStatsRow[] = []

  for (const [norm, displayName] of coachMap) {
    const archived = buildCoachHistoryFromLeagueHistory(leagueHistory, displayName, saveTeams, careerLog)
    const schoolHint = schoolForCoach(norm, saveState, archived)
    const rows = mergeInProgressCoachHistory(archived, displayName, schoolHint || undefined, saveState)
    if (rows.length === 0) continue

    const career = aggregateCoachCareer(rows)
    const wins = career.totalWins
    const losses = career.totalLosses
    const games = wins + losses
    const winPct = games > 0 ? wins / games : 0

    out.push({
      coachName: displayName,
      school: schoolForCoach(norm, saveState, rows),
      wins,
      losses,
      winPct,
      regionalTitles: countRegionalTitlesForCoachRows(rows, leagueHistory),
      playoffAppearances: countPlayoffAppearancesForCoachRows(rows, leagueHistory, saveState),
      stateRunnerUps: career.runnerUps,
      stateChampionships: career.stateChampionships,
      seasons: career.seasons,
    })
  }

  out.sort((a, b) => {
    if (b.stateChampionships !== a.stateChampionships) return b.stateChampionships - a.stateChampionships
    if (b.wins !== a.wins) return b.wins - a.wins
    return a.coachName.localeCompare(b.coachName)
  })

  return out
}
