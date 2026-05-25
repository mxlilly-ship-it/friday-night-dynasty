/**
 * Playoff bracket view helpers (standard 8-team + regional multi-region brackets).
 */

/** Dropdown value for statewide semifinal + championship (not a scheduling region). */
export const PLAYOFF_FINAL_FOUR_VIEW = '__final_four__'

export type PlayoffSeedRow = {
  seed: number
  team: string
  region?: string
  region_seed?: number
}

/** Seed label for bracket lines: regional rank (1–8) when regional; overall seed otherwise. */
export function playoffDisplaySeedForTeam(
  seeds: PlayoffSeedRow[],
  teamName: string,
  mode: 'overall' | 'regional',
): number | null {
  const n = String(teamName ?? '').trim()
  if (!n || n.startsWith('Game ') || /^Seed\s+\d+$/i.test(n)) return null
  const row = seeds.find((s) => String(s.team) === n)
  if (!row) return null
  if (mode === 'regional') {
    const rs = Number(row.region_seed)
    return Number.isFinite(rs) && rs > 0 ? rs : null
  }
  const sn = Number(row.seed)
  return Number.isFinite(sn) && sn > 0 ? sn : null
}

export type PlayoffMatchup = { home: string; away: string }

export type PlayoffGameRow = {
  home: string
  away: string
  home_score?: number | null
  away_score?: number | null
  winner?: string
  round?: string
  projected?: boolean
}

/** True when seeds carry per-team region labels (regional_4x4 / regional_8x4). */
export function isRegionalPlayoffSeeds(seeds: PlayoffSeedRow[]): boolean {
  return seeds.some((s) => {
    const r = s.region != null ? String(s.region).trim() : ''
    return r.length > 0
  })
}

export function playoffRegionsFromSeeds(seeds: PlayoffSeedRow[]): string[] {
  const set = new Set<string>()
  for (const s of seeds) {
    const r = s.region != null ? String(s.region).trim() : ''
    if (r) set.add(r)
  }
  return [...set].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
}

export function userRegionFromSeeds(seeds: PlayoffSeedRow[], userTeam: string): string | null {
  const ut = String(userTeam || '').trim()
  if (!ut) return null
  const row = seeds.find((s) => String(s.team) === ut)
  const r = row?.region != null ? String(row.region).trim() : ''
  return r || null
}

/** Overall (non-regional) round names from bracket size — matches systems/playoff_system.py. */
export function roundNamesForBracketSize(bracketSize: number): string[] {
  let n = Math.max(2, Math.floor(bracketSize))
  const out: string[] = []
  while (n >= 2) {
    if (n === 2) out.push('Championship')
    else if (n === 4) out.push('Semifinal')
    else if (n === 8) out.push('Quarterfinal')
    else out.push(`Round of ${n}`)
    n = Math.floor(n / 2)
  }
  return out
}

/** First-round pairings by seed order (1vN, 2vN-1, …) — matches engine slot pairing. */
export function firstRoundPairsFromSeeds(seeds: PlayoffSeedRow[], bracketSize: number): PlayoffMatchup[] {
  const ordered = [...seeds]
    .sort((a, b) => Number(a.seed) - Number(b.seed))
    .slice(0, bracketSize)
    .map((s) => String(s.team))
  const n = ordered.length
  if (n < 2) return []
  const pairs: PlayoffMatchup[] = []
  for (let i = 0; i < n / 2; i++) {
    pairs.push({ home: ordered[i], away: ordered[n - 1 - i] })
  }
  return pairs
}

/** Standard fixed bracket columns (8, 16, 32, …) for overall seeding. */
export function buildOverallPlayoffColumns(
  seeds: PlayoffSeedRow[],
  results: PlayoffGameRow[],
  bracketSize: number,
): PlayoffRoundColumn[] {
  const size = Math.max(2, Math.floor(bracketSize))
  const roundNames = roundNamesForBracketSize(size)
  const columns: PlayoffRoundColumn[] = []
  let priorPairs = firstRoundPairsFromSeeds(seeds, size)
  let priorRoundGames: PlayoffGameRow[] = []

  for (let ri = 0; ri < roundNames.length; ri++) {
    const roundName = roundNames[ri]
    const games = results.filter((g) => String(g.round || '') === roundName)
    const isFirst = ri === 0
    const isLast = ri === roundNames.length - 1

    if (isFirst) {
      columns.push({
        title: roundName,
        roundKey: roundName,
        pairs: priorPairs,
        games,
        rows: [],
      })
      priorRoundGames = games
      continue
    }

    if (isLast) {
      const prevRoundName = roundNames[ri - 1]
      const prevRows = buildTwoGameRoundRows(priorRoundGames, priorPairs, results.filter((g) => String(g.round || '') === prevRoundName))
      const row = buildChampionshipRow(prevRows, games)
      columns.push({
        title: roundName,
        roundKey: roundName,
        pairs: [],
        games,
        rows: row ? [row] : [],
      })
      continue
    }

    const rows = buildTwoGameRoundRows(priorRoundGames, priorPairs, games)
    columns.push({
      title: roundName,
      roundKey: roundName,
      pairs: [],
      games,
      rows,
    })
    priorPairs = rows.map((r) => ({ home: String(r.home), away: String(r.away) }))
    priorRoundGames = games
  }

  return columns
}

