/**
 * Player attribute columns aligned with systems/save_system.py `player_to_dict`
 * (excluding name — shown separately; position / secondary shown in roster “Position” column).
 */
export const PLAYER_ATTRIBUTE_COLUMNS: ReadonlyArray<{ key: string; label: string }> = [
  { key: 'height', label: 'Ht' },
  { key: 'weight', label: 'Wt' },
  { key: 'frame', label: 'Frm' },
  { key: 'speed', label: 'SPD' },
  { key: 'agility', label: 'AGI' },
  { key: 'acceleration', label: 'ACC' },
  { key: 'strength', label: 'STR' },
  { key: 'balance', label: 'BAL' },
  { key: 'jumping', label: 'JMP' },
  { key: 'stamina', label: 'STA' },
  { key: 'injury', label: 'INJ' },
  { key: 'toughness', label: 'Tgh' },
  { key: 'effort', label: 'Eff' },
  { key: 'football_iq', label: 'IQ' },
  { key: 'coachability', label: 'Coa' },
  { key: 'confidence', label: 'Cnf' },
  { key: 'discipline', label: 'Dsc' },
  { key: 'leadership', label: 'Ldr' },
  { key: 'composure', label: 'Cmp' },
  { key: 'throw_power', label: 'THP' },
  { key: 'throw_accuracy', label: 'THA' },
  { key: 'decisions', label: 'Dec' },
  { key: 'catching', label: 'CTH' },
  { key: 'run_blocking', label: 'RBK' },
  { key: 'pass_blocking', label: 'PBK' },
  { key: 'vision', label: 'Vis' },
  { key: 'ball_security', label: 'Car' },
  { key: 'break_tackle', label: 'BTK' },
  { key: 'elusiveness', label: 'Elu' },
  { key: 'route_running', label: 'RTE' },
  { key: 'coverage', label: 'CV' },
  { key: 'blitz', label: 'Blz' },
  { key: 'pass_rush', label: 'PR' },
  { key: 'run_defense', label: 'RDF' },
  { key: 'pursuit', label: 'Purs' },
  { key: 'tackling', label: 'Tck' },
  { key: 'block_shedding', label: 'BSh' },
  { key: 'kick_power', label: 'KP' },
  { key: 'kick_accuracy', label: 'KA' },
  { key: 'potential', label: 'Pot' },
  { key: 'growth_rate', label: 'Grw' },
  { key: 'peak_age', label: 'PkAge' },
  { key: 'consistency', label: 'Con' },
  { key: 'late_bloomer', label: 'Late' },
  { key: 'early_bloomer', label: 'Early' },
  { key: 'age', label: 'Age' },
  { key: 'year', label: 'Yr#' },
]

/** Attribute columns rendered in the horizontal scroll strip (Ht/Wt are fixed columns on roster/depth). */
export const PLAYER_ATTRIBUTE_COLUMNS_SCROLL = PLAYER_ATTRIBUTE_COLUMNS.filter(
  (c) => c.key !== 'height' && c.key !== 'weight',
)

/** Total inches → feet'inches\" (e.g. 70 → 5'10\"). */
export function formatHeightInches(totalInches: unknown): string {
  const n = Number(totalInches)
  if (!Number.isFinite(n)) return '—'
  const inches = Math.round(n)
  const ft = Math.floor(inches / 12)
  const inch = inches % 12
  return `${ft}'${inch}"`
}

export function formatWeightLbs(lbs: unknown): string {
  const n = Number(lbs)
  if (!Number.isFinite(n)) return '—'
  return `${Math.round(n)}`
}

/** One-line size for sublabels (roster cards, depth starters). */
export function formatPlayerMeasureLine(p: any): string {
  const h = formatHeightInches(p?.height)
  const w = formatWeightLbs(p?.weight)
  if (w === '—') return h
  return `${h} · ${w} lb`
}

export function formatPlayerAttributeCell(p: any, key: string): string {
  const v = p?.[key]
  if (v === null || v === undefined || v === '') return '—'
  if (key === 'height') return formatHeightInches(v)
  if (key === 'weight') return formatWeightLbs(v)
  if (typeof v === 'boolean') return v ? 'Y' : 'N'
  if (typeof v === 'number') {
    if (!Number.isFinite(v)) return '—'
    return Number.isInteger(v) ? String(v) : v.toFixed(1)
  }
  return String(v)
}

/** CSS grid: summary cols + Ht + Wt + one track per scroll attribute (roster & depth candidate tables). */
export function rosterDepthTableGridTemplateColumns(scrollAttrCount: number): string {
  const lead =
    'minmax(200px,1.15fr) minmax(108px,128px) 52px 52px 54px 54px 50px 52px minmax(54px,64px) minmax(48px,56px)'
  const attrs = Array(Math.max(0, scrollAttrCount))
    .fill('minmax(48px,56px)')
    .join(' ')
  return `${lead} ${attrs}`.trim()
}

