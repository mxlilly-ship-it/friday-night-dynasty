/**
 * Coach fields aligned with systems/save_system.py `coach_to_dict`.
 */
export const COACH_SKILL_KEYS = [
  { key: 'playcalling', label: 'Playcalling' },
  { key: 'player_development', label: 'Player development' },
  { key: 'community_outreach', label: 'Community outreach' },
  { key: 'culture', label: 'Culture' },
  { key: 'recruiting', label: 'Recruiting' },
  { key: 'scheme_teach', label: 'Scheme teach' },
] as const

export const COACH_ATTRIBUTE_GROUPS: ReadonlyArray<{ title: string; rows: ReadonlyArray<{ key: string; label: string }> }> = [
  {
    title: 'Identity',
    rows: [
      { key: 'name', label: 'Name' },
      { key: 'age', label: 'Age' },
      { key: 'years_at_school', label: 'Years at school' },
      { key: 'years_since_scheme_change', label: 'Years since scheme change' },
    ],
  },
  {
    title: 'Philosophy',
    rows: [
      { key: 'offensive_style', label: 'Offensive style' },
      { key: 'defensive_style', label: 'Defensive style' },
    ],
  },
  {
    title: 'Playbooks',
    rows: [
      { key: 'offensive_formation', label: 'Offensive playbook' },
      { key: 'defensive_formation', label: 'Defensive playbook' },
    ],
  },
  {
    title: 'Skills (1–10)',
    rows: [...COACH_SKILL_KEYS],
  },
  {
    title: 'Offseason focus',
    rows: [
      { key: 'winter_strength_pct', label: 'Winter strength %' },
      { key: 'spring_offense_focus', label: 'Spring offense' },
      { key: 'spring_defense_focus', label: 'Spring defense' },
    ],
  },
]

export function formatCoachAttributeCell(c: any, key: string): string {
  if (!c || typeof c !== 'object') return '—'
  const v = c[key]
  if (v === null || v === undefined || v === '') return '—'
  if (key === 'preferred_schemes') {
    if (v && typeof v === 'object' && Object.keys(v).length === 0) return '—'
    try {
      return JSON.stringify(v)
    } catch {
      return '—'
    }
  }
  if (typeof v === 'boolean') return v ? 'Y' : 'N'
  if (typeof v === 'number') {
    if (!Number.isFinite(v)) return '—'
    if (key === 'winter_strength_pct') return `${Math.round(v)}%`
    return Number.isInteger(v) ? String(v) : v.toFixed(1)
  }
  return String(v)
}
