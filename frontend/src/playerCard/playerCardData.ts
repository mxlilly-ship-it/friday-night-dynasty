import { formatHeightInches } from '../playerAttributes'
import { buildPlayerStatRows } from '../playerSeasonStats'

/** Mirrors `PlayerData` in playerCard.js */
export type PlayerCardData = {
  name: string
  school: string
  positions: string[]
  classYear: string
  height: string
  weightLbs: number
  age: number
  overallRating: number
  positionRatings: { label: string; value: number }[]
  attributes: {
    physical: Record<string, number>
    mental: Record<string, number>
    offense: Record<string, number>
    defense: Record<string, number>
    kicking: Record<string, number>
    development: Record<string, number>
  }
  careerStats: {
    label: string
    gp: number | null
    tackles: number | null
    tfl: number | null
    sacks: number | null
    ff: number | null
    blk: number | null
    ovr: number
    inProgress?: boolean
  }[]
  positionFitRatings: {
    offense: Record<string, number>
    defense: Record<string, number>
  }
  facePhotoSrc?: string
  teamLogoSrc?: string
}

const OFFENSE_POSITIONS = ['QB', 'RB', 'WR', 'OL', 'TE'] as const
const DEFENSE_POSITIONS = ['DE', 'DT', 'LB', 'CB', 'S'] as const

const OFFENSE_FIT_ORDER = ['QB', 'RB', 'TE', 'WR', 'OL']
const DEFENSE_FIT_ORDER = ['DE', 'DT', 'LB', 'S', 'CB']

function num(p: any, key: string, fallback = 50) {
  const v = Number(p?.[key])
  return Number.isFinite(v) ? v : fallback
}

function computeOffenseRating(p: any, pos: string) {
  if (pos === 'QB') return (num(p, 'throw_power') + num(p, 'throw_accuracy') + num(p, 'decisions') + num(p, 'football_iq')) / 4
  if (pos === 'RB')
    return (num(p, 'speed') + num(p, 'break_tackle') + num(p, 'vision') + num(p, 'ball_security') + num(p, 'catching')) / 5
  if (pos === 'WR' || pos === 'TE') return (num(p, 'catching') + num(p, 'route_running') + num(p, 'speed') + num(p, 'agility')) / 4
  if (pos === 'OL') return (num(p, 'run_blocking') + num(p, 'pass_blocking') + num(p, 'strength')) / 3
  return 0
}

function computeDefenseRating(p: any, pos: string) {
  if (pos === 'DE' || pos === 'DT')
    return (num(p, 'pass_rush') + num(p, 'run_defense') + num(p, 'block_shedding') + num(p, 'strength')) / 4
  if (pos === 'LB') return (num(p, 'tackling') + num(p, 'pursuit') + num(p, 'coverage') + num(p, 'run_defense')) / 4
  if (pos === 'CB' || pos === 'S') return (num(p, 'coverage') + num(p, 'speed') + num(p, 'agility') + num(p, 'tackling')) / 4
  return 0
}

function computePlayerOverall(p: any) {
  const primary = String(p?.position ?? '')
  if (OFFENSE_POSITIONS.includes(primary as (typeof OFFENSE_POSITIONS)[number])) {
    return Math.round(computeOffenseRating(p, primary))
  }
  if (DEFENSE_POSITIONS.includes(primary as (typeof DEFENSE_POSITIONS)[number])) {
    return Math.round(computeDefenseRating(p, primary))
  }
  if (primary === 'K' || primary === 'P') {
    return Math.round((num(p, 'kick_power') + num(p, 'kick_accuracy')) / 2)
  }
  const keys = ['speed', 'strength', 'football_iq', 'tackling', 'coverage', 'throw_accuracy']
  return Math.round(keys.reduce((s, k) => s + num(p, k), 0) / keys.length)
}

function classYearLabel(year: unknown): string {
  const n = Number(year)
  if (n === 9 || n === 1) return 'Freshman'
  if (n === 10 || n === 2) return 'Sophomore'
  if (n === 11 || n === 3) return 'Junior'
  if (n === 12 || n === 4) return 'Senior'
  return year != null ? String(year) : '—'
}

function shortYearLabel(year: unknown, calendarYear: number): string {
  const n = Number(year)
  let abbr = '—'
  if (n === 9 || n === 1) abbr = 'Fr'
  else if (n === 10 || n === 2) abbr = 'So'
  else if (n === 11 || n === 3) abbr = 'Jr'
  else if (n === 12 || n === 4) abbr = 'Sr'
  const yy = String(calendarYear).slice(-2)
  return `${abbr} · '${yy}`
}

function sidePosition(p: any, side: 'offense' | 'defense'): string | null {
  const allowed = side === 'offense' ? OFFENSE_POSITIONS : DEFENSE_POSITIONS
  const primary = String(p?.position ?? '')
  const secondary = String(p?.secondary_position ?? '')
  if ((allowed as readonly string[]).includes(primary)) return primary
  if ((allowed as readonly string[]).includes(secondary)) return secondary
  return null
}

function countGamesPlayed(saveState: any, teamName: string, playerName: string): number {
  let gp = 0
  for (const wk of saveState?.week_results ?? []) {
    for (const g of wk ?? []) {
      if (!g?.played) continue
      const stats = g?.player_stats ?? []
      if (
        stats.some(
          (s: any) => String(s?.team_name ?? '') === teamName && String(s?.player_name ?? '') === playerName,
        )
      ) {
        gp += 1
      }
    }
  }
  return gp
}

function seasonInProgress(saveState: any): boolean {
  const phase = String(saveState?.season_phase ?? '').toLowerCase()
  return phase !== 'season_summary' && phase !== 'offseason' && phase !== 'done'
}

