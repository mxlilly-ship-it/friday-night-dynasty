/** Build combined offseason growth report (Winter + Spring + Training Results). */

export type AttributeChangeRow = {
  attr: string
  label: string
  before?: number
  after?: number
  delta: number
  base?: number
  equipment?: number
}

export type OffseasonPhaseSection = {
  id: string
  title: string
  subtitle?: string
  changes: AttributeChangeRow[]
  emptyMessage?: string
}

export type OffseasonPlayerReport = {
  playerName: string
  position: string
  yearLabel: string
  ovr?: { before: number; after: number; delta: number }
  sections: OffseasonPhaseSection[]
}

const ATTR_LABELS: Record<string, string> = {
  speed: 'Speed',
  agility: 'Agility',
  acceleration: 'Acceleration',
  strength: 'Strength',
  balance: 'Balance',
  jumping: 'Jumping',
  stamina: 'Stamina',
  injury: 'Injury',
  frame: 'Frame',
  toughness: 'Toughness',
  effort: 'Effort',
  football_iq: 'Football IQ',
  coachability: 'Coachability',
  confidence: 'Confidence',
  discipline: 'Discipline',
  leadership: 'Leadership',
  composure: 'Composure',
  throw_power: 'Throw power',
  throw_accuracy: 'Throw accuracy',
  decisions: 'Decisions',
  catching: 'Catching',
  run_blocking: 'Run blocking',
  pass_blocking: 'Pass blocking',
  vision: 'Vision',
  ball_security: 'Ball security',
  break_tackle: 'Break tackle',
  elusiveness: 'Elusiveness',
  route_running: 'Route running',
  coverage: 'Coverage',
  blitz: 'Blitz',
  pass_rush: 'Pass rush',
  run_defense: 'Run defense',
  pursuit: 'Pursuit',
  tackling: 'Tackling',
  block_shedding: 'Block shedding',
  kick_power: 'Kick power',
  kick_accuracy: 'Kick accuracy',
}

export function formatAttrLabel(key: string): string {
  return ATTR_LABELS[key] ?? key.replace(/_/g, ' ')
}

function formatYear(year: unknown): string {
  const n = Number(year)
  if (Number.isNaN(n)) return '—'
  if (n === 9 || n === 1) return 'FR'
  if (n === 10 || n === 2) return 'SO'
  if (n === 11 || n === 3) return 'JR'
  if (n === 12 || n === 4) return 'SR'
  return String(year)
}

function rowsFromAttributeDeltas(deltas: Record<string, number> | null | undefined): AttributeChangeRow[] {
  if (!deltas || typeof deltas !== 'object') return []
  return Object.entries(deltas)
    .filter(([, v]) => Number(v) !== 0)
    .map(([attr, delta]) => ({
      attr,
      label: formatAttrLabel(attr),
      delta: Number(delta),
    }))
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta) || a.label.localeCompare(b.label))
}

function findPlayerOnTeam(saveState: any, userTeam: string, playerName: string) {
  const team = (saveState?.teams as any[] | undefined)?.find((t) => t?.name === userTeam)
  const player = team?.roster?.find((p: any) => String(p?.name) === playerName)
  return { team, player }
}

function winterPlayerChanges(result: any, playerName: string): AttributeChangeRow[] {
  const rows = Array.isArray(result?.player_rows) ? result.player_rows : []
  const row = rows.find((r: any) => String(r?.player_name) === playerName)
  return rowsFromAttributeDeltas(row?.attribute_deltas)
}

function springPlayerChanges(result: any, playerName: string): AttributeChangeRow[] {
  const rows = Array.isArray(result?.player_rows) ? result.player_rows : []
  const row = rows.find((r: any) => String(r?.player_name) === playerName)
  if (row?.attribute_deltas) return rowsFromAttributeDeltas(row.attribute_deltas)
  const notable = Array.isArray(result?.notable_players) ? result.notable_players : []
  return notable
    .filter((n: any) => String(n?.player_name) === playerName)
    .map((n: any) => ({
      attr: String(n.attribute ?? ''),
      label: formatAttrLabel(String(n.attribute ?? '')),
      delta: Number(n.delta ?? 0),
    }))
    .filter((r: { delta: number }) => r.delta !== 0)
}

