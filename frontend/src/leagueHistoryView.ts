/**
 * Helpers for STATE → League History (archived seasons from league_history.json).
 */

export function standingsListToRecord(
  standingsList: unknown,
): Record<string, { wins: number; losses: number; points_for: number; points_against: number }> {
  const out: Record<string, { wins: number; losses: number; points_for: number; points_against: number }> = {}
  if (!Array.isArray(standingsList)) return out
  for (const r of standingsList) {
    if (!r || typeof r !== 'object') continue
    const team = String((r as { team?: unknown }).team ?? '').trim()
    if (!team) continue
    out[team] = {
      wins: Number((r as { wins?: unknown }).wins ?? 0),
      losses: Number((r as { losses?: unknown }).losses ?? 0),
      points_for: Number((r as { points_for?: unknown }).points_for ?? 0),
      points_against: Number((r as { points_against?: unknown }).points_against ?? 0),
    }
  }
  return out
}

export function findSeasonEntryByCalendarYear(seasons: unknown, year: number): Record<string, unknown> | null {
  if (!Array.isArray(seasons)) return null
  const y = Number(year)
  if (!Number.isFinite(y)) return null
  for (const s of seasons) {
    if (!s || typeof s !== 'object') continue
    if (Number((s as { year?: unknown }).year) === y) return s as Record<string, unknown>
  }
  return null
}

/** Split unrelated brackets (multiclass flat merge) via connectivity on team names. */
export function partitionBracketGamesByConnectedTeams(gamesIn: unknown): unknown[][] {
  const list = (Array.isArray(gamesIn) ? gamesIn : []).filter((g) => g && typeof g === 'object') as Record<
    string,
    unknown
  >[]
  if (!list.length) return []
  const teams = new Set<string>()
  for (const g of list) {
    if (g.home) teams.add(String(g.home))
    if (g.away) teams.add(String(g.away))
  }
  const adj = new Map<string, Set<string>>()
  for (const t of teams) adj.set(t, new Set())
  for (const g of list) {
    const h = String(g.home || '')
    const a = String(g.away || '')
    if (h && a) {
      adj.get(h)!.add(a)
      adj.get(a)!.add(h)
    }
  }
  const visited = new Set<string>()
  const components: string[][] = []
  for (const t of teams) {
    if (visited.has(t)) continue
    const comp: string[] = []
    const stack = [t]
    while (stack.length) {
      const u = stack.pop()!
      if (visited.has(u)) continue
      visited.add(u)
      comp.push(u)
      for (const v of adj.get(u) || []) {
        if (!visited.has(v)) stack.push(v)
      }
    }
    components.push(comp)
  }
  return components.map((comp) =>
    list.filter((g) => comp.includes(String(g.home)) && comp.includes(String(g.away))),
  )
}

/**
 * Prefer embedded playoffs_by_class (new saves); else partition flat bracket_results using team graph + labels.
 *
 * ``ARCHIVE_PLAYOFF_ROUND_PRIORITY`` / ``sortedArchivePlayoffRounds`` mirror
 * ``systems.playoff_system.PLAYOFF_ROUND_PRIORITY`` for UI column order (low = earlier round).
 */
export const ARCHIVE_PLAYOFF_ROUND_PRIORITY: Record<string, number> = {
  'Round of 64': 1,
  'Round of 32': 2,
  'Regional Quarterfinal': 2,
  'Round of 16': 3,
  'Regional Semifinal': 3,
  Quarterfinal: 4,
  'Regional Final': 4,
  Semifinal: 5,
  Championship: 6,
}

/** Group ``bracket_results`` by ``round`` and order rounds for display (regional + state). */
export function sortedArchivePlayoffRounds(
  bracketResults: unknown,
): { round: string; games: Record<string, unknown>[] }[] {
  const list = (Array.isArray(bracketResults) ? bracketResults : []).filter(
    (g) => g && typeof g === 'object',
  ) as Record<string, unknown>[]
  const byRound = new Map<string, Record<string, unknown>[]>()
  for (const g of list) {
    const r = String(g.round ?? '').trim() || 'Game'
    if (!byRound.has(r)) byRound.set(r, [])
    byRound.get(r)!.push(g)
  }
  const rounds = [...byRound.keys()]
  rounds.sort((a, b) => {
    const pa = ARCHIVE_PLAYOFF_ROUND_PRIORITY[a] ?? 99
    const pb = ARCHIVE_PLAYOFF_ROUND_PRIORITY[b] ?? 99
    if (pa !== pb) return pa - pb
    return a.localeCompare(b)
  })
  return rounds.map((round) => ({ round, games: byRound.get(round) ?? [] }))
}

export function getHistoricalPlayoffsByClass(
  season: Record<string, unknown> | null | undefined,
  classificationOfTeam: (teamName: string) => string,
): Record<string, Record<string, unknown>> {
  const out: Record<string, Record<string, unknown>> = {}
  if (!season || typeof season !== 'object') return out
  const embedded = season.playoffs_by_class
  if (embedded && typeof embedded === 'object') {
    for (const [k, v] of Object.entries(embedded as Record<string, unknown>)) {
      if (v && typeof v === 'object') out[String(k)] = v as Record<string, unknown>
    }
    return out
  }
  const flat = (season.playoffs as { bracket_results?: unknown } | undefined)?.bracket_results
  if (!Array.isArray(flat) || flat.length === 0) return out
  const buckets = partitionBracketGamesByConnectedTeams(flat)
  const used = new Set<string>()
  buckets.forEach((gamesRaw, idx) => {
    const games = gamesRaw as Record<string, unknown>[]
    if (!games.length) return
    const t0 = String(games[0].home || games[0].away || '')
    let label = t0 ? classificationOfTeam(t0) : `Bracket ${idx + 1}`
    if (!label.trim() || label === '—') label = `Bracket ${idx + 1}`
    let key = label
    let n = 2
    while (used.has(key)) {
      key = `${label} (${n})`
      n += 1
    }
    used.add(key)
    const champGame = games.find((g) => String(g.round) === 'Championship')
    out[key] = {
      bracket_results: games,
      completed: Boolean(champGame && champGame.winner),
      champion: champGame?.winner ? String(champGame.winner) : null,
      runner_up:
        champGame && champGame.winner && champGame.home === champGame.winner ? champGame.away : champGame?.home ?? null,
      seeds: [],
    }
  })
  return out
}