function pickAttributes(p: any, entries: [string, string][]): Record<string, number> {
  const out: Record<string, number> = {}
  for (const [key, label] of entries) {
    out[label] = Math.round(num(p, key))
  }
  return out
}

const MENTAL_KEYS: [string, string][] = [
  ['football_iq', 'Football IQ'],
  ['coachability', 'Coachability'],
  ['composure', 'Composure'],
  ['leadership', 'Leadership'],
  ['toughness', 'Toughness'],
  ['confidence', 'Confidence'],
  ['effort', 'Effort'],
  ['discipline', 'Discipline'],
]

const OFFENSE_KEYS: [string, string][] = [
  ['pass_blocking', 'Pass block'],
  ['run_blocking', 'Run block'],
  ['catching', 'Catching'],
  ['elusiveness', 'Elusiveness'],
  ['decisions', 'Decisions'],
  ['break_tackle', 'Break tackle'],
  ['route_running', 'Route running'],
  ['vision', 'Vision'],
  ['ball_security', 'Ball security'],
  ['throw_power', 'Throw power'],
  ['throw_accuracy', 'Throw accuracy'],
]

const DEFENSE_KEYS: [string, string][] = [
  ['coverage', 'Coverage'],
  ['blitz', 'Blitz'],
  ['tackling', 'Tackling'],
  ['run_defense', 'Run defense'],
  ['block_shedding', 'Block shed'],
  ['pass_rush', 'Pass rush'],
  ['pursuit', 'Pursuit'],
]

const PHYSICAL_KEYS: [string, string][] = [
  ['acceleration', 'Acceleration'],
  ['strength', 'Strength'],
  ['balance', 'Balance'],
  ['agility', 'Agility'],
  ['stamina', 'Stamina'],
  ['frame', 'Frame'],
  ['jumping', 'Jumping'],
  ['speed', 'Speed'],
  ['injury', 'Injury'],
]

const KICKING_KEYS: [string, string][] = [
  ['kick_power', 'Kick power'],
  ['kick_accuracy', 'Kick accuracy'],
]

const DEV_KEYS: [string, string][] = [
  ['potential', 'Potential'],
  ['consistency', 'Consistency'],
  ['growth_rate', 'Growth rate'],
  ['early_bloomer', 'Early bloomer'],
  ['late_bloomer', 'Late bloomer'],
  ['peak_age', 'Peak age'],
  ['year', 'Class year'],
]

export function buildPlayerCardData(
  player: any,
  teamName: string,
  saveState: any,
  opts?: { teamLogoSrc?: string; facePhotoSrc?: string },
): PlayerCardData {
  const name = String(player?.name ?? 'Unknown')
  const primary = String(player?.position ?? '—')
  const secondary = String(player?.secondary_position ?? '').trim()
  const positions = [primary, secondary].filter((p) => p && p !== '—')

  const offPos = sidePosition(player, 'offense')
  const defPos = sidePosition(player, 'defense')
  const positionRatings: { label: string; value: number }[] = []
  if (offPos) positionRatings.push({ label: `Off ${offPos}`, value: Math.round(computeOffenseRating(player, offPos)) })
  if (defPos) positionRatings.push({ label: `Def ${defPos}`, value: Math.round(computeDefenseRating(player, defPos)) })

  const offenseFit: Record<string, number> = {}
  for (const pos of OFFENSE_FIT_ORDER) offenseFit[pos] = Math.round(computeOffenseRating(player, pos))

  const defenseFit: Record<string, number> = {}
  for (const pos of DEFENSE_FIT_ORDER) defenseFit[pos] = Math.round(computeDefenseRating(player, pos))

  const statRow = buildPlayerStatRows(saveState).find((r) => r.teamName === teamName && r.playerName === name)
  const calendarYear = Number(saveState?.current_year ?? new Date().getFullYear())
  const ovr = computePlayerOverall(player)
  const inProgress = seasonInProgress(saveState)
  const hasLoggedStats =
    !!statRow &&
    statRow.tackles + statRow.sacks + statRow.passYds + statRow.rushYds + statRow.recYds + statRow.rec > 0

  const careerStats: PlayerCardData['careerStats'] = []
  if (inProgress || statRow) {
    careerStats.push({
      label: shortYearLabel(player?.year, calendarYear),
      gp: hasLoggedStats ? countGamesPlayed(saveState, teamName, name) : null,
      tackles: hasLoggedStats ? statRow!.tackles : null,
      tfl: hasLoggedStats ? statRow!.tfl : null,
      sacks: hasLoggedStats ? statRow!.sacks : null,
      ff: null,
      blk: null,
      ovr,
      inProgress: inProgress && !hasLoggedStats,
    })
  }

  const weightRaw = Number(player?.weight)
  return {
    name,
    school: teamName,
    positions,
    classYear: classYearLabel(player?.year),
    height: formatHeightInches(player?.height),
    weightLbs: Number.isFinite(weightRaw) ? Math.round(weightRaw) : 0,
    age: Math.round(num(player, 'age', 16)),
    overallRating: ovr,
    positionRatings,
    attributes: {
      mental: pickAttributes(player, MENTAL_KEYS),
      offense: pickAttributes(player, OFFENSE_KEYS),
      defense: pickAttributes(player, DEFENSE_KEYS),
      physical: pickAttributes(player, PHYSICAL_KEYS),
      kicking: pickAttributes(player, KICKING_KEYS),
      development: pickAttributes(player, DEV_KEYS),
    },
    careerStats,
    positionFitRatings: { offense: offenseFit, defense: defenseFit },
    teamLogoSrc: opts?.teamLogoSrc,
    facePhotoSrc: opts?.facePhotoSrc,
  }
}