function trainingSection(saveState: any, playerName: string): OffseasonPhaseSection | null {
  const players = saveState?.offseason_training_results?.players
  if (!Array.isArray(players)) return null
  const row = players.find((p: any) => String(p?.name) === playerName)
  if (!row) return null
  const attrs = row.attributes && typeof row.attributes === 'object' ? row.attributes : {}
  const changes: AttributeChangeRow[] = Object.entries(attrs)
    .map(([attr, raw]) => {
      const v = raw as Record<string, number>
      return {
        attr,
        label: formatAttrLabel(attr),
        before: Number(v.before),
        after: Number(v.after),
        delta: Number(v.delta ?? Number(v.after) - Number(v.before)),
        base: Number(v.base ?? 0),
        equipment: Number(v.equipment ?? 0),
      }
    })
    .filter((c) => c.delta !== 0)
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta) || a.label.localeCompare(b.label))

  return {
    id: 'training-results',
    title: 'Training & development',
    subtitle: 'Main offseason growth + program equipment',
    changes,
    emptyMessage: 'No attribute changes (freshman or capped by potential)',
  }
}

export function buildOffseasonPlayerReport(
  saveState: any,
  userTeam: string,
  playerName: string,
): OffseasonPlayerReport | null {
  const pn = String(playerName ?? '').trim()
  if (!pn || !userTeam) return null

  const { player } = findPlayerOnTeam(saveState, userTeam, pn)
  const position = String(player?.position ?? '—')
  const yearLabel = formatYear(player?.year)

  const sections: OffseasonPhaseSection[] = []

  const winterHist = Array.isArray(saveState?.offseason_winter_history) ? saveState.offseason_winter_history : []
  for (const entry of winterHist) {
    const stage = String(entry?.stage ?? 'Winter training')
    sections.push({
      id: `winter-${stage}`,
      title: stage,
      subtitle: entry?.user_team_result?.summary ? String(entry.user_team_result.summary) : undefined,
      changes: winterPlayerChanges(entry?.user_team_result, pn),
      emptyMessage: 'No gains this session',
    })
  }

  const liveWinter = saveState?.offseason_winter_training_results?.user_team_result
  if (liveWinter) {
    const stage = String(saveState?.offseason_winter_training_results?.stage ?? liveWinter?.stage ?? 'Winter')
    if (!sections.some((s) => s.title === stage)) {
      sections.push({
        id: `winter-live-${stage}`,
        title: stage,
        subtitle: liveWinter.summary ? String(liveWinter.summary) : undefined,
        changes: winterPlayerChanges(liveWinter, pn),
        emptyMessage: 'No gains this session',
      })
    }
  }

  const springResult =
    saveState?.offseason_spring_history ?? saveState?.offseason_spring_ball_results?.user_team_result
  if (springResult) {
    const off = String(springResult.offensive_focus ?? '').replace(/_/g, ' ')
    const def = String(springResult.defensive_focus ?? '').replace(/_/g, ' ')
    sections.push({
      id: 'spring-ball',
      title: 'Spring Ball',
      subtitle: [off && `Off: ${off}`, def && `Def: ${def}`].filter(Boolean).join(' · '),
      changes: springPlayerChanges(springResult, pn),
      emptyMessage: 'No gains this spring',
    })
  }

  const training = trainingSection(saveState, pn)
  if (training) sections.push(training)

  const trainingRow = saveState?.offseason_training_results?.players?.find((p: any) => String(p?.name) === pn)
  const ovr = trainingRow
    ? {
        before: Number(trainingRow.before ?? 0),
        after: Number(trainingRow.after ?? 0),
        delta: Number(trainingRow.delta ?? 0),
      }
    : undefined

  if (sections.length === 0 && !ovr) return null

  return {
    playerName: pn,
    position,
    yearLabel,
    ovr,
    sections,
  }
}
