/**
 * Playbook-shaped depth chart display slots (maps to canonical storage: QB, RB, WR, OL, TE, DE, DT, LB, CB, S).
 * Base personnel matches systems/offensive_personnel.py and systems/defensive_personnel.py.
 */
import {
  DEFENSIVE_PLAYBOOKS,
  DEFENSIVE_PLAYBOOK_TO_FORMATIONS,
  OFFENSIVE_PLAYBOOKS,
  OFFENSIVE_PLAYBOOK_TO_FORMATIONS,
  type DefensivePlaybook,
  type OffensivePlaybook,
} from './newSaveTypes'

export const CANONICAL_OFFENSE_KEYS = ['QB', 'RB', 'WR', 'OL', 'TE'] as const
export const CANONICAL_DEFENSE_KEYS = ['DE', 'DT', 'LB', 'CB', 'S'] as const
export const CANONICAL_STORAGE_KEYS = [...CANONICAL_OFFENSE_KEYS, ...CANONICAL_DEFENSE_KEYS] as const

/** Max depth slots per canonical position (matches systems/depth_chart.py). */
export const POSITION_DEPTH: Record<string, number> = {
  QB: 2,
  RB: 4,
  WR: 6,
  OL: 8,
  TE: 2,
  DE: 4,
  DT: 3,
  LB: 5,
  CB: 4,
  S: 3,
}

export type DepthDisplaySlot = {
  /** Unique UI id (e.g. off_flexbone_rb2). */
  id: string
  /** Label on chart (QB, FB, DL3, SS, …). */
  label: string
  side: 'offense' | 'defense'
  /** Canonical key in depth_chart_order. */
  storageKey: string
  storageIndex: number
  /** Position used for candidate pool / ratings (FB → RB, DL → DE). */
  ratingKey: string
}

export type PlaybookDepthLayout = {
  offensivePlaybook: string
  defensivePlaybook: string
  baseOffenseFormation: string
  baseDefenseFormation: string
  offense: DepthDisplaySlot[]
  defense: DepthDisplaySlot[]
}

type Personnel = { ol: number; rb: number; te: number; wr: number }
type DefPersonnel = { dl: number; lb: number; db: number }

/** (OL, RB, TE, WR) on field — mirrors OFFENSIVE_FORMATION_PERSONNEL. */
const OFFENSIVE_FORMATION_PERSONNEL: Record<string, Personnel> = {
  Dual: { ol: 5, rb: 1, te: 1, wr: 3 },
  Trio: { ol: 5, rb: 1, te: 0, wr: 4 },
  Empty: { ol: 5, rb: 0, te: 0, wr: 5 },
  Pro: { ol: 5, rb: 2, te: 1, wr: 2 },
  Twins: { ol: 5, rb: 1, te: 1, wr: 3 },
  'Trey Wing': { ol: 5, rb: 1, te: 2, wr: 2 },
  Wing: { ol: 5, rb: 1, te: 2, wr: 2 },
  Flexbone: { ol: 5, rb: 3, te: 0, wr: 2 },
  'Double Wing': { ol: 5, rb: 3, te: 2, wr: 0 },
  'Power I': { ol: 5, rb: 3, te: 1, wr: 1 },
  'Wing T': { ol: 5, rb: 3, te: 1, wr: 1 },
  Doubles: { ol: 5, rb: 1, te: 1, wr: 3 },
  'Wide Slot': { ol: 5, rb: 1, te: 1, wr: 3 },
  Goalline: { ol: 5, rb: 2, te: 3, wr: 0 },
}

/** (DL, LB, DB) — mirrors DEFENSIVE_FORMATION_PERSONNEL. */
const DEFENSIVE_FORMATION_PERSONNEL: Record<string, DefPersonnel> = {
  '4-3': { dl: 4, lb: 3, db: 4 },
  '3-4': { dl: 3, lb: 4, db: 4 },
  Nickel: { dl: 4, lb: 2, db: 5 },
  Dime: { dl: 4, lb: 1, db: 6 },
  '5-2': { dl: 5, lb: 2, db: 4 },
  '3-3 Stack': { dl: 3, lb: 3, db: 5 },
  '3-3 Stack 3-High': { dl: 3, lb: 3, db: 5 },
  '6-2': { dl: 6, lb: 2, db: 3 },
}

const OFFENSIVE_PLAYBOOK_BASE_FORMATION: Record<OffensivePlaybook, string> = {
  Spread: 'Dual',
  Pro: 'Pro',
  Flexbone: 'Flexbone',
  Smashmouth: 'Power I',
  'Double Wing': 'Double Wing',
  'Wing T': 'Wing T',
}

const DEFENSIVE_PLAYBOOK_BASE_FORMATION: Record<DefensivePlaybook, string> = {
  '4-3': '4-3',
  '3-4': '3-4',
  '5-2': '5-2',
  '3-3 Stack': '3-3 Stack',
}

