/** Weekly gameplan package types — mirrors systems/weekly_gameplan.py */

export type GameplanMode = 'grid' | 'callsheet'

export type VerticalShots = 'conservative' | 'balanced' | 'aggressive'
export type PressureTendency = 'conservative' | 'balanced' | 'aggressive'
export type CoverageMode = 'normal' | 'bracket_1' | 'rotation_1'

export type TeamScript = {
  pace: number
  clock_management: number
  risk: number
  ball_security: number
  garbage_time: number
  youth_reps: number
  four_minute: number
  go_for_2: number
  vertical_shots: VerticalShots
  pressure_tendency: PressureTendency
  /** Defense team script — run-fit / box emphasis (0 = light box, 100 = stack vs run). */
  def_run_fit: number
  /** Defense team script — coverage style (0 = keep in front, 100 = press and contest). */
  def_coverage: number
  /** Defense team script — 3rd-down aggression (0 = shell, 100 = heat). */
  def_third_down: number
}

export type OffenseUsage = {
  rb_carry_split: string
  wr_target_order: string[]
  qb_designed_runs: number
}

export type SkillTargetPlayer = {
  name: string
  chartPos: 'RB' | 'WR' | 'TE'
  overall: number
  displayPos: string
}

export type DefenseUsage = {
  coverage: CoverageMode
}

export type HalftimeSlot = {
  trigger: string | null
  response: 'A' | 'B' | 'C' | null
}

export type PracticeDay = Record<string, number>

export type SidePackage = {
  version: number
  gameplan_mode: GameplanMode
  confirmed: boolean
  grid: Record<string, unknown>
  callsheet: Record<string, unknown>
  usage: OffenseUsage | DefenseUsage
  practice: Record<string, PracticeDay>
  halftime: { slots: HalftimeSlot[] }
}

export type InstalledPlay = { id: string; name: string }

export type HalftimeTrigger = { id: string; label: string }

export const PRACTICE_DAYS = ['mon', 'tue', 'wed', 'thu'] as const
export const PRACTICE_PILLARS_OFF = [
  'pass_game',
  'run_game',
  'third_down',
  'red_zone',
  'goal_line',
  'opponent_prep',
  'conditioning',
  'rest',
] as const
export const PRACTICE_PILLARS_DEF = [
  'pass_defense',
  'run_defense',
  'third_down',
  'red_zone',
  'goal_line',
  'opponent_prep',
  'conditioning',
  'rest',
] as const

export const OFF_CALLSHEET_SECTIONS: { key: string; label: string; size: number }[] = [
  { key: 'opening', label: 'Opening script', size: 10 },
  { key: 'base_dd', label: 'Base D&D', size: 15 },
  { key: 'third_long', label: '3rd & long (7+)', size: 3 },
  { key: 'third_medium', label: '3rd & medium', size: 3 },
  { key: 'third_short', label: '3rd & short', size: 3 },
  { key: 'fourth_long', label: '4th & long', size: 2 },
  { key: 'fourth_medium', label: '4th & medium', size: 2 },
  { key: 'fourth_short', label: '4th & short', size: 2 },
  { key: 'red_zone', label: 'Red zone', size: 5 },
  { key: 'backed_up', label: 'Backed up', size: 3 },
  { key: 'goal_line', label: 'Goal line', size: 3 },
  { key: 'two_minute', label: '2-minute', size: 4 },
]

export const DEF_CALLSHEET_SECTIONS: { key: string; label: string; size: number }[] = [
  { key: 'base_dd', label: 'Base D&D', size: 8 },
  { key: 'third_long', label: '3rd & long (7+)', size: 3 },
  { key: 'third_medium', label: '3rd & medium', size: 3 },
  { key: 'third_short', label: '3rd & short', size: 3 },
  { key: 'fourth_long', label: '4th & long', size: 2 },
  { key: 'fourth_medium', label: '4th & medium', size: 2 },
  { key: 'fourth_short', label: '4th & short', size: 2 },
  { key: 'red_zone', label: 'Red zone', size: 3 },
  { key: 'goal_line', label: 'Goal line', size: 3 },
  { key: 'opponent_backed_up', label: 'Opponent backed up', size: 2 },
  { key: 'two_minute', label: '2-minute', size: 3 },
]

export const RB_CARRY_OPTIONS = [
  { value: '70_30', label: 'RB1 heavy (70/30)' },
  { value: '60_40', label: 'RB1 lean (60/40)' },
  { value: '55_45', label: 'RB1 slight (55/45)' },
  { value: '50_50', label: 'Even (50/50)' },
  { value: '45_55', label: 'RB2 slight (45/55)' },
  { value: '40_60', label: 'RB2 lean (40/60)' },
  { value: '30_70', label: 'RB2 heavy (30/70)' },
]

