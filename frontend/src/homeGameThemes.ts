/** Home game theme nights — mirrors ``systems/home_game_themes.py``. */

export type HomeThemeGroup =
  | 'school_community'
  | 'legacy'
  | 'community_service'
  | 'fan_experience'

export type HomeThemeDef = {
  id: string
  label: string
  pp: number
  cash: number
  group: HomeThemeGroup
}

export const HOME_THEME_GROUP_LABELS: Record<HomeThemeGroup, string> = {
  school_community: 'School / community',
  legacy: 'Legacy / program history',
  community_service: 'Community service / honor',
  fan_experience: 'Fan experience / atmosphere',
}

export const HOME_THEME_CATALOG: HomeThemeDef[] = [
  { id: 'youth_night', label: 'Youth Night', pp: 150, cash: 0, group: 'school_community' },
  { id: 'elementary_night', label: 'Elementary Night', pp: 0, cash: 500, group: 'school_community' },
  { id: 'teacher_appreciation_night', label: 'Teacher Appreciation Night', pp: 100, cash: 0, group: 'school_community' },
  { id: 'senior_night', label: 'Senior Night', pp: 200, cash: 0, group: 'school_community' },
  { id: 'homecoming', label: 'Homecoming', pp: 300, cash: 2500, group: 'school_community' },
  { id: 'spirit_night', label: 'Spirit Night', pp: 200, cash: 0, group: 'school_community' },
  { id: 'alumni_night', label: 'Alumni Night', pp: 0, cash: 2000, group: 'legacy' },
  { id: 'hall_of_fame_night', label: 'Hall of Fame Night', pp: 200, cash: 0, group: 'legacy' },
  { id: 'championship_anniversary_night', label: 'Championship Anniversary Night', pp: 0, cash: 1500, group: 'legacy' },
  { id: 'jersey_retirement_night', label: 'Jersey Retirement Night', pp: 200, cash: 0, group: 'legacy' },
  { id: 'decade_night', label: 'Decade Night (80s, 90s, etc.)', pp: 100, cash: 0, group: 'legacy' },
  { id: 'legends_night', label: 'Legends Night', pp: 0, cash: 1000, group: 'legacy' },
  { id: 'military_appreciation_night', label: 'Military Appreciation Night', pp: 0, cash: 2000, group: 'community_service' },
  { id: 'first_responders_night', label: 'First Responders Night', pp: 300, cash: 0, group: 'community_service' },
  { id: 'healthcare_workers_night', label: 'Healthcare Workers Night', pp: 200, cash: 0, group: 'community_service' },
  { id: 'community_heroes_night', label: 'Community Heroes Night', pp: 200, cash: 0, group: 'community_service' },
  { id: 'local_nonprofit_night', label: 'Local Nonprofit Night', pp: 0, cash: 1500, group: 'community_service' },
  { id: 'cancer_awareness_night', label: 'Cancer Awareness Night', pp: 200, cash: 0, group: 'community_service' },
  { id: 'white_out', label: 'White Out', pp: 150, cash: 0, group: 'fan_experience' },
  { id: 'blackout', label: 'Blackout', pp: 150, cash: 0, group: 'fan_experience' },
  { id: 'stripe_out', label: 'Stripe Out', pp: 150, cash: 0, group: 'fan_experience' },
  { id: 'neon_night', label: 'Neon Night', pp: 150, cash: 0, group: 'fan_experience' },
  { id: 'rivalry_night', label: 'Rivalry Night', pp: 0, cash: 4000, group: 'fan_experience' },
]

const THEME_BY_ID = new Map(HOME_THEME_CATALOG.map((t) => [t.id, t]))

export function gameSlotKey(week: number, gameIndex: number): string {
  return `${week}:${gameIndex}`
}

export function themeById(id: string | null | undefined): HomeThemeDef | undefined {
  const tid = String(id || '').trim()
  return tid ? THEME_BY_ID.get(tid) : undefined
}

export function themeRewardSummary(theme: HomeThemeDef): string {
  if (theme.pp > 0 && theme.cash > 0) return `${theme.pp} PP or $${theme.cash.toLocaleString()}`
  if (theme.pp > 0) return `${theme.pp} PP`
  if (theme.cash > 0) return `$${theme.cash.toLocaleString()}`
  return ''
}