/** Maps DL display index → DE/DT storage (DE chain then DT, same as defensive_personnel._dl_depth_chain). */
function dlStorageAt(displayIndex: number, dlCount: number): { storageKey: 'DE' | 'DT'; storageIndex: number } {
  const chains: Record<number, Array<{ storageKey: 'DE' | 'DT'; storageIndex: number }>> = {
    3: [
      { storageKey: 'DE', storageIndex: 0 },
      { storageKey: 'DT', storageIndex: 0 },
      { storageKey: 'DT', storageIndex: 1 },
    ],
    4: [
      { storageKey: 'DE', storageIndex: 0 },
      { storageKey: 'DE', storageIndex: 1 },
      { storageKey: 'DT', storageIndex: 0 },
      { storageKey: 'DT', storageIndex: 1 },
    ],
    5: [
      { storageKey: 'DE', storageIndex: 0 },
      { storageKey: 'DE', storageIndex: 1 },
      { storageKey: 'DT', storageIndex: 0 },
      { storageKey: 'DT', storageIndex: 1 },
      { storageKey: 'DE', storageIndex: 2 },
    ],
    6: [
      { storageKey: 'DE', storageIndex: 0 },
      { storageKey: 'DE', storageIndex: 1 },
      { storageKey: 'DT', storageIndex: 0 },
      { storageKey: 'DT', storageIndex: 1 },
      { storageKey: 'DE', storageIndex: 2 },
      { storageKey: 'DE', storageIndex: 3 },
    ],
  }
  const chain = chains[dlCount] ?? chains[4]!
  return chain[Math.min(displayIndex, chain.length - 1)]!
}

/** CB depth then S depth (defensive_personnel._db_depth_chain). */
function dbStorageAt(displayIndex: number, dbCount: number): { storageKey: 'CB' | 'S'; storageIndex: number } {
  const cbCount = dbCount <= 4 ? Math.max(2, dbCount - 2) : dbCount - 2
  if (displayIndex < cbCount) {
    return { storageKey: 'CB', storageIndex: displayIndex }
  }
  return { storageKey: 'S', storageIndex: displayIndex - cbCount }
}

function dbLabel(displayIndex: number, dbCount: number): string {
  const cbCount = dbCount <= 4 ? Math.max(2, dbCount - 2) : dbCount - 2
  if (displayIndex < cbCount) return `CB${displayIndex + 1}`
  const sIdx = displayIndex - cbCount
  if (dbCount === 4 && sIdx === 0) return 'SS'
  if (dbCount === 4 && sIdx === 1) return 'FS'
  return sIdx === 0 ? 'SS' : 'FS'
}

function rbLabel(index: number, rbCount: number, playbook: string): string {
  if (playbook === 'Flexbone' && rbCount === 3) {
    if (index === 0) return 'RB'
    if (index === 1) return 'RB'
    return 'FB'
  }
  if (playbook === 'Wing T' && rbCount === 3) {
    if (index === 0) return 'RB'
    if (index === 1) return 'WB'
    return 'FB'
  }
  if (rbCount === 1) return 'RB'
  return `RB${index + 1}`
}

function buildOffenseDisplaySlots(playbook: string, personnel: Personnel): DepthDisplaySlot[] {
  const slots: DepthDisplaySlot[] = []
  let n = 0
  const nextId = () => `off_${playbook.replace(/\s+/g, '_')}_${n++}`

  slots.push({
    id: nextId(),
    label: 'QB',
    side: 'offense',
    storageKey: 'QB',
    storageIndex: 0,
    ratingKey: 'QB',
  })

  for (let i = 0; i < personnel.rb; i += 1) {
    slots.push({
      id: nextId(),
      label: rbLabel(i, personnel.rb, playbook),
      side: 'offense',
      storageKey: 'RB',
      storageIndex: i,
      ratingKey: 'RB',
    })
  }

  for (let i = 0; i < personnel.te; i += 1) {
    slots.push({
      id: nextId(),
      label: personnel.te === 1 ? 'TE' : `TE${i + 1}`,
      side: 'offense',
      storageKey: 'TE',
      storageIndex: i,
      ratingKey: 'TE',
    })
  }

  for (let i = 0; i < personnel.wr; i += 1) {
    slots.push({
      id: nextId(),
      label: personnel.wr === 1 ? 'WR' : `WR${i + 1}`,
      side: 'offense',
      storageKey: 'WR',
      storageIndex: i,
      ratingKey: 'WR',
    })
  }

  for (let i = 0; i < personnel.ol; i += 1) {
    slots.push({
      id: nextId(),
      label: `OL${i + 1}`,
      side: 'offense',
      storageKey: 'OL',
      storageIndex: i,
      ratingKey: 'OL',
    })
  }

  return slots
}