/** In-region round names (matches systems/playoff_system.py). */
export function regionalInRegionRoundNames(teamsPerRegion: number): string[] {
  const tpr = Math.max(2, teamsPerRegion)
  const out: string[] = []
  let n = tpr
  while (n >= 2) {
    if (n === 2) out.push('Regional Final')
    else if (n === 4) out.push('Regional Semifinal')
    else if (n === 8) out.push('Regional Quarterfinal')
    else out.push(`Regional Round of ${n}`)
    n = Math.floor(n / 2)
  }
  return out
}

/** First-round pairings for slot-ordered teams (standard 1v8, 4v5, 2v7, 3v6 for 8). */
export function firstRoundPairsFromOrderedTeams(names: string[]): PlayoffMatchup[] {
  const n = names.length
  if (n < 2) return []
  if (n === 2) return [{ home: names[0], away: names[1] }]
  if (n === 4) {
    return [
      { home: names[0], away: names[3] },
      { home: names[1], away: names[2] },
    ]
  }
  if (n === 8) {
    return [
      { home: names[0], away: names[7] },
      { home: names[3], away: names[4] },
      { home: names[1], away: names[6] },
      { home: names[2], away: names[5] },
    ]
  }
  if (n === 16) {
    return [
      { home: names[0], away: names[15] },
      { home: names[7], away: names[8] },
      { home: names[3], away: names[12] },
      { home: names[4], away: names[11] },
      { home: names[1], away: names[14] },
      { home: names[6], away: names[9] },
      { home: names[2], away: names[13] },
      { home: names[5], away: names[10] },
    ]
  }
  const pairs: PlayoffMatchup[] = []
  for (let i = 0; i < n / 2; i++) pairs.push({ home: names[i], away: names[n - 1 - i] })
  return pairs
}

export function findPlayoffGame(games: PlayoffGameRow[], pair: PlayoffMatchup): PlayoffGameRow | undefined {
  return games.find(
    (g) =>
      (g.home === pair.home && g.away === pair.away) || (g.home === pair.away && g.away === pair.home),
  )
}

function winnerByIndex(games: PlayoffGameRow[], pairs: PlayoffMatchup[], i: number): string | null {
  const p = pairs[i]
  if (!p) return null
  const g = findPlayoffGame(games, p)
  const w = g?.winner
  return w != null && String(w).trim() !== '' ? String(w) : null
}

/** Projected + played rows for a two-game semifinal round after a prior round. */
export function buildTwoGameRoundRows(
  priorGames: PlayoffGameRow[],
  priorPairs: PlayoffMatchup[],
  roundGames: PlayoffGameRow[],
): PlayoffGameRow[] {
  const w = (i: number) => winnerByIndex(priorGames, priorPairs, i)
  const proj = (which: 1 | 2): PlayoffGameRow => {
    if (which === 1) {
      return { home: w(0) ?? 'TBD', away: w(3) ?? 'TBD', home_score: null, away_score: null, projected: true }
    }
    return { home: w(1) ?? 'TBD', away: w(2) ?? 'TBD', home_score: null, away_score: null, projected: true }
  }
  const matches1 = (g: PlayoffGameRow) => {
    const a = w(0),
      b = w(3)
    if (!a || !b) return false
    return (g.home === a && g.away === b) || (g.home === b && g.away === a)
  }
  const matches2 = (g: PlayoffGameRow) => {
    const a = w(1),
      b = w(2)
    if (!a || !b) return false
    return (g.home === a && g.away === b) || (g.home === b && g.away === a)
  }
  if (roundGames.length >= 2) return roundGames.map((g) => ({ ...g, projected: false }))
  if (roundGames.length === 1) {
    const g = roundGames[0]
    if (matches1(g)) return [g, proj(2)]
    if (matches2(g)) return [proj(1), g]
    return [g, proj(2)]
  }
  return [proj(1), proj(2)]
}