export function defaultTeamScript(): TeamScript {
  return {
    pace: 50,
    clock_management: 50,
    risk: 50,
    ball_security: 50,
    garbage_time: 70,
    youth_reps: 40,
    four_minute: 50,
    go_for_2: 50,
    vertical_shots: 'balanced',
    pressure_tendency: 'balanced',
    def_run_fit: 50,
    def_coverage: 50,
    def_third_down: 50,
  }
}

export function emptyPracticeDay(side: 'offense' | 'defense'): PracticeDay {
  const pillars = side === 'offense' ? PRACTICE_PILLARS_OFF : PRACTICE_PILLARS_DEF
  return Object.fromEntries(pillars.map((p) => [p, 0]))
}

export function emptyPractice(side: 'offense' | 'defense'): Record<string, PracticeDay> {
  return Object.fromEntries(PRACTICE_DAYS.map((d) => [d, emptyPracticeDay(side)]))
}

export function emptyHalftimeSlots(): HalftimeSlot[] {
  return [
    { trigger: null, response: null },
    { trigger: null, response: null },
    { trigger: null, response: null },
  ]
}

export function emptyOffenseCallsheet(): Record<string, unknown> {
  const cs: Record<string, unknown> = {}
  for (const s of OFF_CALLSHEET_SECTIONS) {
    cs[s.key] = Array(s.size).fill('')
  }
  cs.vertical_shots = 'balanced'
  return cs
}

export function emptyDefenseCallsheet(): Record<string, unknown> {
  const cs: Record<string, unknown> = {}
  for (const s of DEF_CALLSHEET_SECTIONS) {
    cs[s.key] = Array(s.size).fill('')
  }
  cs.pressure_tendency = 'balanced'
  return cs
}

export function defaultOffenseUsage(): OffenseUsage {
  return {
    rb_carry_split: '50_50',
    wr_target_order: ['', '', '', '', ''],
    qb_designed_runs: 50,
  }
}

export function defaultDefenseUsage(): DefenseUsage {
  return { coverage: 'normal' }
}

export function practicePillarLabel(key: string): string {
  return key
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

/** Halftime A/B/C labels — mirrors systems/weekly_gameplan.py */
export const HALFTIME_RESPONSES_OFF: Record<string, Record<'A' | 'B' | 'C', string>> = {
  run_stuffed: { A: 'Attack perimeter', B: 'Pound inside', C: 'Play-action' },
  qb_pressure: { A: 'Quick game', B: 'Move pocket', C: 'Max protect shots' },
  third_down_fail: { A: 'Quick to sticks', B: 'Run on short 3rd', C: 'Take a shot' },
  rz_stalled: { A: 'Power run', B: 'Spread quick RZ', C: 'Play-action RZ' },
  need_chunks: { A: 'Vertical shots', B: 'Play-action deep', C: 'Perimeter smoke' },
  pass_taken_away: { A: 'Commit to run', B: 'Misdirection', C: 'Tempo looks' },
  blitz_beat_us: { A: 'Hot quick', B: 'Screens', C: 'Slide and run' },
}

export const HALFTIME_RESPONSES_DEF: Record<string, Record<'A' | 'B' | 'C', string>> = {
  run_gashing: { A: 'Heavier packages', B: 'Blitz more', C: 'Play more zone' },
  pass_beating: { A: 'More man', B: 'Zone shell', C: 'Pressure QB' },
  explosives: { A: 'Deep safety help', B: 'Press man', C: 'Simulated pressure' },
  third_down_leaks: { A: 'Tighten short zone', B: 'Heat on 3rd', C: 'Bracket #1' },
  rz_struggling: { A: 'Goal-line heavies', B: 'Man match RZ', C: 'Blitz RZ' },
  qb_scramble: { A: 'Spy contain', B: 'Rush with lanes', C: 'Lock coverage' },
}

export type ScriptKnobHint = { low: string; high: string; mid?: string }

export const TEAM_SCRIPT_HINTS: Record<string, ScriptKnobHint> = {
  pace: { low: 'Slower tempo — fewer plays, more clock burn', high: 'Faster tempo — more plays per game' },
  clock_management: {
    low: 'When leading, run more clock off between snaps',
    high: 'When leading, keep tempo up to score again',
  },
  risk: { low: 'Punt/FG on 4th unless very short', high: 'Go for it on 4th down more often' },
  ball_security: { low: 'Accept more risk for big plays', high: 'Protect the ball — fewer turnovers' },
  four_minute: { low: 'Conservative run-heavy to kill clock', high: 'Aggressive four-minute offense' },
  go_for_2: { low: 'Kick extra points', high: 'Go for two more often' },
  garbage_time: { low: 'Keep starters in when up big', high: 'Pull starters earlier when up big' },
  youth_reps: { low: 'Ride starters', high: 'Get backups more snaps in blowouts' },
  pressure_tendency: { low: 'More coverage shells', high: 'More pressure/blitz' },
  def_run_fit: { low: 'Light box — make them throw', high: 'Heavy run fits — stack the box' },
  def_coverage: { low: 'Keep plays in front — deep safeties', high: 'Press and contest — hunt takeaways' },
  def_third_down: { low: 'Structured shells on 3rd down', high: 'Bring heat — blitz and stunt on 3rd' },
}

export const PRACTICE_DAY_BUDGET = 50

export function practiceDayTotal(practice: Record<string, PracticeDay> | undefined, day: string, pillars: readonly string[]) {
  const row = practice?.[day] ?? {}
  return pillars.reduce((sum, p) => sum + Math.max(0, Number(row[p] ?? 0) || 0), 0)
}

export function countCallsheetPlayIds(callsheet: Record<string, unknown>): Map<string, number> {
  const counts = new Map<string, number>()
  for (const val of Object.values(callsheet)) {
    if (!Array.isArray(val)) continue
    for (const raw of val) {
      const id = String(raw ?? '').trim()
      if (!id) continue
      counts.set(id, (counts.get(id) ?? 0) + 1)
    }
  }
  return counts
}

export function computeSkillPlayerOverall(p: Record<string, unknown> | undefined): number {
  if (!p) return 0
  const keys = [
    'speed',
    'agility',
    'acceleration',
    'strength',
    'football_iq',
    'coachability',
    'throw_accuracy',
    'catching',
    'run_blocking',
    'pass_blocking',
    'tackling',
    'coverage',
  ]
  const vals = keys.map((k) => Number(p[k] ?? 50))
  return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length)
}

