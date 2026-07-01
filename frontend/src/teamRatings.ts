/** Roster-derived team ratings — mirrors ``systems/team_ratings.py`` for local saves; API is authoritative online. */

export type TeamRatingRow = {
  teamName: string
  classification: string
  region: string
  wins: number
  losses: number
  overall: number
  offense: number
  defense: number
  run: number
  pass: number
}

const STARTER_COUNT = 11
const STARTER_WEIGHT = 2.0
const BACKUP_WEIGHT = 0.5

const COMMUNITY_TALENT_POOL: Record<string, number> = {
  rural: 4,
  urban: 8,
  suburban: 7,
  affluent: 6,
  'blue-collar': 7,
  'football factory': 9,
}

function num(v: unknown, fallback = 50): number {
  const n = Number(v)
  return Number.isFinite(n) ? n : fallback
}

function talentPoolForCommunity(raw: unknown): number {
  const key = String(raw ?? '')
    .trim()
    .toLowerCase()
  return COMMUNITY_TALENT_POOL[key] ?? 5
}

function prestigeCommunityMultiplier(prestige: number, talentPool: number): number {
  const mult = 0.82 + (prestige - 3) * 0.04 + (talentPool - 4) * 0.05
  return Math.max(0.75, Math.min(1.6, mult))
}

function clampRating(v: number): number {
  return Math.max(20, Math.min(95, Math.round(v)))
}

function playerOffenseContribution(p: Record<string, unknown>): number {
  const pos = String(p.position ?? '')
  const sec = String(p.secondary_position ?? '')
  if (pos === 'QB') {
    return (num(p.throw_power) + num(p.throw_accuracy) + num(p.decisions) + num(p.football_iq)) / 4
  }
  if (pos === 'RB') {
    return (num(p.speed) + num(p.break_tackle) + num(p.vision) + num(p.ball_security) + num(p.catching)) / 5
  }
  if (pos === 'WR' || pos === 'TE') {
    return (num(p.catching) + num(p.route_running) + num(p.speed) + num(p.agility)) / 4
  }
  if (pos === 'OL') {
    return (num(p.run_blocking) + num(p.pass_blocking) + num(p.strength)) / 3
  }
  if (sec === 'RB' || sec === 'WR' || sec === 'TE') {
    return ((num(p.catching) + num(p.speed) + num(p.vision)) / 3) * 0.5
  }
  return 0
}

function playerDefenseContribution(p: Record<string, unknown>): number {
  const pos = String(p.position ?? '')
  const sec = String(p.secondary_position ?? '')
  if (pos === 'DE' || pos === 'DT') {
    return (num(p.pass_rush) + num(p.run_defense) + num(p.block_shedding) + num(p.strength)) / 4
  }
  if (pos === 'LB') {
    return (num(p.tackling) + num(p.pursuit) + num(p.coverage) + num(p.run_defense)) / 4
  }
  if (pos === 'CB' || pos === 'S') {
    return (num(p.coverage) + num(p.speed) + num(p.agility) + num(p.tackling)) / 4
  }
  if (sec === 'DE' || sec === 'DT' || sec === 'LB' || sec === 'CB' || sec === 'S') {
    return ((num(p.tackling) + num(p.coverage) + num(p.speed)) / 3) * 0.5
  }
  return 0
}

function playerRunContribution(p: Record<string, unknown>): number {
  const pos = String(p.position ?? '')
  if (pos === 'QB') return ((num(p.speed) + num(p.agility) + num(p.elusiveness)) / 3) * 0.3
  if (pos === 'RB') return (num(p.speed) + num(p.break_tackle) + num(p.vision) + num(p.strength)) / 4
  if (pos === 'WR' || pos === 'TE') return num(p.run_blocking) * 0.5
  if (pos === 'OL') return (num(p.run_blocking) + num(p.strength)) / 2
  return 0
}

function playerPassContribution(p: Record<string, unknown>): number {
  const pos = String(p.position ?? '')
  if (pos === 'QB') return (num(p.throw_power) + num(p.throw_accuracy) + num(p.decisions)) / 3
  if (pos === 'WR' || pos === 'TE') return (num(p.catching) + num(p.route_running) + num(p.speed)) / 3
  if (pos === 'RB') return num(p.catching) * 0.5
  if (pos === 'OL') return (num(p.pass_blocking) + num(p.strength)) / 2
  return 0
}

function weightedAvgStarters(vals: number[], sortKeys: number[]): number {
  if (!vals.length) return 50
  const paired = vals.map((v, i) => ({ v, k: sortKeys[i] ?? v }))
  paired.sort((a, b) => b.k - a.k)
  const weights = [
    ...Array(Math.min(STARTER_COUNT, paired.length)).fill(STARTER_WEIGHT),
    ...Array(Math.max(0, paired.length - STARTER_COUNT)).fill(BACKUP_WEIGHT),
  ]
  let total = 0
  let denom = 0
  for (let i = 0; i < paired.length; i++) {
    total += paired[i].v * weights[i]
    denom += weights[i]
  }
  return denom > 0 ? total / denom : 50
}

