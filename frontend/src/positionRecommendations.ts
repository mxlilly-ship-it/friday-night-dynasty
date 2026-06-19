/** Mirrors ``systems.position_changes`` for preseason UI hints. */

const OFFENSE_POSITIONS = ['QB', 'RB', 'WR', 'OL', 'TE'] as const
const DEFENSE_POSITIONS = ['DE', 'DT', 'LB', 'CB', 'S'] as const
const SPECIALIST_POSITIONS = ['K', 'P'] as const
const TWO_WAY_POSITION_FIT_THRESHOLD = 62

const POSITION_RATIOS: Record<string, number> = {
  QB: 0.05,
  RB: 0.1,
  WR: 0.14,
  OL: 0.18,
  TE: 0.05,
  DE: 0.1,
  DT: 0.07,
  LB: 0.12,
  CB: 0.09,
  S: 0.07,
  K: 0.02,
  P: 0.02,
}

const PRIMARY_POSITION_CAPS: Record<string, number> = {
  QB: 2,
  K: 2,
  P: 2,
}

export type PositionRecommendation = {
  position: string
  secondary: string | null
}

function num(p: Record<string, unknown>, key: string, fallback = 50): number {
  const v = Number(p[key])
  return Number.isFinite(v) ? v : fallback
}

function sideForPosition(pos: string): 'off' | 'def' | 'sp' {
  if ((OFFENSE_POSITIONS as readonly string[]).includes(pos)) return 'off'
  if ((DEFENSE_POSITIONS as readonly string[]).includes(pos)) return 'def'
  return 'sp'
}

function positionRatingOffense(p: Record<string, unknown>, pos: string): number {
  if (pos === 'QB') {
    return (num(p, 'throw_power') + num(p, 'throw_accuracy') + num(p, 'decisions') + num(p, 'football_iq')) / 4
  }
  if (pos === 'RB') {
    return (
      num(p, 'speed') +
      num(p, 'break_tackle') +
      num(p, 'vision') +
      num(p, 'ball_security') +
      num(p, 'catching')
    ) / 5
  }
  if (pos === 'WR' || pos === 'TE') {
    return (num(p, 'catching') + num(p, 'route_running') + num(p, 'speed') + num(p, 'agility')) / 4
  }
  if (pos === 'OL') {
    return (num(p, 'run_blocking') + num(p, 'pass_blocking') + num(p, 'strength')) / 3
  }
  return 0
}

function positionRatingDefense(p: Record<string, unknown>, pos: string): number {
  if (pos === 'DE' || pos === 'DT') {
    return (
      num(p, 'pass_rush') +
      num(p, 'run_defense') +
      num(p, 'block_shedding') +
      num(p, 'strength')
    ) / 4
  }
  if (pos === 'LB') {
    return (num(p, 'tackling') + num(p, 'pursuit') + num(p, 'coverage') + num(p, 'run_defense')) / 4
  }
  if (pos === 'CB' || pos === 'S') {
    return (num(p, 'coverage') + num(p, 'speed') + num(p, 'agility') + num(p, 'tackling')) / 4
  }
  return 0
}

function positionRatingSpecialist(p: Record<string, unknown>, pos: string): number {
  if (pos === 'K' || pos === 'P') {
    return (num(p, 'kick_power') + num(p, 'kick_accuracy')) / 2
  }
  return 0
}

function ratingAt(p: Record<string, unknown>, pos: string): number {
  if ((OFFENSE_POSITIONS as readonly string[]).includes(pos)) return positionRatingOffense(p, pos)
  if ((DEFENSE_POSITIONS as readonly string[]).includes(pos)) return positionRatingDefense(p, pos)
  if ((SPECIALIST_POSITIONS as readonly string[]).includes(pos)) return positionRatingSpecialist(p, pos)
  return 0
}

function scalePositionCounts(rosterSize: number): Record<string, number> {
  const size = Math.max(1, rosterSize)
  const counts: Record<string, number> = {}
  for (const [pos, ratio] of Object.entries(POSITION_RATIOS)) {
    counts[pos] = Math.max(pos === 'K' || pos === 'P' || pos === 'QB' ? 1 : 2, Math.floor(size * ratio))
  }
  let total = Object.values(counts).reduce((a, b) => a + b, 0)
  let diff = size - total
  const flexPositions = ['RB', 'WR', 'OL', 'LB', 'CB']
  const step = diff > 0 ? 1 : -1
  let flexIdx = 0
  while (diff !== 0 && flexPositions.length > 0) {
    const pos = flexPositions[flexIdx % flexPositions.length] ?? 'WR'
    counts[pos] = Math.max(2, (counts[pos] ?? 2) + step)
    diff -= step
    flexIdx += 1
  }
  for (const [pos, cap] of Object.entries(PRIMARY_POSITION_CAPS)) {
    if (counts[pos] != null) counts[pos] = Math.min(counts[pos], cap)
  }
  return counts
}

function positionFillPriority(pos: string, cap: number): [number, number, string] {
  if (pos === 'K') return [0, 0, pos]
  if (pos === 'P') return [0, 1, pos]
  if (pos === 'QB') return [0, 2, pos]
  return [1, cap, pos]
}