export function themeOffersBoth(themeId: string): boolean {
  const t = themeById(themeId)
  return Boolean(t && t.pp > 0 && t.cash > 0)
}

export function themesByGroup(): Array<{ group: HomeThemeGroup; label: string; themes: HomeThemeDef[] }> {
  const order: HomeThemeGroup[] = ['school_community', 'legacy', 'community_service', 'fan_experience']
  return order.map((group) => ({
    group,
    label: HOME_THEME_GROUP_LABELS[group],
    themes: HOME_THEME_CATALOG.filter((t) => t.group === group),
  }))
}

export type UserHomeGameSlot = {
  week: number
  game_index: number
  opponent: string
  slot_key: string
}

export function listUserHomeGames(saveState: any, userTeam: string): UserHomeGameSlot[] {
  const tn = String(userTeam || '').trim()
  if (!tn) return []
  const weeks = saveState?.weeks ?? []
  const out: UserHomeGameSlot[] = []
  for (let wi = 0; wi < weeks.length; wi++) {
    const wk = weeks[wi] ?? []
    for (let gi = 0; gi < wk.length; gi++) {
      const g = wk[gi]
      if (!g || g.home !== tn) continue
      out.push({
        week: wi + 1,
        game_index: gi,
        opponent: String(g.away ?? '—'),
        slot_key: gameSlotKey(wi + 1, gi),
      })
    }
  }
  return out
}

export function themeLabelForGame(
  saveState: any,
  teamName: string,
  week: number,
  gameIndex: number,
): string | null {
  const tn = String(teamName || '').trim()
  if (!tn) return null
  const store = saveState?.home_game_themes
  if (!store || typeof store !== 'object') return null
  const teamMap = (store as Record<string, unknown>)[tn]
  if (!teamMap || typeof teamMap !== 'object') return null
  const entry = (teamMap as Record<string, { theme_id?: string }>)[gameSlotKey(week, gameIndex)]
  if (!entry?.theme_id) return null
  return themeById(entry.theme_id)?.label ?? entry.theme_id
}

export type HomeThemeSelection = {
  week: number
  game_index: number
  theme_id: string
  reward_choice?: 'pp' | 'cash'
}

export function readUserThemeDraft(saveState: any, userTeam: string): Record<string, HomeThemeSelection> {
  const out: Record<string, HomeThemeSelection> = {}
  const tn = String(userTeam || '').trim()
  const store = saveState?.home_game_themes?.[tn]
  if (!store || typeof store !== 'object') return out
  for (const [slot, raw] of Object.entries(store as Record<string, unknown>)) {
    if (!raw || typeof raw !== 'object') continue
    const parsed = parseGameSlotKey(slot)
    if (!parsed) continue
    const theme_id = String((raw as { theme_id?: string }).theme_id || '').trim()
    if (!theme_id) continue
    const rc = (raw as { reward_choice?: string }).reward_choice
    out[slot] = {
      week: parsed[0],
      game_index: parsed[1],
      theme_id,
      reward_choice: rc === 'pp' || rc === 'cash' ? rc : undefined,
    }
  }
  return out
}

function parseGameSlotKey(key: string): [number, number] | null {
  const parts = String(key || '').split(':')
  if (parts.length !== 2) return null
  const week = Number(parts[0])
  const gi = Number(parts[1])
  if (!Number.isFinite(week) || !Number.isFinite(gi)) return null
  return [week, gi]
}

export function draftToPayload(draft: Record<string, HomeThemeSelection>): HomeThemeSelection[] {
  return Object.values(draft).filter((row) => row.theme_id)
}

export type HomeThemeSeasonGame = {
  week: number
  opponent: string
  theme_label: string
  won: boolean | null
  earned: boolean
  pp: number
  cash: number
  reward_choice?: string
}

export type HomeThemeSeasonSummary = {
  pp_total: number
  cash_total: number
  games: HomeThemeSeasonGame[]
}

export function userHomeThemeSummary(saveState: any, userTeam: string): HomeThemeSeasonSummary | null {
  const tn = String(userTeam || '').trim()
  if (!tn) return null
  const raw = saveState?.home_theme_season_rewards?.[tn]
  if (!raw || typeof raw !== 'object') return null
  return raw as HomeThemeSeasonSummary
}
