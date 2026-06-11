/** Mirrors ``systems.position_changes.recommend_player_positions`` for preseason UI hints. */

const OFFENSE_POSITIONS = ['QB', 'RB', 'WR', 'OL', 'TE'] as const
const DEFENSE_POSITIONS = ['DE', 'DT', 'LB', 'CB', 'S'] as const
const SPECIALIST_POSITIONS = ['K', 'P'] as const
const TWO_WAY_POSITION_FIT_THRESHOLD = 62

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
