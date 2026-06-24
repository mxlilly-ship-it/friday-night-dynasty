/** Coach CP economy — mirrors systems/coach_development.py */

export const COACH_DEV_SKILLS = [
  { key: 'playcalling', label: 'Playcalling' },
  { key: 'player_development', label: 'Player development' },
  { key: 'community_outreach', label: 'Community outreach' },
  { key: 'culture', label: 'Culture' },
  { key: 'recruiting', label: 'Recruiting' },
  { key: 'scheme_teach', label: 'Scheme teach' },
] as const

export const COACH_DEV_THRESHOLDS: Record<number, number> = {
  1: 0,
  2: 12,
  3: 28,
  4: 48,
  5: 72,
  6: 100,
  7: 135,
  8: 175,
  9: 220,
  10: 270,
}

export const CREATION_BONUS_CP_DEFAULT = 60
export const CREATION_BONUS_CP_LOW_PRESTIGE = 80
export const CREATION_BONUS_LOW_PRESTIGE_MAX = 5

export function creationBonusCpForPrestige(prestige: number | null | undefined): number {
  const p = Number(prestige ?? 5)
  return p <= CREATION_BONUS_LOW_PRESTIGE_MAX ? CREATION_BONUS_CP_LOW_PRESTIGE : CREATION_BONUS_CP_DEFAULT
}

export function coachDevLevelFromCp(cp: number): number {
  let level = 1
  for (let i = 1; i <= 10; i++) {
    if (cp >= (COACH_DEV_THRESHOLDS[i] ?? 0)) level = i
  }
  return level
}

export function coachDevNextThreshold(level: number): number | null {
  if (level >= 10) return null
  return COACH_DEV_THRESHOLDS[level + 1] ?? null
}

export function coachDevCpToNextLevel(cp: number): { current: number; next: number; remaining: number } | null {
  const lv = coachDevLevelFromCp(cp)
  const next = coachDevNextThreshold(lv)
  if (next == null) return null
  return { current: COACH_DEV_THRESHOLDS[lv] ?? 0, next, remaining: Math.max(0, next - cp) }
}

export function coachDevAllocatedFromLevels(levels: Record<string, number>): Record<string, number> {
  return Object.fromEntries(
    COACH_DEV_SKILLS.map(({ key }) => {
      const lv = Math.max(1, Math.min(10, Number(levels[key] ?? 5)))
      return [key, COACH_DEV_THRESHOLDS[lv] ?? 0]
    }),
  )
}

export type CoachDevBreakdown = {
  base_cp?: number
  record_cp?: number
  wins_cp?: number
  losses_cp?: number
  playoffs_bonus?: number
  postseason_tier?: string
  goal_cp?: number
  loyalty_bonus?: number
  losing_season_penalty?: number
  age_modifier?: number
  cp_change?: number
  prior_cp_total?: number
  win_goal_met?: boolean
  stage_goal_met?: boolean
  wins?: number
  losses?: number
}

export function formatCoachCpDelta(n: number): string {
  const v = Math.round(Number(n) * 10) / 10
  if (v > 0) return `+${v}`
  return String(v)
}
