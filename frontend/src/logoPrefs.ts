/** True when the dynasty uses built-in data/teams.json (not an uploaded league JSON). */
export function saveUsesDefaultLeagueLogos(state: unknown): boolean {
  if (!state || typeof state !== 'object') return true
  return !(state as { custom_league_json?: boolean }).custom_league_json
}