/** RB / WR / TE from depth chart with overall for usage target picks. */
export function buildSkillTargetPlayers(team: Record<string, unknown> | null | undefined): SkillTargetPlayer[] {
  if (!team) return []
  const dc = (team.depth_chart_order ?? team.depth_chart) as Record<string, string[]> | undefined
  if (!dc || typeof dc !== 'object') return []
  const roster = (team.roster ?? []) as Record<string, unknown>[]
  const byName = new Map<string, Record<string, unknown>>()
  for (const p of roster) {
    const n = String(p?.name ?? '').trim()
    if (n) byName.set(n, p)
  }
  const out: SkillTargetPlayer[] = []
  const seen = new Set<string>()
  for (const chartPos of ['RB', 'WR', 'TE'] as const) {
    for (const raw of dc[chartPos] ?? []) {
      const name = String(raw ?? '').trim()
      if (!name || seen.has(name)) continue
      seen.add(name)
      const p = byName.get(name)
      const primary = String(p?.position ?? chartPos).trim() || chartPos
      const secondary = String(p?.secondary_position ?? '').trim()
      const displayPos =
        secondary && secondary !== primary && (secondary === 'RB' || secondary === 'WR' || secondary === 'TE')
          ? `${primary}/${secondary}`
          : primary
      out.push({
        name,
        chartPos,
        overall: computeSkillPlayerOverall(p),
        displayPos,
      })
    }
  }
  return out
}

export function formatSkillTargetLabel(player: SkillTargetPlayer): string {
  const ovr = player.overall > 0 ? `${player.overall} OVR` : '— OVR'
  return `${player.name} · ${player.displayPos} · ${ovr}`
}

const EMPTY_TARGET_ORDER = ['', '', '', '', '']

/** Full gameplan JSON for save/reuse. Strips roster-specific target order. */
export function buildGameplanExportPayload(
  offensePackage: SidePackage | null,
  defensePackage: SidePackage | null,
  teamScript: TeamScript,
): Record<string, unknown> {
  const off = offensePackage ? (structuredClone(offensePackage) as SidePackage) : null
  const def = defensePackage ? (structuredClone(defensePackage) as SidePackage) : null
  if (off?.usage && typeof off.usage === 'object') {
    off.usage = {
      ...(off.usage as OffenseUsage),
      wr_target_order: [...EMPTY_TARGET_ORDER],
    }
  }
  return {
    version: 1,
    offense_package: off,
    defense_package: def,
    team_script: teamScript,
  }
}