function buildDefenseDisplaySlots(playbook: string, personnel: DefPersonnel): DepthDisplaySlot[] {
  const slots: DepthDisplaySlot[] = []
  let n = 0
  const nextId = () => `def_${playbook.replace(/\s+/g, '_')}_${n++}`

  for (let i = 0; i < personnel.dl; i += 1) {
    const { storageKey, storageIndex } = dlStorageAt(i, personnel.dl)
    slots.push({
      id: nextId(),
      label: `DL${i + 1}`,
      side: 'defense',
      storageKey,
      storageIndex,
      ratingKey: storageKey,
    })
  }

  for (let i = 0; i < personnel.lb; i += 1) {
    slots.push({
      id: nextId(),
      label: personnel.lb === 1 ? 'LB' : `LB${i + 1}`,
      side: 'defense',
      storageKey: 'LB',
      storageIndex: i,
      ratingKey: 'LB',
    })
  }

  for (let i = 0; i < personnel.db; i += 1) {
    const { storageKey, storageIndex } = dbStorageAt(i, personnel.db)
    slots.push({
      id: nextId(),
      label: dbLabel(i, personnel.db),
      side: 'defense',
      storageKey,
      storageIndex,
      ratingKey: storageKey,
    })
  }

  return slots
}

export function normalizeOffensivePlaybook(value: unknown): OffensivePlaybook {
  const s = String(value ?? '').trim()
  if ((OFFENSIVE_PLAYBOOKS as readonly string[]).includes(s)) return s as OffensivePlaybook
  return 'Spread'
}

export function normalizeDefensivePlaybook(value: unknown): DefensivePlaybook {
  const s = String(value ?? '').trim()
  if ((DEFENSIVE_PLAYBOOKS as readonly string[]).includes(s)) return s as DefensivePlaybook
  return '4-3'
}

export function getPlaybookDepthLayout(
  offensivePlaybookRaw: unknown,
  defensivePlaybookRaw: unknown,
): PlaybookDepthLayout {
  const offensivePlaybook = normalizeOffensivePlaybook(offensivePlaybookRaw)
  const defensivePlaybook = normalizeDefensivePlaybook(defensivePlaybookRaw)

  const baseOffenseFormation =
    OFFENSIVE_PLAYBOOK_BASE_FORMATION[offensivePlaybook] ??
    OFFENSIVE_PLAYBOOK_TO_FORMATIONS[offensivePlaybook]?.[0] ??
    'Dual'
  const baseDefenseFormation =
    DEFENSIVE_PLAYBOOK_BASE_FORMATION[defensivePlaybook] ??
    DEFENSIVE_PLAYBOOK_TO_FORMATIONS[defensivePlaybook]?.[0] ??
    '4-3'

  const offPersonnel = OFFENSIVE_FORMATION_PERSONNEL[baseOffenseFormation] ?? OFFENSIVE_FORMATION_PERSONNEL.Dual!
  const defPersonnel = DEFENSIVE_FORMATION_PERSONNEL[baseDefenseFormation] ?? DEFENSIVE_FORMATION_PERSONNEL['4-3']!

  return {
    offensivePlaybook,
    defensivePlaybook,
    baseOffenseFormation,
    baseDefenseFormation,
    offense: buildOffenseDisplaySlots(offensivePlaybook, offPersonnel),
    defense: buildDefenseDisplaySlots(defensivePlaybook, defPersonnel),
  }
}

export function getCoachPlaybooksFromSave(saveState: any, userTeam: string): {
  offensive: string
  defensive: string
} {
  const team = (saveState?.teams ?? []).find((t: any) => t?.name === userTeam)
  const coach = team?.coach ?? {}
  return {
    offensive: String(coach.offensive_formation ?? 'Spread'),
    defensive: String(coach.defensive_formation ?? '4-3'),
  }
}

export function getSlotPlayerName(order: Record<string, string[]>, slot: DepthDisplaySlot): string {
  return order[slot.storageKey]?.[slot.storageIndex] ?? '—'
}

export function setSlotPlayerName(
  order: Record<string, string[]>,
  slot: DepthDisplaySlot,
  playerName: string,
): Record<string, string[]> {
  const key = slot.storageKey
  const arr = [...(order[key] ?? [])]
  while (arr.length <= slot.storageIndex) arr.push('—')
  const prevName = arr[slot.storageIndex]
  const nextName = playerName === '' ? '—' : playerName
  arr[slot.storageIndex] = nextName
  if (prevName && prevName !== '—' && nextName !== '—') {
    const swapIdx = arr.findIndex((n, i) => i !== slot.storageIndex && n === nextName)
    if (swapIdx >= 0) arr[swapIdx] = prevName
  }
  return { ...order, [key]: arr }
}

export function allDisplaySlots(layout: PlaybookDepthLayout): DepthDisplaySlot[] {
  return [...layout.offense, ...layout.defense]
}

export function findDisplaySlot(layout: PlaybookDepthLayout, slotId: string): DepthDisplaySlot | undefined {
  return allDisplaySlots(layout).find((s) => s.id === slotId)
}