export function buildChampionshipRow(sfRows: PlayoffGameRow[], chGames: PlayoffGameRow[]): PlayoffGameRow | null {
  if (chGames.length) return { ...chGames[0], projected: false }
  if (sfRows.length === 2) {
    const w1 = sfRows[0]?.winner
    const w2 = sfRows[1]?.winner
    if (w1 && w2) {
      return {
        home: String(w1),
        away: String(w2),
        home_score: null,
        away_score: null,
        projected: true,
      }
    }
  }
  if (sfRows.length === 1 && sfRows[0]?.winner) {
    return {
      home: String(sfRows[0].winner),
      away: 'TBD',
      home_score: null,
      away_score: null,
      projected: true,
    }
  }
  return { home: 'TBD', away: 'TBD', home_score: null, away_score: null, projected: true }
}

export type PlayoffRoundColumn = {
  title: string
  roundKey: string
  pairs: PlayoffMatchup[]
  games: PlayoffGameRow[]
  rows: PlayoffGameRow[]
}

export type RegionalPlayoffView = {
  isRegional: true
  regions: string[]
  selectedRegion: string
  teamsPerRegion: number
  inRegionColumns: PlayoffRoundColumn[]
  stateSfRows: PlayoffGameRow[]
  stateChRow: PlayoffGameRow | null
}

export function buildRegionalPlayoffSlice(
  seeds: PlayoffSeedRow[],
  results: PlayoffGameRow[],
  region: string,
): { inRegionColumns: PlayoffRoundColumn[]; stateSfRows: PlayoffGameRow[]; stateChRow: PlayoffGameRow | null } {
  const regionSeeds = seeds
    .filter((s) => String(s.region) === region)
    .sort((a, b) => Number(a.seed) - Number(b.seed))
  const regionTeams = new Set(regionSeeds.map((s) => String(s.team)))
  const inRoundNames = regionalInRegionRoundNames(regionSeeds.length)

  const gamesInRegion = (roundName: string) =>
    results.filter(
      (g) =>
        String(g.round || '') === roundName &&
        regionTeams.has(String(g.home)) &&
        regionTeams.has(String(g.away)),
    )

  const shortTitle = (name: string) => name.replace(/^Regional /, 'Reg. ')

  const inRegionColumns: PlayoffRoundColumn[] = []
  let priorPairs = firstRoundPairsFromOrderedTeams(regionSeeds.map((s) => String(s.team)))
  let priorRoundGames: PlayoffGameRow[] = []

  for (let ri = 0; ri < inRoundNames.length; ri++) {
    const roundName = inRoundNames[ri]
    const games = gamesInRegion(roundName)
    const isFirst = ri === 0
    const isLast = ri === inRoundNames.length - 1

    if (isFirst) {
      inRegionColumns.push({
        title: shortTitle(roundName),
        roundKey: roundName,
        pairs: priorPairs,
        games,
        rows: [],
      })
      priorRoundGames = games
      continue
    }

    if (isLast) {
      const prevRoundName = inRoundNames[ri - 1]
      const prevRows = buildTwoGameRoundRows(priorRoundGames, priorPairs, gamesInRegion(prevRoundName))
      const row = buildChampionshipRow(prevRows, games)
      inRegionColumns.push({
        title: shortTitle(roundName),
        roundKey: roundName,
        pairs: [],
        games,
        rows: row ? [row] : [],
      })
      continue
    }

    const rows = buildTwoGameRoundRows(priorRoundGames, priorPairs, games)
    inRegionColumns.push({
      title: shortTitle(roundName),
      roundKey: roundName,
      pairs: [],
      games,
      rows,
    })
    priorPairs = rows.map((r) => ({ home: String(r.home), away: String(r.away) }))
    priorRoundGames = games
  }

  const { stateSfRows, stateChRow } = buildStatePlayoffFromResults(results)
  return { inRegionColumns, stateSfRows, stateChRow }
}

/** State semifinal + championship only (Final Four view). */
export function buildStatePlayoffFromResults(results: PlayoffGameRow[]): {
  stateSfRows: PlayoffGameRow[]
  stateChRow: PlayoffGameRow | null
} {
  const stateSf = results.filter((g) => String(g.round || '') === 'Semifinal')
  const stateCh = results.filter((g) => String(g.round || '') === 'Championship')
  const stateSfRows = stateSf.length
    ? stateSf.map((g) => ({ ...g, projected: false }))
    : buildTwoGameRoundRows([], [], [])
  const stateChRow = buildChampionshipRow(stateSfRows, stateCh)
  return { stateSfRows, stateChRow }
}
