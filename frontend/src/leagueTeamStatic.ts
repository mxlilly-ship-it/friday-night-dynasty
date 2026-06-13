import type { TeamsDataResponse } from './newSaveTypes'

export type LeagueTeamStaticRow = {
  stadium_name?: string
  rivals?: string[]
}

export function buildLeagueTeamStaticLookup(
  data: TeamsDataResponse | null | undefined,
): Map<string, LeagueTeamStaticRow> {
  const lookup = new Map<string, LeagueTeamStaticRow>()
  for (const t of data?.teams ?? []) {
    const name = String(t?.name ?? '').trim()
    if (!name) continue
    const row: LeagueTeamStaticRow = {}
    const stadium = String(t?.stadium_name ?? '').trim()
    if (stadium) row.stadium_name = stadium
    if (Array.isArray(t?.rivals) && t.rivals.length) {
      row.rivals = t.rivals.map((x) => String(x).trim()).filter(Boolean)
    }
    if (row.stadium_name || row.rivals?.length) lookup.set(name, row)
  }
  return lookup
}

/** Backfill stadium_name / rivals from teams.json when missing on save rows. */
export function enrichSaveTeamsFromLeagueJson(
  state: any,
  lookup: Map<string, LeagueTeamStaticRow>,
): boolean {
  const teams = state?.teams
  if (!Array.isArray(teams) || lookup.size === 0) return false
  let changed = false
  for (const t of teams) {
    if (!t || typeof t !== 'object') continue
    const name = String((t as { name?: string }).name ?? '').trim()
    const src = lookup.get(name)
    if (!src) continue
    const row = t as { stadium_name?: string; rivals?: string[] }
    if (!String(row.stadium_name ?? '').trim() && src.stadium_name) {
      row.stadium_name = src.stadium_name
      changed = true
    }
    if ((!row.rivals || row.rivals.length === 0) && src.rivals?.length) {
      row.rivals = [...src.rivals]
      changed = true
    }
  }
  return changed
}

let cachedLookup: Map<string, LeagueTeamStaticRow> | null = null
let cachePromise: Promise<Map<string, LeagueTeamStaticRow>> | null = null

export async function fetchLeagueTeamStaticLookup(
  apiBase: string,
): Promise<Map<string, LeagueTeamStaticRow>> {
  if (cachedLookup) return cachedLookup
  if (cachePromise) return cachePromise
  cachePromise = (async () => {
    const r = await fetch(`${apiBase.replace(/\/$/, '')}/teams-data`)
    if (!r.ok) return new Map<string, LeagueTeamStaticRow>()
    const data = (await r.json()) as TeamsDataResponse
    cachedLookup = buildLeagueTeamStaticLookup(data)
    return cachedLookup
  })()
  try {
    return await cachePromise
  } finally {
    cachePromise = null
  }
}

export async function enrichSaveStateFromLeagueJson(state: any, apiBase: string): Promise<boolean> {
  const lookup = await fetchLeagueTeamStaticLookup(apiBase)
  return enrichSaveTeamsFromLeagueJson(state, lookup)
}