function calculateTeamRatingsForTeam(team: Record<string, unknown>): {
  offense: number
  defense: number
  run: number
  pass: number
} {
  const roster = Array.isArray(team.roster) ? team.roster : []
  if (!roster.length) {
    return { offense: 50, defense: 50, run: 50, pass: 50 }
  }

  const items = roster
    .filter((p): p is Record<string, unknown> => p && typeof p === 'object')
    .map((p) => ({
      o: playerOffenseContribution(p),
      d: playerDefenseContribution(p),
      r: playerRunContribution(p),
      p: playerPassContribution(p),
    }))

  const offItems = items.filter((x) => x.o > 0)
  const defItems = items.filter((x) => x.d > 0)
  const runItems = items.filter((x) => x.r > 0)
  const passItems = items.filter((x) => x.p > 0)

  let offense = weightedAvgStarters(
    offItems.map((x) => x.o),
    offItems.map((x) => x.o),
  )
  let defense = weightedAvgStarters(
    defItems.map((x) => x.d),
    defItems.map((x) => x.d),
  )
  let run = weightedAvgStarters(
    runItems.map((x) => x.r),
    runItems.map((x) => x.r),
  )
  let pass = weightedAvgStarters(
    passItems.map((x) => x.p),
    passItems.map((x) => x.p),
  )

  const prestige = num(team.prestige, 5)
  const talentPool = talentPoolForCommunity(team.community_type ?? team.community)
  const mult = prestigeCommunityMultiplier(prestige, talentPool)
  offense *= mult
  defense *= mult
  run *= mult
  pass *= mult

  return {
    offense: clampRating(offense),
    defense: clampRating(defense),
    run: clampRating(run),
    pass: clampRating(pass),
  }
}

function teamCompositeStrength(ratings: { offense: number; defense: number }): number {
  return Math.round((ratings.offense + ratings.defense) / 2)
}

function parseApiRow(raw: Record<string, unknown>): TeamRatingRow | null {
  const teamName = String(raw.team_name ?? '').trim()
  if (!teamName) return null
  return {
    teamName,
    classification: String(raw.classification ?? '—').trim() || '—',
    region: String(raw.region ?? '—').trim() || '—',
    wins: num(raw.wins, 0),
    losses: num(raw.losses, 0),
    overall: num(raw.overall, 50),
    offense: num(raw.offense, 50),
    defense: num(raw.defense, 50),
    run: num(raw.run, 50),
    pass: num(raw.pass, 50),
  }
}

/** Client-side ratings from in-memory save state (local bundle / offline fallback). */
export function buildTeamRatingsFromSaveState(saveState: any): TeamRatingRow[] {
  const standings = saveState?.standings && typeof saveState.standings === 'object' ? saveState.standings : {}
  const rows: TeamRatingRow[] = []
  for (const t of saveState?.teams ?? []) {
    if (!t || typeof t !== 'object') continue
    const teamName = String((t as { name?: unknown }).name ?? '').trim()
    if (!teamName) continue
    const ratings = calculateTeamRatingsForTeam(t as Record<string, unknown>)
    const st = standings[teamName]
    const stObj = st && typeof st === 'object' ? st : {}
    rows.push({
      teamName,
      classification: String((t as { classification?: unknown }).classification ?? '—').trim() || '—',
      region: String((t as { region?: unknown }).region ?? '—').trim() || '—',
      wins: num((stObj as { wins?: unknown }).wins, 0),
      losses: num((stObj as { losses?: unknown }).losses, 0),
      overall: teamCompositeStrength(ratings),
      offense: ratings.offense,
      defense: ratings.defense,
      run: ratings.run,
      pass: ratings.pass,
    })
  }
  rows.sort((a, b) => {
    if (b.overall !== a.overall) return b.overall - a.overall
    if (b.offense !== a.offense) return b.offense - a.offense
    return a.teamName.localeCompare(b.teamName)
  })
  return rows
}

export async function fetchTeamRatings(opts: {
  apiBase: string
  saveId: string
  headers?: Record<string, string>
}): Promise<TeamRatingRow[]> {
  const hdrs = opts.headers?.Authorization ? opts.headers : {}
  const r = await fetch(`${opts.apiBase}/saves/${opts.saveId}/team-ratings`, { headers: hdrs })
  if (!r.ok) throw new Error(await r.text())
  const j = await r.json()
  const list = Array.isArray(j?.teams) ? j.teams : []
  const rows: TeamRatingRow[] = []
  for (const raw of list) {
    if (!raw || typeof raw !== 'object') continue
    const row = parseApiRow(raw as Record<string, unknown>)
    if (row) rows.push(row)
  }
  return rows
}

export function filterTeamRatingsByClass(rows: TeamRatingRow[], classFilter: string | 'all'): TeamRatingRow[] {
  if (classFilter === 'all') return rows
  return rows.filter((r) => r.classification === classFilter)
}

export function ratingsForTeam(rows: TeamRatingRow[], teamName: string): TeamRatingRow | null {
  const want = String(teamName ?? '').trim()
  if (!want) return null
  return rows.find((r) => r.teamName === want) ?? null
}
