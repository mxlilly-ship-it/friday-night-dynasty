/**
 * Maps engine play options into the Coach's Call Sheet buckets
 * (rushing / passing / screen / trick / situational) for offense, defense, and special.
 */

export type CallsheetSide = 'offense' | 'defense' | 'special'
export type CallsheetBucket = 'rushing' | 'passing' | 'screen' | 'trick' | 'situational'

export type CallsheetPlayRow = {
  id: string
  name: string
  tag: 'base' | 'red-zone' | 'third' | 'trick'
  category: string
}

export type CallsheetPlays = Record<CallsheetBucket, CallsheetPlayRow[]>

const BUCKETS: CallsheetBucket[] = ['rushing', 'passing', 'screen', 'trick', 'situational']

export function createEmptyCallsheet(): CallsheetPlays {
  return {
    rushing: [],
    passing: [],
    screen: [],
    trick: [],
    situational: [],
  }
}

/** Red zone: inside opponent 20 (offense-relative ball 80+). */
function offenseRedZone(ballPosition: number): boolean {
  return ballPosition >= 80
}

/** Defense user: "red zone" when backed up near own goal (ball 20 or less). */
function defenseRedZone(ballPosition: number): boolean {
  return ballPosition <= 20
}

export function inferPlayTag(
  isUserOnOffense: boolean,
  ballPosition: number,
  down: number,
  yardsToGo: number,
): CallsheetPlayRow['tag'] {
  const rz = isUserOnOffense ? offenseRedZone(ballPosition) : defenseRedZone(ballPosition)
  if (rz) return 'red-zone'
  if (down === 3 || (down === 4 && yardsToGo <= 3)) return 'third'
  return 'base'
}

function bucketOffenseCategory(cat: string): CallsheetBucket {
  const c = cat.toUpperCase()
  if (c === 'INSIDE_RUN' || c === 'OUTSIDE_RUN') return 'rushing'
  if (c === 'SHORT_PASS' || c === 'MEDIUM_PASS' || c === 'LONG_PASS') return 'passing'
  if (c === 'PLAY_ACTION') return 'screen'
  if (c.includes('SPECIAL') || c.includes('AFTER_TOUCHDOWN') || c.includes('FOURTH')) return 'situational'
  return 'situational'
}

function bucketDefenseCategory(cat: string): CallsheetBucket {
  const c = cat.toUpperCase()
  if (c === 'ZONES') return 'rushing'
  if (c === 'MANS') return 'passing'
  if (c === 'ZONE_PRESSURE') return 'screen'
  if (c === 'MAN_PRESSURE') return 'trick'
  if (c.includes('SPECIAL') || c.includes('AFTER_TOUCHDOWN')) return 'situational'
  return 'situational'
}

function bucketSpecialPlay(p: { id: string; category: string }): CallsheetBucket {
  const id = p.id.toUpperCase()
  const cat = (p.category || '').toUpperCase()
  if (id.includes('KICKOFF') || cat.includes('KICKOFF')) return 'rushing'
  if (id.includes('PAT') || id.includes('FIELD_GOAL') || id.includes('FG') || cat.includes('AFTER_TOUCHDOWN'))
    return 'passing'
  if (id.includes('PUNT') || cat.includes('PUNT')) return 'screen'
  if (id.includes('FAKE')) return 'trick'
  return 'situational'
}

function isSpecialEligible(p: { category: string }): boolean {
  const c = (p.category || '').toUpperCase()
  return (
    c.includes('SPECIAL') ||
    c.includes('AFTER_TOUCHDOWN') ||
    c.includes('KICKOFF') ||
    c.includes('FOURTH')
  )
}

type PlayIn = { id: string; name: string; category: string }

export function buildOffenseCallsheet(
  plays: PlayIn[],
  isUserOnOffense: boolean,
  ballPosition: number,
  down: number,
  yardsToGo: number,
): CallsheetPlays {
  const out = createEmptyCallsheet()
  const tagBase = () => inferPlayTag(isUserOnOffense, ballPosition, down, yardsToGo)
  for (const p of plays) {
    const b = bucketOffenseCategory(p.category || '')
    const row: CallsheetPlayRow = {
      id: p.id,
      name: p.name,
      tag: p.id.toUpperCase().includes('FAKE') ? 'trick' : tagBase(),
      category: p.category || '',
    }
    out[b].push(row)
  }
  for (const k of BUCKETS) out[k].sort((a, b) => a.name.localeCompare(b.name))
  return out
}

export function buildDefenseCallsheet(
  plays: PlayIn[],
  isUserOnOffense: boolean,
  ballPosition: number,
  down: number,
  yardsToGo: number,
): CallsheetPlays {
  const out = createEmptyCallsheet()
  const tagBase = () => inferPlayTag(isUserOnOffense, ballPosition, down, yardsToGo)
  for (const p of plays) {
    const b = bucketDefenseCategory(p.category || '')
    const row: CallsheetPlayRow = {
      id: p.id,
      name: p.name,
      tag: p.id.toUpperCase().includes('FAKE') ? 'trick' : tagBase(),
      category: p.category || '',
    }
    out[b].push(row)
  }
  for (const k of BUCKETS) out[k].sort((a, b) => a.name.localeCompare(b.name))
  return out
}

export function buildSpecialCallsheet(
  offensePlays: PlayIn[],
  defensePlays: PlayIn[],
  isUserOnOffense: boolean,
  ballPosition: number,
  down: number,
  yardsToGo: number,
): CallsheetPlays {
  const out = createEmptyCallsheet()
  const tagBase = () => inferPlayTag(isUserOnOffense, ballPosition, down, yardsToGo)
  const seen = new Set<string>()
  const add = (p: PlayIn) => {
    if (!isSpecialEligible(p)) return
    if (seen.has(p.id)) return
    seen.add(p.id)
    const b = bucketSpecialPlay(p)
    out[b].push({
      id: p.id,
      name: p.name,
      tag: p.id.toUpperCase().includes('FAKE') ? 'trick' : tagBase(),
      category: p.category || '',
    })
  }
  offensePlays.forEach(add)
  defensePlays.forEach(add)
  for (const k of BUCKETS) out[k].sort((a, b) => a.name.localeCompare(b.name))
  return out
}

export const CALLSHEET_BUCKET_LABELS: Record<CallsheetBucket, string> = {
  rushing: 'RUSHING',
  passing: 'PASSING',
  screen: 'SCREEN / RPO',
  trick: 'TRICK PLAYS',
  situational: 'SITUATIONAL',
}

/** Column order in the call sheet grid (matches game_interface.html). */
export const CALLSHEET_BUCKET_ORDER: CallsheetBucket[] = ['rushing', 'passing', 'screen', 'trick', 'situational']

const HEADER_CLASS: Record<CallsheetBucket, string> = {
  rushing: 'rush',
  passing: 'pass',
  screen: 'screen',
  trick: 'trick',
  situational: 'special',
}

const HEADER_ICON: Record<CallsheetBucket, string> = {
  rushing: '🏃',
  passing: '🎯',
  screen: '📡',
  trick: '🃏',
  situational: '⚡',
}

export function callsheetHeaderClass(bucket: CallsheetBucket): string {
  return HEADER_CLASS[bucket]
}

export function callsheetHeaderTitle(bucket: CallsheetBucket): string {
  return `${HEADER_ICON[bucket]} ${CALLSHEET_BUCKET_LABELS[bucket]}`
}