function assignBalancedPrimaryPositions(roster: Record<string, unknown>[]): Map<Record<string, unknown>, string> {
  const assignments = new Map<Record<string, unknown>, string>()
  if (roster.length < 1) return assignments

  const targets = scalePositionCounts(roster.length)
  const counts: Record<string, number> = Object.fromEntries(Object.keys(targets).map((k) => [k, 0]))
  const unassigned = new Set(roster)

  const fillOrder = Object.keys(targets).sort((a, b) => {
    const pa = positionFillPriority(a, targets[a] ?? 0)
    const pb = positionFillPriority(b, targets[b] ?? 0)
    return pa[0] - pb[0] || pa[1] - pb[1] || pa[2].localeCompare(pb[2])
  })

  for (const pos of fillOrder) {
    const cap = targets[pos] ?? 0
    if (cap <= 0) continue
    const candidates = [...unassigned].sort((a, b) => ratingAt(b, pos) - ratingAt(a, pos))
    for (const p of candidates) {
      if ((counts[pos] ?? 0) >= cap) break
      assignments.set(p, pos)
      unassigned.delete(p)
      counts[pos] = (counts[pos] ?? 0) + 1
    }
  }

  const flexPositions = Object.keys(targets).filter(
    (p) => !(SPECIALIST_POSITIONS as readonly string[]).includes(p) && p !== 'QB',
  )
  for (const p of [...unassigned]) {
    const options = flexPositions
      .filter((pos) => (counts[pos] ?? 0) < (targets[pos] ?? 0))
      .map((pos) => [pos, ratingAt(p, pos)] as const)
      .sort((a, b) => b[1] - a[1])
    const pos =
      options[0]?.[0] ??
      flexPositions.reduce((best, candidate) => (ratingAt(p, candidate) > ratingAt(p, best) ? candidate : best), 'WR')
    assignments.set(p, pos)
    unassigned.delete(p)
    counts[pos] = (counts[pos] ?? 0) + 1
  }

  return assignments
}

function assignSecondaryForPlayer(p: Record<string, unknown>, primary: string): string | null {
  const candidates: Array<[string, number, 'off' | 'def' | 'sp']> = []
  for (const pos of OFFENSE_POSITIONS) {
    candidates.push([pos, positionRatingOffense(p, pos), sideForPosition(pos)])
  }
  for (const pos of DEFENSE_POSITIONS) {
    candidates.push([pos, positionRatingDefense(p, pos), sideForPosition(pos)])
  }
  candidates.sort((a, b) => b[1] - a[1])

  const primarySide = sideForPosition(primary)
  if (primarySide === 'sp') return null
  const other = primarySide === 'off' ? 'def' : 'off'
  for (const [pos, rating, s] of candidates) {
    if (pos === primary) continue
    if (s === other && rating >= TWO_WAY_POSITION_FIT_THRESHOLD) return pos
  }
  return null
}

/** Balanced coach recommendations for an entire roster (mirrors CPU preseason assignment). */
export function recommendBalancedPositionsForRoster(
  roster: Record<string, unknown>[],
): Record<string, PositionRecommendation> {
  const primaries = assignBalancedPrimaryPositions(roster)
  const out: Record<string, PositionRecommendation> = {}
  for (const p of roster) {
    const name = String(p.name ?? '')
    if (!name) continue
    const primary = primaries.get(p) ?? String(p.position ?? 'WR')
    out[name] = {
      position: primary,
      secondary: assignSecondaryForPlayer(p, primary),
    }
  }
  return out
}

/** Single-player fit (unbalanced). Prefer ``recommendBalancedPositionsForRoster`` when roster is available. */
export function recommendPlayerPositions(p: Record<string, unknown>): PositionRecommendation {
  const candidates: Array<[string, number, 'off' | 'def' | 'sp']> = []
  for (const pos of OFFENSE_POSITIONS) {
    candidates.push([pos, positionRatingOffense(p, pos), sideForPosition(pos)])
  }
  for (const pos of DEFENSE_POSITIONS) {
    candidates.push([pos, positionRatingDefense(p, pos), sideForPosition(pos)])
  }
  for (const pos of SPECIALIST_POSITIONS) {
    candidates.push([pos, positionRatingSpecialist(p, pos), sideForPosition(pos)])
  }
  candidates.sort((a, b) => b[1] - a[1])
  const [bestPos, , side] = candidates[0] ?? ['WR', 0, 'off']
  let secondary: string | null = null
  if (side !== 'sp') {
    const other = side === 'off' ? 'def' : 'off'
    for (const [pos, rating, s] of candidates) {
      if (s === other && pos !== bestPos && rating >= TWO_WAY_POSITION_FIT_THRESHOLD) {
        secondary = pos
        break
      }
    }
  }
  return { position: bestPos, secondary }
}

export function formatPositionRecommendation(rec: PositionRecommendation): string {
  if (rec.secondary) return `${rec.position} · ${rec.secondary}`
  return rec.position
}

/** Recommended primary counts per position for a roster size (mirrors CPU assignment targets). */
export function primaryPositionTargets(rosterSize: number): Record<string, number> {
  return scalePositionCounts(rosterSize)
}

export const ALL_POSITIONS_ORDERED = [
  ...OFFENSE_POSITIONS,
  ...DEFENSE_POSITIONS,
  ...SPECIALIST_POSITIONS,
] as const

/** Count primary positions from a name → { position } draft map. */
export function countPrimaryPositions(
  draft: Record<string, { position: string }>,
): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const pos of ALL_POSITIONS_ORDERED) counts[pos] = 0
  for (const entry of Object.values(draft)) {
    const pos = String(entry.position ?? '').trim()
    if (pos) counts[pos] = (counts[pos] ?? 0) + 1
  }
  return counts
}
