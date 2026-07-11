export type AllStatePlayerEntry = {
  position: string
  name: string
  team: string
  classification?: string
  score?: number
  stats?: Record<string, number>
}

export type AllStateClassBlock = {
  first_team?: AllStatePlayerEntry[]
  second_team?: AllStatePlayerEntry[]
  honorable_mention?: AllStatePlayerEntry[]
}

export type SeasonAwards = {
  player_of_the_year?: { name?: string; team?: string; classification?: string } | null
  offensive_player_of_the_year?: { name?: string; team?: string; classification?: string } | null
  defensive_player_of_the_year?: { name?: string; team?: string; classification?: string } | null
  all_state_by_class?: Record<string, AllStateClassBlock>
  all_state_first_team?: AllStatePlayerEntry[]
}

const OFFENSE_ORDER = ['QB', 'RB', 'WR', 'TE', 'OL', 'K', 'P']
const DEFENSE_ORDER = ['DL', 'LB', 'DB']

export function awardsFromSeasonEntry(season: unknown): SeasonAwards | null {
  if (!season || typeof season !== 'object') return null
  const s = season as Record<string, unknown>
  const nested = s.awards
  if (nested && typeof nested === 'object') return nested as SeasonAwards
  return null
}

export function listAwardClasses(awards: SeasonAwards | null | undefined): string[] {
  const by = awards?.all_state_by_class
  if (!by || typeof by !== 'object') return []
  return Object.keys(by).sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
}

export function userAllStatePicks(
  awards: SeasonAwards | null | undefined,
  userTeam: string,
): AllStatePlayerEntry[] {
  const team = String(userTeam || '').trim()
  if (!team || !awards?.all_state_by_class) return []
  const out: AllStatePlayerEntry[] = []
  for (const block of Object.values(awards.all_state_by_class)) {
    if (!block) continue
    for (const tier of ['first_team', 'second_team', 'honorable_mention'] as const) {
      for (const e of block[tier] ?? []) {
        if (String(e.team || '') === team) out.push(e)
      }
    }
  }
  return out
}

export function sortAllStateEntries(entries: AllStatePlayerEntry[]): AllStatePlayerEntry[] {
  const rank = (pos: string) => {
    const p = pos.toUpperCase()
    const oi = OFFENSE_ORDER.indexOf(p)
    if (oi >= 0) return oi
    const di = DEFENSE_ORDER.indexOf(p)
    if (di >= 0) return OFFENSE_ORDER.length + di
    return 99
  }
  return [...entries].sort((a, b) => rank(a.position) - rank(b.position) || a.name.localeCompare(b.name))
}

export function statLineForEntry(entry: AllStatePlayerEntry): string {
  const pos = String(entry.position || '').toUpperCase()
  const s = entry.stats ?? {}
  if (pos === 'QB') return `${s.pass_yds ?? 0} pass yds, ${s.pass_td ?? 0} TD`
  if (pos === 'RB') return `${s.rush_yds ?? 0} rush yds, ${s.rush_td ?? 0} TD`
  if (pos === 'WR' || pos === 'TE') return `${s.rec_yds ?? 0} rec yds, ${s.rec_td ?? 0} TD`
  if (pos === 'K') return `${s.fg_made ?? 0}/${s.fg_att ?? 0} FG, ${s.xp_made ?? 0} XP`
  if (pos === 'P') {
    const punts = Number(s.punts ?? 0)
    const py = Number(s.punt_yards ?? 0)
    const avg = punts > 0 ? (py / punts).toFixed(1) : '0'
    return `${avg} avg (${punts} punts)`
  }
  if (pos === 'OL') return 'Starting OL'
  return `${s.tackles ?? 0} tkl, ${s.sacks ?? 0} sk, ${s.interceptions ?? 0} INT`
}
